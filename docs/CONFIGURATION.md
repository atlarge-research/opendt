# Configuration

OpenDT uses a single YAML configuration file that controls all services. Configuration files are stored in the `config/` directory.

## File Location

- **Default:** `config/default.yaml`
- **Experiments:** `config/experiments/experiment_1.yaml`, `config/experiments/experiment_2.yaml`

Run with a specific config:

```
make up config=config/experiments/experiment_1.yaml
```

## Configuration Structure

```yaml
global:
  speed_factor: 1
  calibration_enabled: false

services:
  dc-mock:
    # Service-specific settings
  simulator:
    # Service-specific settings

kafka:
  topics:
    # Topic definitions
```

## Global Settings

The `global:` section contains settings that affect the entire system.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| speed_factor | float | 1 | Simulation speed multiplier |
| calibration_enabled | bool | false | Enable the calibrator service |

### speed_factor

Controls how fast the simulation runs relative to real time:

| Value | Behavior |
|-------|----------|
| 1 | Real-time (1 second simulation = 1 second wall clock) |
| 300 | 300x speed (1 hour simulation = 12 seconds wall clock) |
| -1 | Maximum speed (no delays between messages) |

With the SURF workload (~7 days of data) and `speed_factor: 300`, the simulation completes in approximately 1 hour.

### calibration_enabled

When `true`, the calibrator service starts and actively tunes topology parameters during the simulation run. Requires the `calibration` Docker Compose profile.

## Experiment Configurations

Pre-configured experiments are in `config/experiments/`:

| File | Description |
|------|-------------|
| experiment_1.yaml | Power prediction without calibration (speed_factor: 300) |
| experiment_2.yaml | Power prediction with calibration enabled (speed_factor: 300) |

## Custom Configurations

1. Copy an existing configuration file
2. Modify settings as needed
3. Run with: `make up config=path/to/your/config.yaml`

## Environment Variables

Some settings can be overridden via environment variables:

| Variable | Description |
|----------|-------------|
| CONFIG_FILE | Path to configuration file |
| RUN_ID | Current run identifier |
| KAFKA_BOOTSTRAP_SERVERS | Kafka broker address |
