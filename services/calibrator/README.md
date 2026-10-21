# calibrator

Optimizes topology parameters by comparing simulation output against actual power measurements.

## Purpose

The calibrator performs grid search over a topology parameter (e.g., `calibrationFactor`, the exponent r of SURF's power model) to find values that minimize the error between predicted and actual power consumption. It publishes the best-performing topology to Kafka for use by the simulator.

## How It Works

1. **Accumulate tasks** - Collect all tasks so far from `dc.workload`
2. **Track power** - Record actual power consumption from `dc.power`
3. **Grid search** - Run parallel simulations with different parameter values
4. **Compare** - Calculate MAPE against actual power for each simulation
5. **Select** - Choose the parameter value with lowest error
6. **Publish** - Send calibrated topology to `sim.topology`

## Calibrated Properties

The calibrator sets one numeric parameter, by its path from the host, on all hosts:

| Property | Path | Description |
|----------|------|-------------|
| calibrationFactor | cpuPowerModel.calibrationFactor | Exponent r of the MSE power model; the one for SURF's hosts |
| asymUtil | cpuPowerModel.asymUtil | Asymptotic utilization coefficient (asymptotic model only) |

## Components

| File | Purpose |
|------|---------|
| main.py | Service orchestration |
| calibration_engine.py | Parallel OpenDC simulations |
| mape_comparator.py | Error calculation |
| power_tracker.py | Actual power tracking |
| topology_manager.py | Topology subscription and publishing |
| result_processor.py | Results aggregation |

## Configuration

The calibrator runs when the config file has a `services.calibrator` section; `calibration_enabled` sets whether it
calibrates from the start:

```yaml
global:
  calibration_enabled: true
```

The control panel switches calibration on and off, and changes all settings but the property, while the twin runs.

Settings under `services.calibrator` in the config file:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| calibrated_property | string | cpuPowerModel.asymUtil | Topology property path to calibrate (`cpuPowerModel.calibrationFactor` for SURF's MSE hosts) |
| min_value | float | 0.1 | Minimum value in the search space |
| max_value | float | 0.9 | Maximum value in the search space |
| linspace_points | int | 9 | Number of candidate values to evaluate |
| max_parallel_workers | int | 4 | Maximum parallel calibration simulations |
| mape_window_minutes | int | 1440 | Time window for MAPE calculation |

### calibrated_property

A dot path from the host (e.g., `cpuPowerModel.calibrationFactor`). The default, `cpuPowerModel.asymUtil`, exists only
in the asymptotic model.

### linspace_points

Creates evenly-spaced values between `min_value` and `max_value`. Higher values improve accuracy but increase calibration time.

### max_parallel_workers

Controls parallelism during calibration. Set based on available CPU cores.

## Output

Results are written to `data/<RUN_ID>/calibrator/`:

```
calibrator/
├── agg_results.parquet   # Calibration metadata and MAPE values
└── opendc/
    └── run_<N>/          # Simulation archives for each calibration run
```

## Logs

```
make logs-calibrator
```

Note: the calibrator runs with the `calibration` Docker Compose profile, when the config has a `services.calibrator`
section.
