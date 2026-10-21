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

The tutorial's live twin has its own configurations in `tutorial/resources/configs/` (`live_twin.yaml`,
`live_twin_calibration.yaml`).

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
    background_load_nodes: 0

kafka:
  topics:
    workload:
      name: "dc.workload"
    power:
      name: "dc.power"
    # ...
```

`services.simulator.background_load_nodes` is required. An optional `services.calibrator` section configures the
[calibrator](/docs/services/calibrator). The services look the Kafka topics up by their keys (`workload`, `power`,
`topology`, `system`, `sim_topology`), so only their `name` may change; Kafka does not create topics on its own.

## Creating Custom Configurations

1. Copy an existing configuration file
2. Modify settings as needed
3. Run with: `make up config=path/to/your/config.yaml`

## Environment Variables

The services read these environment variables, set by `docker-compose.yml` and `make up`:

| Variable | Description |
|----------|-------------|
| CONFIG_FILE | Path to configuration file |
| RUN_ID | Current run identifier |
| KAFKA_BOOTSTRAP_SERVERS | Kafka broker address (`kafka:29092` in the containers) |
| WORKLOAD_DIR | Workload folder in the container (`/app/workload`) |
| DATA_DIR | Run outputs in the container (`/app/data`) |
