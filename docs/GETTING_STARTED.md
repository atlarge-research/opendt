# Getting Started

This guide covers installation and running OpenDT.

## Prerequisites

- **Docker & Docker Compose** - Container runtime
- **Make** - Build automation
- **Python 3.11+** - For local development
- **uv** - Python package manager ([install](https://astral.sh/uv))

## Installation

Clone the repository and set up the development environment:

```
git clone https://github.com/atlarge-research/opendt.git
cd opendt
make setup
```

This creates a virtual environment and installs all dependencies.

## Running OpenDT

Start all services with the default configuration:

```
make up
```

This will:
1. Initialize a new run with a timestamped ID
2. Start Kafka, the simulator, dc-mock, and supporting services
3. Begin replaying workload data and generating power predictions

Run with a specific configuration file:

```
make up config=config/experiments/experiment_1.yaml
```

Stop services:

```
make down
```

## Accessing the System

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | Grafana visualization |
| API | http://localhost:3001 | REST API with OpenAPI docs |

## Viewing Logs

```
make logs-simulator
make logs-dc-mock
make logs-calibrator
make logs-api
```

## Run Output

Each run creates a timestamped directory under `data/`:

```
data/2024_01_15_10_30_00/
├── config.yaml           # Copy of configuration used
├── metadata.json         # Run metadata
├── .env                  # Environment variables
└── simulator/
    ├── agg_results.parquet   # Aggregated simulation results
    └── opendc/               # OpenDC simulation archives
```

## Development

Activate the environment:

```
source .venv/bin/activate
```

Run tests:

```
make test
```

Open a container shell:

```
make shell-simulator
make shell-dc-mock
make shell-calibrator
make shell-api
```
