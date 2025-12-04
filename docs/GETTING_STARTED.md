# Getting Started

This guide covers installation, configuration, and running your first OpenDT simulation.

## Prerequisites

- **Docker & Docker Compose** - Container runtime
- **Make** - Build automation
- **Python 3.11+** - For local development
- **uv** - Python package manager ([install](https://astral.sh/uv))

## Installation

Clone the repository and set up the development environment:

```
git clone https://github.com/your-org/opendt.git
cd opendt
make setup
```

This creates a virtual environment and installs all dependencies.

## Running OpenDT

### Basic Usage

Start all services with the default configuration:

```
make up
```

This will:
1. Initialize a new run with a timestamped ID
2. Start Kafka, the simulator, dc-mock, and supporting services
3. Begin replaying workload data and generating power predictions

### Custom Configuration

Run with a specific configuration file:

```
make up config=config/experiments/experiment_1.yaml
```

### Stopping Services

```
make down
```

## Accessing the System

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | Grafana visualization |
| API | http://localhost:3001 | REST API with OpenAPI docs |
| Kafka | localhost:9092 | Message broker |

## Viewing Logs

```
make logs-simulator    # Simulator service
make logs-dc-mock      # Data replay service
make logs-calibrator   # Calibration service (if enabled)
make logs-dashboard    # API service
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

## Running Experiments

OpenDT includes pre-configured experiments for research purposes.

### Experiment 1: Power Prediction

Predicts power consumption without calibration:

```
make up config=config/experiments/experiment_1.yaml
```

### Experiment 2: Power Prediction with Calibration

Predicts power consumption with active topology calibration:

```
make up config=config/experiments/experiment_2.yaml
```

### Experiment Duration

Duration depends on:
- **Workload length** - The SURF dataset contains ~7 days of data
- **Speed factor** - Configured in the YAML file

With `speed_factor: 300`, a 7-day workload completes in approximately 1 hour.

### Generating Publication Plots

After running an experiment, generate comparison plots:

```
python reproducibility-capsule/generate_plot.py
```

See [Reproducibility Capsule](../reproducibility-capsule/README.md) for details.

## Development

### Activating the Environment

```
source .venv/bin/activate
```

### Running Tests

```
make test
```

### Opening a Container Shell

```
make shell-simulator
make shell-dc-mock
make shell-calibrator
make shell-dashboard
```

## Troubleshooting

### Services not starting

Check Docker is running and ports 3000, 3001, 9092 are available.

### Configuration not found

Ensure the config file path is correct and the file exists.

### Simulation not progressing

Check the simulator logs:

```
make logs-simulator
```

Verify workload data exists in `workload/<WORKLOAD_NAME>/`.

## Next Steps

- [Concepts](CONCEPTS.md) - Understand the data models and system behavior
- [Configuration](CONFIGURATION.md) - Customize OpenDT for your needs
