# OpenDT - Open Digital Twin for Datacenters

**OpenDT** is a distributed system for real-time datacenter simulation and What-If analysis. It operates in "Shadow Mode" by replaying historical workload data through the OpenDC simulator to compare predicted vs. actual power consumption.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

## Quick Start

### Prerequisites

- **Docker & Docker Compose** - Container orchestration
- **Make** - Convenience commands
- **Python 3.11+** - For local development
- **uv** - Python package manager ([install](https://astral.sh/uv/install))

### Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/opendt.git
cd opendt

# 2. Setup environment
make setup

# 3. Start services
make up

# 4. Access services
open http://localhost:8000  # Dashboard
```

That's it! The system is now running with the SURF workload dataset.

### Running an Experiment

```bash
# Run experiment with custom config
make experiment name=baseline

# View results
ls output/baseline/run_1/
# - results.parquet    (power predictions)
# - power_plot.png     (actual vs simulated)
# - opendc/            (simulation archives)
```

## Documentation

### Getting Started

- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design, services, and data flow
- **[Data Models](docs/DATA_MODELS.md)** - Pydantic models and data schemas

### Service Documentation

- **[dc-mock](services/dc-mock/README.md)** - Data producer (workload replay)
- **[sim-worker](services/sim-worker/README.md)** - Simulation engine (OpenDC integration)
- **[dashboard](services/dashboard/README.md)** - Web dashboard and REST API
- **[kafka-init](services/kafka-init/README.md)** - Kafka infrastructure setup

## Architecture

```
┌──────────────┐     ┌────────────────────────────────────┐
│   dc-mock    │────>│            Kafka Bus               │
│  (Producer)  │     │  ┌──────────────────────────────┐  │
│              │     │  │ Topics:                      │  │
│ Reads:       │     │  │  • dc.workload (tasks)       │  │
│  - tasks     │     │  │  • dc.power (telemetry)      │  │
│  - fragments │     │  │  • dc.topology (real)        │  │
│  - power     │     │  │  • sim.topology (simulated)  │  │
│  - topology  │     │  │  • sim.results (predictions) │  │
└──────────────┘     │  └──────────────────────────────┘  │
                     └───────┬────────────────────────────┘
                             │
                   ┌─────────┴─────────────┐
                   │                       │
          ┌────────▼──────┐     ┌──────────▼───────┐
          │  sim-worker   │     │   dashboard      │
          │  (Consumer)   │     │   (FastAPI)      │
          │               │     │                  │
          │ • Windows     │     │ • Web UI         │
          │ • OpenDC      │     │ • REST API       │
          │ • Caching     │◀────│ • Topology Mgmt  │
          │ • Experiments │     │                  │
          └───────┬───────┘     └─────────┬────────┘
                  │                       │
                  │              ┌────────▼────────┐
                  │              │   PostgreSQL    │
                  │              │   (TimescaleDB) │
                  │              └─────────────────┘
                  │
          ┌───────▼───────┐
          │ Experiment    │
          │ Output:       │
          │  • Parquet    │
          │  • Plots      │
          │  • Archives   │
          └───────────────┘
```

See [Architecture Overview](docs/ARCHITECTURE.md) for detailed explanation.

## Available Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `make up` | Start with clean slate (deletes volumes) |
| `make up-debug` | Start in debug mode (local file output) |
| `make down` | Stop all services |
| `make logs` | View all logs |
| `make ps` | Show running containers |

### Experiment Commands

| Command | Description |
|---------|-------------|
| `make experiment name=X` | Run experiment X |
| `make experiment-debug name=X` | Run experiment X with debug output |
| `make experiment-down` | Stop experiment |

### Development Commands

| Command | Description |
|---------|-------------|
| `make setup` | Setup virtual environment |
| `make test` | Run all tests |
| `make shell-dashboard` | Open shell in dashboard container |
| `make kafka-topics` | List Kafka topics |

### Monitoring Commands

| Command | Description |
|---------|-------------|
| `make logs-dc-mock` | View dc-mock logs |
| `make logs-sim-worker` | View sim-worker logs |
| `make logs-dashboard` | View dashboard logs |

Run `make help` to see all available commands.

## Configuration

### Basic Configuration

**File**: `config/default.yaml`

```yaml
workload: "SURF"  # Data directory name

simulation:
  speed_factor: 300           # 300x real-time
  window_size_minutes: 5      # 5-minute windows
  heartbeat_frequency_minutes: 1
  experiment_mode: false

kafka:
  bootstrap_servers: "kafka:29092"
```

### Experiment Configuration

**File**: `config/experiments/my_experiment.yaml`

```yaml
workload: "SURF"

simulation:
  speed_factor: 300
  window_size_minutes: 15  # Longer windows for experiments
  experiment_mode: true    # Enable experiment mode
```

## System Components

### Services

- **dc-mock**: Replays historical workload/power data to Kafka
- **sim-worker**: Consumes streams, invokes OpenDC simulator
- **dashboard**: Web dashboard with REST API for system control and visualization

### Infrastructure

- **Kafka**: Message broker (KRaft mode, no Zookeeper)
- **PostgreSQL**: Database for persistent storage
- **OpenDC**: Java-based datacenter simulator (bundled)

### Shared Libraries

- **opendt-common**: Pydantic models, configuration, Kafka utilities
