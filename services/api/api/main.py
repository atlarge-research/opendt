"""OpenDT API - FastAPI Application for datacenter simulation data."""

import logging
import os
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

from api import hosts, levers, twin
from api.carbon_query import CarbonDataQuery, CarbonDataResponse
from api.power_query import PowerDataQuery, PowerDataResponse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting OpenDT API service...")

    try:
        app.state.config = load_config_from_env()
        logger.info(f"Configuration loaded for workload: {app.state.config.workload}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        app.state.config = None

    try:
        app.state.kafka_producer = get_kafka_producer()
        logger.info("Kafka producer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Kafka producer: {e}")
        app.state.kafka_producer = None

    # the runtime settings the control panel sent, by field (until then, the configured ones apply)
    app.state.settings = {}
    app.state.topology = None  # the simulated topology sent last
    yield

    logger.info("Shutting down OpenDT API service...")
    if app.state.kafka_producer:
        app.state.kafka_producer.close()
        logger.info("Kafka producer closed")


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
    """Health check endpoint."""
    kafka_status = "connected" if app.state.kafka_producer else "disconnected"
    config_status = "loaded" if app.state.config else "not loaded"

    return {
        "status": "healthy",
        "kafka": kafka_status,
        "config": config_status,
    }


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
    topic_name = publish("sim_topology", app.state.topology, key="datacenter")

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
    interval_seconds: int = Query(
        60, gt=0, le=3600, description="Sampling interval in seconds (1-3600)"
    ),
    start_time: datetime | None = Query(None, description="Optional start time (ISO 8601 format)"),
):
    """Query aligned power usage data from simulation and actual consumption.

    This endpoint reads from:
    - `agg_results.parquet`: Aggregated simulation results
    - `consumption.parquet`: Actual power consumption from workload

    The data is aligned to a common interval and clipped to the shortest timeseries.
    """
    run_id = os.getenv("RUN_ID")
    if not run_id:
        raise HTTPException(status_code=500, detail="RUN_ID environment variable not set")

    if not app.state.config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    try:
        query = PowerDataQuery(run_id=run_id, workload_context=workload())

        result = query.query(interval_seconds=interval_seconds, start_time=start_time)

        logger.debug(f"Power data query successful: {result.metadata['count']} data points")

        return result

    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        logger.error(f"Invalid data: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error querying power data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


@app.get("/api/co2_emission", response_model=CarbonDataResponse)
def get_carbon_emission_data(
    interval_seconds: int = Query(
        60, gt=0, le=3600, description="Sampling interval in seconds (1-3600)"
    ),
    start_time: datetime | None = Query(None, description="Optional start time (ISO 8601 format)"),
):
    """Query carbon emission data from simulation results.

    This endpoint reads from `agg_results.parquet` and calculates carbon emission
    based on power draw and carbon intensity.

    Carbon emission formula: power_draw (W) * carbon_intensity (gCO2/kWh) / 1000 = gCO2/h
    """
    run_id = os.getenv("RUN_ID")
    if not run_id:
        raise HTTPException(status_code=500, detail="RUN_ID environment variable not set")

    try:
        query = CarbonDataQuery(run_id=run_id)

        result = query.query(interval_seconds=interval_seconds, start_time=start_time)

        logger.debug(f"Carbon emission query successful: {result.metadata['count']} data points")

        return result

    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        logger.error(f"Invalid data: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error querying carbon emission data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


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


@app.get("/api/status")
def get_status():
    """The control panel's values, flat: the twin's time and topology, and the runtime settings as configured or
    as sent last."""
    config, calibrator = app.state.config, app.state.config.services.calibrator
    configured = {
        "speed_factor": config.global_config.speed_factor,
        "calibration": config.global_config.calibration_enabled,
        "parallel_simulations": calibrator and calibrator.max_parallel_workers,
        "calibration_min": calibrator and calibrator.min_value,
        "calibration_max": calibrator and calibrator.max_value,
        "calibration_points": calibrator and calibrator.linspace_points,
        "mape_window": calibrator and calibrator.mape_window_minutes,
    }
    configured = {
        key: value for key, value in configured.items() if value is not None
    }  # no calibrator, none
    status = twin.status(twin_run())
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
def get_components(part: Literal[tuple(hosts.PARTS)] | None = None):
    """The CPUs and GPUs the Topology table offers, with their specs."""
    parts = [part] if part else hosts.PARTS
    return {
        "data": [
            {"part": kind, "name": name, **specs}
            for kind in parts
            for name, specs in hosts.PARTS[kind].items()
        ]
    }


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
    publish("sim_topology", app.state.topology, key="datacenter")


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
