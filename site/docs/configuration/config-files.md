---
sidebar_position: 1
---

# Configuration Files

OpenDT uses a single YAML configuration file that controls all services.

## File Location

Configuration files are stored in the `config/` directory:

```
config/
├── default.yaml           # Default configuration
└── experiments/
    ├── experiment_1.yaml  # Without calibration
    └── experiment_2.yaml  # With calibration
```

## Using a Configuration

Specify a config file when starting OpenDT:

```bash
make up config=config/experiments/experiment_1.yaml
```

If no config is specified, `config/default.yaml` is used.

## File Structure

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
    workload:
      name: "dc.workload"
    power:
      name: "dc.power"
    # ...
```

## Creating Custom Configurations

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
