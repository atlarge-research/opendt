"""OpenDT API - FastAPI Application for datacenter simulation data."""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from odt_common import load_config_from_env
from odt_common.config import DynamicConfigEvent, WorkloadContext
from odt_common.models.topology import (
    CPU,
    Cluster,
    Host,
    Memory,
    MseCPUPowerModel,
    PowerSource,
    Topology,
)
from odt_common.utils import get_kafka_producer
from odt_common.utils.kafka import send_message

from api import hosts, levers, portfolio, startup, twin
from api.carbon_query import CarbonDataQuery, CarbonDataResponse
from api.power_query import PowerDataQuery, PowerDataResponse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """The configuration and one Kafka producer for all requests; compose starts the API once Kafka is up."""
    app.state.config = load_config_from_env()
    app.state.kafka_producer = get_kafka_producer()
    # the runtime settings the control panel sent, by field (until then, the configured ones apply)
    app.state.settings = {}
    app.state.topology = None  # the simulated topology sent last
    yield
    app.state.kafka_producer.close()


app = FastAPI(
    title="OpenDT API",
    description="Open Digital Twin - REST API for datacenter simulation",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Default topology for Swagger UI (matches SURF data)
DEFAULT_TOPOLOGY = Topology(
    clusters=[
        Cluster(
            name="C01",
            hosts=[
                Host(
                    name="H01",
                    count=277,
                    cpu=CPU(coreCount=16, coreSpeed=2100.0),
                    memory=Memory(memorySize=128000000),
                    cpuPowerModel=MseCPUPowerModel(
                        modelType="mse",
                        power=300.0,
                        idlePower=25.0,
                        maxPower=174.0,
                        calibrationFactor=4.0,
                    ),
                )
            ],
            powerSource=PowerSource(carbonTracePath="/app/workload/carbon_zones/NL.parquet"),
        )
    ]
)

# Example for OpenAPI docs
DEFAULT_TOPOLOGY_EXAMPLE = DEFAULT_TOPOLOGY.model_dump(mode="json")


@app.put("/api/topology")
async def update_topology(
    topology: Annotated[
        Topology,
        Body(
            description="Datacenter topology configuration",
            openapi_examples={
                "default": {
                    "summary": "SURF datacenter topology",
                    "description": "Default SURF topology: 277 hosts, 16 cores each @ 2.1 GHz",
                    "value": DEFAULT_TOPOLOGY_EXAMPLE,
                }
            },
        ),
    ] = DEFAULT_TOPOLOGY,
):
    """Publish a new simulated topology; the simulator runs it from its next window of operation."""
    app.state.topology = topology.model_dump(mode="json")
    topic_name = publish("sim_topology", app.state.topology, key="topology")

    return {
        "status": "updated",
        "message": f"Topology published to {topic_name}",
        "clusters": len(topology.clusters),
        "total_hosts": topology.total_host_count(),
        "total_cores": topology.total_core_count(),
        "topic": topic_name,
    }


@app.get("/api/power", response_model=PowerDataResponse)
def get_power_data(
    interval_seconds: int = Query(60, gt=0, le=3600, description="Sampling interval [s]"),
    start_time: datetime | None = Query(None, description="Optional start time (ISO 8601)"),
):
    """The measured and the simulated power (simulator/agg_results.parquet), aligned to one interval and clipped to
    the shorter series."""
    try:
        return PowerDataQuery(run_dir().name, workload()).query(interval_seconds, start_time)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/co2_emission", response_model=CarbonDataResponse)
def get_carbon_emission_data(
    interval_seconds: int = Query(60, gt=0, le=3600, description="Sampling interval [s]"),
    start_time: datetime | None = Query(None, description="Optional start time (ISO 8601)"),
):
    """The simulated CO2 emissions: power draw [W] x carbon intensity [gCO2/kWh] / 1000 = gCO2/h."""
    try:
        return CarbonDataQuery(run_dir().name).query(interval_seconds, start_time)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def workload() -> WorkloadContext:
    """The workload mounted into the container: its trace, measured power, and carbon trace."""
    return WorkloadContext(workload_dir=Path(os.getenv("WORKLOAD_DIR", "/app/workload")))


def run_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/app/data")) / os.getenv("RUN_ID", "")


def twin_run() -> Path:
    """The run folder of this twin; 404 until its first window of operation is complete."""
    if not twin.windows(run_dir()):
        raise HTTPException(status_code=404, detail="No window of operation is complete yet")
    return run_dir()


def publish(topic: str, message: dict, key: str | None = None) -> str:
    """Send a message to one of OpenDT's Kafka topics, by its name in the configuration; returns the topic."""
    name = app.state.config.kafka.topics[topic].name
    send_message(producer=app.state.kafka_producer, topic=name, message=message, key=key)
    return name


@app.get("/api/progress")
def get_progress():
    """While the twin starts: the step it is at and a tip; nothing once its first window is complete."""
    return {"data": startup.progress(run_dir(), time.time())}


@app.get("/api/status")
def get_status():
    """The control panel's values, flat: the twin's time and topology, and the runtime settings as configured or
    as sent last."""
    config = app.state.config
    configured = {
        "speed_factor": config.global_config.speed_factor,
        "calibration": config.global_config.calibration_enabled,
    }
    if calibrator := config.services.calibrator:  # no calibrator, none of its settings
        configured |= {
            "parallel_simulations": calibrator.max_parallel_workers,
            "calibration_min": calibrator.min_value,
            "calibration_max": calibrator.max_value,
            "calibration_points": calibrator.linspace_points,
            "mape_window": calibrator.mape_window_minutes,
        }
    if not twin.windows(run_dir()):  # starting: what is configured, and the workload's topology
        cluster = json.loads(workload().topology_file.read_text())["clusters"][0]
        start = {
            "hosts": cluster["hosts"][0]["count"],
            "carbon_zone": twin.zone(cluster["powerSource"]["carbonTracePath"]),
        }
        return {**configured, **start, **app.state.settings}
    status = twin.status(run_dir())
    return {
        **configured,
        **app.state.settings,
        **status,
        "twin_time": status["twin_time"].isoformat(),
    }


def rows(table) -> Response:
    """A table of the twin for Infinity, {"data": [...]}; no rows until the first window of operation is complete."""
    run = run_dir()
    data = table(run).to_json(orient="records", date_format="iso") if twin.windows(run) else "[]"
    return Response(f'{{"data": {data}}}', media_type="application/json")


@app.get("/api/cluster")
def get_cluster(
    start: datetime | None = None,
    end: datetime | None = None,
    points: Annotated[int | None, Query(gt=0)] = None,
):
    """Hosts, jobs, CPU of the hosts (mean, median; demand vs. capacity in cores), and energy, CO2, and embodied
    CO2 per sample; with `points`, about that many, every so many samples counted from the latest."""

    def cut(run: Path) -> pd.DataFrame:
        cluster = twin.cluster(run).set_index("timestamp")[start:end].reset_index()
        return cluster.iloc[:: -max(1, len(cluster) // points)][::-1] if points else cluster

    return rows(cut)


@app.get("/api/totals")
def get_totals(period: Literal[tuple(twin.PERIODS)] = "day"):
    """Energy [kWh], CO2 [kg], and embodied CO2 [kg] per period; the last period runs up to the twin's time."""
    return rows(lambda run: twin.totals(run, period))


@app.get("/api/scheduling")
def get_scheduling():
    """Per window: hours until all jobs submitted so far are done, and the median time in queue [min]."""
    return rows(twin.scheduling)


@app.get("/api/jobs")
def get_jobs():
    """The jobs not done yet, with their predicted start and finish, and the hours left."""
    return rows(twin.jobs)


@app.get("/api/events")
def get_events(markers: Literal["on", "off"] = "on"):
    """Changes of servers, r, carbon zone, and scheduler, for markers on the graphs; none while switched off."""
    return rows(twin.events) if markers == "on" else {"data": []}


@app.get("/api/arrivals")
def get_arrivals():
    """Jobs submitted per hour so far."""
    return rows(twin.arrivals)


@app.get("/api/hosts")
def get_hosts():
    """The host groups the twin runs, or runs from its next window, as the Topology table shows them."""
    topology = app.state.topology
    if topology is None:
        windows = twin.windows(run_dir())
        if not windows:
            return {"data": []}
        topology = twin.topology(windows[-1])
    return {"data": hosts.rows(topology)}


@app.post("/api/hosts")
def edit_hosts(row: Annotated[hosts.Row, Query()]):
    """Save a row of the Topology table: a host group changed, added (no id), or removed (count 0)."""
    send_topology(row=row)
    return get_hosts()


@app.get("/api/components")
def get_components(part: Literal[tuple(portfolio.PRESETS)]):
    """The names the Topology tables' lists offer: the portfolio's CPUs, GPUs (a host can also have none), or
    racks."""
    names = list(portfolio.parts(part))
    return {"data": [{"name": name} for name in (["None", *names] if part == "GPU" else names)]}


@app.get("/api/portfolio")
def get_portfolio(kind: Literal[tuple(portfolio.PRESETS)]):
    """The CPUs, GPUs, or racks to build the datacenter from, preconfigured and the user's own, with where each
    comes from."""
    return {
        "data": [{"id": name, "name": name, **part} for name, part in portfolio.parts(kind).items()]
    }


@app.post("/api/portfolio")
def edit_portfolio(part: Annotated[portfolio.Part, Query()]):
    """Save a row of a portfolio table: a part changed, added (no id), or removed; 422 if it cannot be."""
    try:
        if part.remove:
            portfolio.remove(part.kind, part.id)
        else:
            portfolio.save(part.kind, part.id, part.model_dump(exclude_none=True))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return get_portfolio(part.kind)


@app.get("/api/accuracy")
def get_accuracy(minutes: int = Query(60, ge=1, le=1440)):
    """Per period (an hour; 5 minutes for the MAPE now): the MAPE [%] and the mean error [kW] of OpenDT's power vs.
    the measured power, the error of the energy so far, and the r the twin ran with."""
    return rows(lambda run: accuracy(run, twin.windows(run)[-1], minutes))


@lru_cache(maxsize=4)  # once per window (`latest`), though several panels ask
def accuracy(run: Path, latest: Path, minutes: int) -> pd.DataFrame:
    power = PowerDataQuery(run_id=run.name, workload_context=workload()).query(interval_seconds=300)
    return twin.accuracy(run, pd.DataFrame([point.model_dump() for point in power.data]), minutes)


def configure(setting: str, value) -> None:
    """A runtime setting of the twin's services, on the compacted sys.config topic, keyed by the setting."""
    event = DynamicConfigEvent(
        setting_key=setting, new_value=value, timestamp=datetime.now(UTC).isoformat(), source="api"
    )
    publish("system", event.model_dump(), key=setting)


def send_topology(**change) -> None:
    """A new simulated topology to the simulator, built on the one sent last; 422 if the twin cannot run it."""
    latest = twin.topology(twin.windows(twin_run())[-1])
    try:
        app.state.topology = levers.topology(app.state.topology, latest, **change)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    publish("sim_topology", app.state.topology, key="topology")


@app.patch("/api/control")
def control(change: levers.Control):
    """Change the running twin: hosts and CO2 zone as a new simulated topology, the scheduler, the replay
    speed, and the calibrator's parallel simulations as runtime settings."""
    if levers.moves_topology(change):
        first = hosts.Row(id=1, count=change.hosts) if change.hosts else None
        send_topology(row=first, zone=change.carbon_zone)
    for field, value in change.model_dump(include=set(levers.SETTINGS), exclude_none=True).items():
        configure(levers.SETTINGS[field], value)
        app.state.settings[field] = value
    return get_status()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
