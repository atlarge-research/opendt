---
sidebar_position: 3
---

# calibrator

Optimizes topology parameters by comparing simulation output against actual power measurements.

## How It Works

The calibrator runs grid searches, one after another, and publishes the best-performing topology for the simulator:

1. **Accumulate** - Collect tasks from `dc.workload` and actual power from `dc.power`
2. **Grid search** - One OpenDC run per value: `linspace_points` values from `min_value` to `max_value`, rounded to 2
   decimals, each on all tasks so far
3. **Compare** - Calculate MAPE against actual power, over the last `mape_window_minutes`, on a 60-s grid
4. **Select** - Choose the value with the lowest error
5. **Publish** - Send the calibrated topology to `sim.topology`, when the best value changes

The runs go in threads, each OpenDC run in its own JVM; each takes about 1.3 GB and times out after 120 s.

## Calibrated Property

The calibrator sets one numeric parameter, by its path from the host, on all hosts:

| Property | Path | Description |
|----------|------|-------------|
| calibrationFactor | cpuPowerModel.calibrationFactor | Exponent r of the MSE power model; the one for SURF's hosts |
| asymUtil | cpuPowerModel.asymUtil | Curve coefficient of the asymptotic power model |

The default, `cpuPowerModel.calibrationFactor`, is the r of the MSE hosts (as SURF's); `cpuPowerModel.asymUtil` exists
only in the asymptotic model.

## Configuration

The calibrator runs when the config file has a `services.calibrator` section. `global.calibration_enabled` sets whether
it calibrates from the start; the control panel switches it on and off, and changes all settings but the property,
while the twin runs. From `config/experiments/experiment_2.yaml`:

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
| calibrated_property | cpuPowerModel.calibrationFactor | Path of the parameter to calibrate |
| min_value | 3 | Lowest value to test |
| max_value | 9 | Highest value to test |
| linspace_points | 7 | Number of values to test |
| max_parallel_workers | 4 | Parallel OpenDC runs |
| mape_window_minutes | 1440 | Minutes of power the MAPE is computed over |

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
