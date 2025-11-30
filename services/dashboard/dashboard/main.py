"""OpenDT Dashboard - Main FastAPI Application."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from odt_common import load_config_from_env
from odt_common.models.topology import CPU, Cluster, CPUPowerModel, Host, Memory, Topology
from odt_common.utils import get_kafka_producer
from odt_common.utils.kafka import send_message

from dashboard.power_query import PowerDataQuery, PowerDataResponse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Setup paths for static files and templates
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Initialize templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting OpenDT Dashboard service...")

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

    yield

    # Shutdown
    logger.info("Shutting down OpenDT Dashboard service...")
    if app.state.kafka_producer:
        app.state.kafka_producer.close()
        logger.info("Kafka producer closed")


# Create FastAPI application
app = FastAPI(
    title="OpenDT Dashboard",
    description="Open Digital Twin - Web Dashboard and API for datacenter simulation",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # Dashboard URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# DASHBOARD
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the OpenDT dashboard UI."""
    return templates.TemplateResponse("index.html", {"request": request})


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
            name="A01",
            hosts=[
                Host(
                    name="A01",
                    count=277,
                    cpu=CPU(coreCount=16, coreSpeed=2100.0),
                    memory=Memory(memorySize=128000000),  # ~128 MB
                    cpuPowerModel=CPUPowerModel(
                        modelType="asymptotic",
                        power=400.0,
                        idlePower=32.0,
                        maxPower=180.0,
                        asymUtil=0.3,
                        dvfs=False,
                    ),
                )
            ],
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
    start_time: datetime | None = Query(
        None, description="Optional start time (ISO 8601 format)"
    ),
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
        raise HTTPException(
            status_code=500, detail="RUN_ID environment variable not set"
        )

    # Get workload context from config
    if not app.state.config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    try:
        # Get workload context with resolved paths
        workload_dir = Path(os.getenv("WORKLOAD_DIR", "/app/workload"))
        workload_context = app.state.config.get_workload_context(base_path=workload_dir)

        # Initialize query
        query = PowerDataQuery(run_id=run_id, workload_context=workload_context)

        # Execute query
        result = query.query(interval_seconds=interval_seconds, start_time=start_time)

        logger.info(
            f"Power data query successful: {result.metadata['count']} data points"
        )

        return result

    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.error(f"Invalid data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error querying power data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
