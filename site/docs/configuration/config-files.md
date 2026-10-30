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

The tutorial's live twin has its own configurations in `tutorial/resources/configs/`.

## Using a Configuration

```bash
make up config=config/experiments/experiment_1.yaml
```

If no config is specified, `config/default.yaml` is used.

## File Structure

```yaml
global:
  speed_factor: -1
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

Required: `services.dc-mock.workload` and `services.simulator.background_load_nodes`; the services also need the
`kafka.topics` keys (see [kafka](/docs/services/kafka)). An optional `services.calibrator` section configures the
[calibrator](/docs/services/calibrator).

## Creating Custom Configurations

1. Copy an existing configuration file
2. Modify settings as needed
3. Run with: `make up config=path/to/your/config.yaml`
