# dashboard Service

The **dashboard** service provides a web-based user interface and REST API for the OpenDT system. It combines real-time visualization with programmatic control through FastAPI endpoints.


## Architecture

```
┌──────────────────────────────────────────────┐
│              dashboard                       │
│                                              │
│  ┌─────────────┐         ┌──────────────┐    │
│  │   FastAPI   │────────>│    Kafka     │    │
│  │             │         │   Producer   │    │
│  │  Routes:    │         └──────────────┘    │
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

## Web Dashboard

### Accessing the Dashboard

Once services are running, access the dashboard at:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Dashboard Features

The web UI provides:
- Real-time metrics display
- System status monitoring
- Interactive controls
- Power consumption charts (via Plotly.js)
- Topology visualization

**Note**: The dashboard JavaScript polls API endpoints that are not yet fully implemented. Some features may show as unavailable until backend endpoints are added.

## API Endpoints

### Root

**GET /**

Serves the web dashboard UI.

**Response**: HTML page with dashboard interface

---

### Health Check

**GET /health**

Service health status including Kafka connectivity.

**Response**:
```json
{
  "status": "healthy",
  "kafka": "connected",
  "config": "loaded"
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
  "status": "updated",
  "message": "Topology published to sim.topology",
  "clusters": 1,
  "total_hosts": 277,
  "total_cores": 4432,
  "topic": "sim.topology"
}
```

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

# Access dashboard
open http://localhost:8000

# View logs
make logs-dashboard
# Or:
docker compose logs -f dashboard
```

### Standalone (Development)

```bash
cd services/dashboard
source ../../.venv/bin/activate

# Set environment
export CONFIG_FILE=../../config/default.yaml
export DATABASE_URL=postgresql://opendt:opendt_dev_password@localhost:5432/opendt

# Run with hot reload
uvicorn dashboard.main:app --reload --host 0.0.0.0 --port 8000
```

## Development

### Project Structure

```
dashboard/
├── __init__.py
├── main.py              # FastAPI app + routes
├── static/              # Dashboard assets
│   ├── js/
│   │   ├── charts.js
│   │   ├── polling.js
│   │   ├── ui.js
│   │   └── ...
│   └── style.css
└── templates/
    └── index.html       # Dashboard HTML
```

### Adding API Endpoints

Define new endpoints in `main.py`:

```python
@app.get("/api/my-endpoint")
async def my_endpoint():
    """Endpoint description for OpenAPI."""
    return {"result": "data"}
```

### Testing

```bash
# Interactive testing via Swagger UI
open http://localhost:8000/docs

# Manual testing via cURL
curl http://localhost:8000/health
```

## Static Assets

The dashboard serves static files from `services/dashboard/static/`:
- **JavaScript**: Charts, polling, UI interactions
- **CSS**: Dashboard styling
- **HTML**: Single-page application template

Files are mounted at `/static` route and referenced in the HTML template.

## Monitoring

### Logs

```bash
# Tail logs
docker compose logs -f dashboard

# Expected output:
# INFO - Starting OpenDT Dashboard service...
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
  "config": "loaded"
}
```

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md) - System design
- [Data Models](../../docs/DATA_MODELS.md) - Topology schema
- [Simulation Worker](../sim-worker/README.md) - Consumer of topology updates
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Framework reference

---

For questions or contributions, see the [Contributing Guide](../../CONTRIBUTING.md).
