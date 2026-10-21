---
sidebar_position: 3
---

# calibrator

Optimizes topology parameters by comparing simulation output against actual power measurements.

## Purpose

The calibrator performs grid search over a topology parameter to find the value that minimizes the error between predicted and actual power consumption. It publishes the best-performing topology to Kafka for use by the simulator.

## How It Works

1. **Accumulate tasks** - Collect tasks from `dc.workload`
2. **Track power** - Record actual power from `dc.power`
3. **Grid search** - Run parallel simulations, one per value (`linspace_points` values from `min_value` to `max_value`, rounded to 2 decimals), each with all tasks so far
4. **Compare** - Calculate MAPE against actual power, over the last `mape_window_minutes`, on a 60-s grid
5. **Select** - Choose the parameter value with lowest error
6. **Publish** - Send the calibrated topology to `sim.topology`, only when the best value changes

Grid searches run one after another. The simulations run in threads, each OpenDC run in its own JVM, with a timeout of
120 s.

## Calibrated Properties

The calibrator tunes one numeric parameter of the hosts, by its path from the host, on all hosts:

| Property | Path | Description |
|----------|------|-------------|
| asymUtil | cpuPowerModel.asymUtil | Asymptotic utilization coefficient (asymptotic power model only) |
| calibrationFactor | cpuPowerModel.calibrationFactor | Exponent r of the MSE power model; the one for SURF's hosts |

## Components

| File | Purpose |
|------|---------|
| main.py | Service orchestration |
| calibration_engine.py | Parallel OpenDC simulations |
| mape_comparator.py | Error calculation |
| power_tracker.py | Actual power tracking |
| result_processor.py | Results and topology broadcasts |
| topology_manager.py | Topology subscription and publishing |

## Configuration

The calibrator runs when the config file has a `services.calibrator` section, for example from
`config/experiments/experiment_2.yaml`:

```yaml
global:
  calibration_enabled: true

services:
  calibrator:
    calibrated_property: "cpuPowerModel.calibrationFactor"
    min_value: 3
    max_value: 9
    linspace_points: 10
    max_parallel_workers: 4
    mape_window_minutes: 60
```

| Setting | Default | Description |
|---------|---------|-------------|
| calibrated_property | cpuPowerModel.asymUtil | Path of the parameter to calibrate |
| min_value | 0.1 | Lowest value to test |
| max_value | 0.9 | Highest value to test |
| linspace_points | 9 | Number of values to test |
| max_parallel_workers | 4 | Parallel OpenDC simulations |
| mape_window_minutes | 1440 | Minutes of power the MAPE is computed over |

`global.calibration_enabled` sets whether the calibrator calibrates from the start. The control panel switches calibration
on and off, and changes all settings but the property, while the twin runs.

## Output

Results are written to `data/<RUN_ID>/calibrator/`:

```
calibrator/
├── agg_results.parquet
└── opendc/
    └── run_<N>/
        ├── sim_<i>/
        └── metadata.json
```

## Logs

```bash
make logs-calibrator
```
