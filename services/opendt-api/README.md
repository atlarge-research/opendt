# opendt-api Service

The **opendt-api** is a FastAPI backend service that provides REST endpoints for managing the OpenDT system, including topology updates, health checks, and future integration with the frontend dashboard.

## Overview

**Purpose**: HTTP/REST gateway for OpenDT system control  
**Type**: API Server  
**Language**: Python 3.11+  
**Framework**: FastAPI + Uvicorn

## Key Features

- ✅ RESTful API with automatic OpenAPI documentation
- ✅ Topology management (update simulated datacenter via API)
- ✅ Health checks for Kafka and configuration
- ✅ Swagger UI for interactive testing
- ✅ Pydantic validation for request/response bodies
- 🔜 WebSocket streaming for live data
- 🔜 Authentication and authorization

## Architecture

```
┌──────────────────────────────────────────────┐
│              opendt-api                      │
│                                              │
│  ┌─────────────┐         ┌──────────────┐    │
│  │   FastAPI   │────────>│    Kafka     │    │
│  │             │         │   Producer   │    │
│  │  Endpoints: │         └──────────────┘    │
│  │  - /        │                             │
│  │  - /health  │         ┌──────────────┐    │
│  │  - /docs    │────────>│  PostgreSQL  │    │
│  │  - /api/... │         │   Database   │    │
│  └─────────────┘         └──────────────┘    │
│                                              │
│  Topics Published:                           │
│  • sim.topology (Topology updates)           │
└──────────────────────────────────────────────┘
```

## API Endpoints

### Root

**GET /**

Returns service information and version.

**Response**:
```json
{
  "service": "OpenDT API",
  "version": "0.1.0",
  "status": "operational",
  "docs": "/docs"
}
```

---

### Health Check

**GET /health**

Service health status including Kafka connectivity.

**Response**:
```json
{
  "status": "healthy",
  "kafka": "connected",
  "config_loaded": true,
  "timestamp": "2025-11-25T10:30:00"
}
```

---

### API Documentation

**GET /docs**

Interactive Swagger UI for testing endpoints.

**GET /redoc**

Alternative ReDoc documentation interface.

---

### Update Topology

**PUT /api/topology**

Updates the simulated datacenter topology for What-If analysis.

**Request Body** (`application/json`):
```json
{
  "clusters": [
    {
      "name": "A01",
      "hosts": [
        {
          "name": "A01-Host",
          "count": 277,
          "cpu": {
            "coreCount": 16,
            "coreSpeed": 2100
          },
          "memory": {
            "memorySize": 128000000
          },
          "cpuPowerModel": {
            "modelType": "asymptotic",
            "power": 400.0,
            "idlePower": 32.0,
            "maxPower": 180.0,
            "asymUtil": 0.3,
            "dvfs": false
          }
        }
      ]
    }
  ]
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Topology updated and published to sim.topology",
  "cluster_count": 1,
  "total_hosts": 277,
  "topic": "sim.topology"
}
```

**Validation**:
- Pydantic model validates structure
- Returns 422 for invalid topology
- Returns 500 for Kafka errors

**Behavior**:
1. Validates topology against `Topology` Pydantic model
2. Publishes to `sim.topology` Kafka topic (compacted)
3. `sim-worker` consumes update and:
   - Updates simulated topology in memory
   - Clears result cache (forces fresh simulations)
   - Uses new topology for subsequent windows

**Example via cURL**:
```bash
curl -X PUT http://localhost:8000/api/topology \
  -H "Content-Type: application/json" \
  -d @data/SURF/topology.json
```

**Example via Swagger UI**:
1. Navigate to http://localhost:8000/docs
2. Expand `PUT /api/topology`
3. Click "Try it out"
4. Use pre-filled SURF topology example
5. Click "Execute"

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to YAML configuration | `/app/config/simulation.yaml` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://opendt:...` |
| `LOG_LEVEL` | Logging level | `INFO` |

### YAML Configuration

**File**: `config/default.yaml`

```yaml
kafka:
  bootstrap_servers: "kafka:29092"
  topics:
    sim_topology:
      name: "sim.topology"
      config:
        cleanup.policy: "compact"
        min.compaction.lag.ms: "0"
```

## Running

### Via Docker Compose

```bash
# Start all services
make up

# Access API
open http://localhost:8000

# Access Swagger UI
open http://localhost:8000/docs

# View logs
make logs-api
# Or:
docker compose logs -f opendt-api
```

### Standalone (Development)

```bash
cd services/opendt-api
source ../../.venv/bin/activate

# Set environment
export CONFIG_FILE=../../config/default.yaml
export DATABASE_URL=postgresql://opendt:opendt_dev_password@localhost:5432/opendt

# Run with hot reload
uvicorn opendt_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Development

### Project Structure

```
opendt_api/
├── __init__.py
└── main.py              # FastAPI app + endpoints
```

### Adding New Endpoints

1. Define endpoint in `main.py`:
```python
@app.get("/api/my-endpoint")
async def my_endpoint():
    """Endpoint description for OpenAPI."""
    return {"result": "data"}
```

2. Add Pydantic models for validation:
```python
from pydantic import BaseModel

class MyRequest(BaseModel):
    field1: str
    field2: int

@app.post("/api/my-endpoint")
async def my_endpoint(request: MyRequest):
    return {"received": request.field1}
```

3. Test via Swagger UI at http://localhost:8000/docs

### Kafka Integration

```python
from opendt_common.utils import get_kafka_producer
from opendt_common.utils.kafka import send_message

# Get producer
config = load_config_from_env()
producer = get_kafka_producer(config)

# Send message
send_message(
    producer=producer,
    topic="sim.topology",
    message=topology.model_dump(mode="json"),
    key="datacenter"
)
```

### Error Handling

```python
from fastapi import HTTPException

try:
    # Operation
    pass
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
except Exception as e:
    raise HTTPException(status_code=500, detail="Internal server error") from e
```

## Testing

### Interactive Testing (Swagger UI)

1. Start services: `make up`
2. Navigate to: http://localhost:8000/docs
3. Test endpoints with interactive forms

### Automated Testing

```bash
cd services/opendt-api
pytest

# With coverage
pytest --cov=opendt_api --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Manual Testing (cURL)

```bash
# Health check
curl http://localhost:8000/health

# Update topology
curl -X PUT http://localhost:8000/api/topology \
  -H "Content-Type: application/json" \
  -d '{"clusters": [...]}'

# Get API docs (JSON)
curl http://localhost:8000/openapi.json
```

## Monitoring

### Logs

```bash
# Tail logs
docker compose logs -f opendt-api

# Expected output:
# INFO - Starting OpenDT API...
# INFO - Config loaded from /app/config/simulation.yaml
# INFO - Kafka producer initialized
# INFO - Uvicorn running on http://0.0.0.0:8000
```

### Health Endpoint

```bash
# Check health
curl http://localhost:8000/health

# Healthy response:
{
  "status": "healthy",
  "kafka": "connected",
  "config_loaded": true
}

# Unhealthy response:
{
  "status": "unhealthy",
  "kafka": "error",
  "error": "Failed to connect to Kafka"
}
```

## Troubleshooting

### Issue: "Failed to connect to Kafka"

**Cause**: Kafka not running or unreachable

**Solution**:
```bash
# Check Kafka status
docker compose ps kafka

# Restart Kafka
docker compose restart kafka

# Wait for Kafka to be healthy
docker compose logs kafka | grep "started"

# Restart API
docker compose restart opendt-api
```

### Issue: "Configuration file not found"

**Cause**: `CONFIG_FILE` path incorrect

**Solution**:
```bash
# Check mounted volume in docker-compose.yml
docker compose exec opendt-api ls -la /app/config/

# Verify CONFIG_FILE environment variable
docker compose exec opendt-api env | grep CONFIG_FILE
```

### Issue: "422 Validation Error" on /api/topology

**Cause**: Invalid topology structure

**Solution**:
1. Review error response for specific validation failures
2. Compare with example topology in Swagger UI
3. Validate JSON structure matches [Topology model](../../docs/DATA_MODELS.md#topology-models)
4. Ensure all required fields present (coreCount, coreSpeed, etc.)

## Future Roadmap

### Planned Endpoints

- `GET /api/workloads` - List available workload datasets
- `GET /api/experiments` - List experiment runs
- `POST /api/experiments` - Start new experiment
- `GET /api/experiments/{name}/results` - Download results
- `GET /api/simulations/status` - Current simulation status
- `POST /api/simulations/pause` - Pause simulation
- `POST /api/simulations/resume` - Resume simulation

### Planned Features

- WebSocket streaming for live power consumption updates
- Experiment management (create, list, download results)
- Topology validation and preview (simulate without running)
- Historical query API for past simulation results
- User authentication and multi-tenancy

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md) - System design
- [Data Models](../../docs/DATA_MODELS.md) - Topology schema
- [Simulation Worker](../sim-worker/README.md) - Consumer of topology updates
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Framework reference
