# Configuration

OpenDT is configured via YAML files. The default configuration is at `config/default.yaml`.

## Configuration File Structure

```yaml
global:
  speed_factor: 1
  calibration_enabled: false

services:
  dc-mock:
    workload: "SURF"
    heartbeat_frequency_minutes: 1
  
  simulator:
    simulation_frequency_minutes: 5

kafka:
  topics:
    # Topic configurations...
```

## Global Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| speed_factor | float | 1 | Simulation speed multiplier |
| calibration_enabled | bool | false | Enable the calibrator service |

### Speed Factor

Controls how fast the simulation runs relative to real time:

| Value | Behavior |
|-------|----------|
| 1 | Real-time (1 second simulation = 1 second wall clock) |
| 300 | 300x speed (1 hour simulation = 12 seconds wall clock) |
| -1 | Maximum speed (no delays between messages) |

## Service Settings

### dc-mock

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| workload | string | "SURF" | Workload directory name under `workload/` |
| heartbeat_frequency_minutes | int | 1 | Heartbeat interval in simulation time |

### simulator

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| simulation_frequency_minutes | int | 5 | Window size for task aggregation |

## Kafka Topics

Topic configurations are defined under `kafka.topics`. Each topic has a name and optional configuration parameters.

### Topic List

| Key | Default Name | Purpose |
|-----|--------------|---------|
| workload | dc.workload | Task submissions and heartbeats |
| power | dc.power | Power consumption telemetry |
| topology | dc.topology | Real datacenter topology |
| sim_topology | sim.topology | Simulated topology updates |
| results | sim.results | Simulation results |
| system | sys.config | System configuration |

### Topic Configuration

Common configuration options:

| Option | Description |
|--------|-------------|
| retention.ms | How long messages are retained |
| cleanup.policy | "delete" (default) or "compact" |
| min.compaction.lag.ms | Minimum time before compaction |

## Experiment Configurations

Pre-configured experiments are in `config/experiments/`:

### experiment_1.yaml

Power prediction without calibration:
- speed_factor: 300
- calibration_enabled: false
- simulation_frequency_minutes: 60

### experiment_2.yaml

Power prediction with active calibration:
- speed_factor: 300
- calibration_enabled: true
- simulation_frequency_minutes: 60

## Creating Custom Configurations

1. Copy an existing configuration file
2. Modify settings as needed
3. Run with: `make up config=path/to/your/config.yaml`

### Example: Fast Development Run

```yaml
global:
  speed_factor: -1  # Maximum speed
  calibration_enabled: false

services:
  dc-mock:
    workload: "SURF"
    heartbeat_frequency_minutes: 1
  
  simulator:
    simulation_frequency_minutes: 15  # Larger windows = fewer simulations
```

## Environment Variables

Some settings can be overridden via environment variables:

| Variable | Description |
|----------|-------------|
| CONFIG_FILE | Path to configuration file |
| RUN_ID | Current run identifier |
| KAFKA_BOOTSTRAP_SERVERS | Kafka broker address |

## Workload Data

Workload data is stored under `workload/<WORKLOAD_NAME>/`:

```
workload/SURF/
├── tasks.parquet       # Task definitions
├── fragments.parquet   # Task execution profiles
├── consumption.parquet # Actual power measurements
├── carbon.parquet      # Grid carbon intensity
├── topology.json       # Datacenter topology
└── workload.yaml       # Workload metadata
```

To use a custom workload, create a directory with the required files and set `services.dc-mock.workload` to the directory name.
