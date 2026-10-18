"""OpenDT API - FastAPI Application for datacenter simulation data."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
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

from api import levers, twin
from api.carbon_query import CarbonDataQuery, CarbonDataResponse
from api.power_query import PowerDataQuery, PowerDataResponse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting OpenDT API service...")

    # Load configuration
    try:
        app.state.config = load_config_from_env()
        logger.info(f"Configuration loaded for workload: {app.state.config.workload}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        app.state.config = None

    # Initialize Kafka producer (stored in app state for reuse)
    try:
        app.state.kafka_producer = get_kafka_producer()
        logger.info("Kafka producer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Kafka producer: {e}")
        app.state.kafka_producer = None

    app.state.settings = {}  # the runtime settings the control panel sent; until then, the configured ones
    app.state.topology = None  # the simulated topology sent last
    yield

    # Shutdown
    logger.info("Shutting down OpenDT API service...")
    if app.state.kafka_producer:
        app.state.kafka_producer.close()
        logger.info("Kafka producer closed")


# Create FastAPI application
app = FastAPI(
    title="OpenDT API",
    description="Open Digital Twin - REST API for datacenter simulation",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for API access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ROOT REDIRECT
# ============================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return RedirectResponse(url="/docs")


# ============================================================================
# API ENDPOINTS
# ============================================================================


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


# ============================================================================
# TOPOLOGY MANAGEMENT
# ============================================================================


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
    """Update the simulated datacenter topology.

    This endpoint validates the topology structure and publishes it to Kafka.
    The simulator will pick it up and use it for future simulations.

    Args:
        topology: Datacenter topology configuration with cluster details

    Returns:
        Success confirmation with topology details

    Raises:
        HTTPException: 500 if Kafka producer is not available
        HTTPException: 500 if publishing to Kafka fails
    """
    # Check if Kafka producer is available
    if not app.state.kafka_producer:
        logger.error("Kafka producer not initialized")
        raise HTTPException(status_code=500, detail="Kafka producer not available")

    # Check if config is loaded (to get topic name)
    if not app.state.config:
        logger.error("Configuration not loaded")
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    # Topology already validated by Pydantic
    logger.info(f"Topology validated: {len(topology.clusters)} cluster(s)")

    # Get sim.topology topic name from config
    sim_topology_topic = app.state.config.kafka.topics.get("sim_topology")
    if not sim_topology_topic:
        logger.error("sim.topology topic not configured")
        raise HTTPException(status_code=500, detail="sim.topology topic not configured")

    topic_name = sim_topology_topic.name

    # Publish to sim.topology Kafka topic with compacted key
    try:
        send_message(
            producer=app.state.kafka_producer,
            topic=topic_name,
            message=topology.model_dump(mode="json"),
            key="datacenter",
        )
        app.state.topology = topology.model_dump(mode="json")
        logger.info(f"Topology published to {topic_name}")
    except Exception as e:
        logger.error(f"Failed to publish topology to Kafka: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish topology: {e}") from e

    return {
        "status": "updated",
        "message": f"Topology published to {topic_name}",
        "clusters": len(topology.clusters),
        "total_hosts": topology.total_host_count(),
        "total_cores": topology.total_core_count(),
        "topic": topic_name,
    }


# ============================================================================
# POWER DATA QUERY
# ============================================================================


@app.get("/api/power", response_model=PowerDataResponse)
async def get_power_data(
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

    Args:
        interval_seconds: Sampling interval in seconds (default: 60)
        start_time: Optional start time filter (ISO 8601 format)

    Returns:
        PowerDataResponse with aligned timeseries data

    Raises:
        HTTPException: If data files are not found or cannot be processed
    """
    # Get run ID from environment
    run_id = os.getenv("RUN_ID")
    if not run_id:
        raise HTTPException(status_code=500, detail="RUN_ID environment variable not set")

    # Get workload context from config
    if not app.state.config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    try:
        query = PowerDataQuery(run_id=run_id, workload_context=workload())

        # Execute query
        result = query.query(interval_seconds=interval_seconds, start_time=start_time)

        logger.info(f"Power data query successful: {result.metadata['count']} data points")

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


# ============================================================================
# CARBON EMISSION DATA QUERY
# ============================================================================


@app.get("/api/co2_emission", response_model=CarbonDataResponse)
async def get_carbon_emission_data(
    interval_seconds: int = Query(
        60, gt=0, le=3600, description="Sampling interval in seconds (1-3600)"
    ),
    start_time: datetime | None = Query(None, description="Optional start time (ISO 8601 format)"),
):
    """Query carbon emission data from simulation results.

    This endpoint reads from `agg_results.parquet` and calculates carbon emission
    based on power draw and carbon intensity.

    Carbon emission formula: power_draw (W) * carbon_intensity (gCO2/kWh) / 1000 = gCO2/h

    Args:
        interval_seconds: Sampling interval in seconds (default: 60)
        start_time: Optional start time filter (ISO 8601 format)

    Returns:
        CarbonDataResponse with carbon emission timeseries data

    Raises:
        HTTPException: If data files are not found or cannot be processed
    """
    # Get run ID from environment
    run_id = os.getenv("RUN_ID")
    if not run_id:
        raise HTTPException(status_code=500, detail="RUN_ID environment variable not set")

    try:
        # Initialize query
        query = CarbonDataQuery(run_id=run_id)

        # Execute query
        result = query.query(interval_seconds=interval_seconds, start_time=start_time)

        logger.info(f"Carbon emission query successful: {result.metadata['count']} data points")

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


# ============================================================================
# DASHBOARD: STATUS, CLUSTER, CONTROL PANEL
# ============================================================================


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


def publish(topic: str, message: dict, key: str | None = None) -> None:
    """Send a message to one of OpenDT's Kafka topics, by its name in the configuration."""
    if not app.state.kafka_producer or not app.state.config:
        raise HTTPException(status_code=500, detail="Kafka producer or configuration not available")
    name = app.state.config.kafka.topics[topic].name
    send_message(producer=app.state.kafka_producer, topic=name, message=message, key=key)


@app.get("/api/status")
def get_status():
    """The twin's time, topology, and replay speed: the control panel's current values (a flat object)."""
    status = twin.status(twin_run())
    sent, config = app.state.settings, app.state.config
    speed = sent.get("global.speed_factor", config.global_config.speed_factor)
    calibrator = config.services.calibrator
    parallel = sent.get(
        "calibrator.max_parallel_workers", calibrator and calibrator.max_parallel_workers
    )
    return {
        **status,
        "twin_time": status["twin_time"].isoformat(),
        "speed_factor": speed,
        "parallel_simulations": parallel,
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
    CO2 per sample; with `points`, every so many samples, about that many in all."""

    def cut(run: Path) -> pd.DataFrame:
        cluster = twin.cluster(run).set_index("timestamp")[start:end].reset_index()
        return cluster.iloc[:: max(1, len(cluster) // points)] if points else cluster

    return rows(cut)


@app.get("/api/totals")
def get_totals(period: Literal["minute", "hour", "day", "week", "month", "year"] = "day"):
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
    return rows(twin.events if markers == "on" else lambda run: twin.events(run).iloc[:0])


@app.get("/api/arrivals")
def get_arrivals():
    """Jobs submitted per hour so far."""
    return rows(twin.arrivals)


@app.get("/api/servers")
def get_servers():
    """The server groups the twin runs now, with their specs."""
    return rows(twin.server_groups)


@app.get("/api/server_kinds")
def get_server_kinds():
    """The kinds of servers the control panel offers, with their specs."""
    kinds = pd.DataFrame(
        {"id": name, **twin.specs({"name": name, **spec})} for name, spec in twin.SERVERS.items()
    )
    return Response(f'{{"data": {kinds.to_json(orient="records")}}}', media_type="application/json")


@app.get("/api/accuracy")
def get_accuracy(minutes: int = Query(60, ge=1, le=1440)):
    """Per period (an hour; 5 minutes for the MAPE now): the MAPE [%] and the mean error [kW] of OpenDT's power vs.
    the measured power, and the r the twin ran with."""

    def per_period(run: Path) -> pd.DataFrame:
        query = PowerDataQuery(run_id=run.name, workload_context=workload())
        power = query.query(interval_seconds=300)
        return twin.accuracy(
            run, pd.DataFrame([point.model_dump() for point in power.data]), minutes
        )

    return rows(per_period)


def configure(setting: str, value) -> None:
    """A runtime setting of the twin's services, on the compacted sys.config topic, keyed by the setting."""
    event = DynamicConfigEvent(
        setting_key=setting, new_value=value, timestamp=datetime.now(UTC).isoformat(), source="api"
    )
    publish("system", event.model_dump(), key=setting)


@app.patch("/api/control")
def control(change: levers.Control):
    """Change the running twin: hosts and CO2 zone as a new simulated topology, the scheduler, the replay
    speed, and the calibrator's parallel simulations as runtime settings."""
    if levers.moves_topology(change):
        latest = twin.topology(twin.windows(twin_run())[-1])
        try:
            app.state.topology = levers.topology(change, app.state.topology, latest)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        publish("sim_topology", app.state.topology, key="datacenter")
    for setting, value in levers.settings(change).items():
        configure(setting, value)
        app.state.settings[setting] = value
    return get_status()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
