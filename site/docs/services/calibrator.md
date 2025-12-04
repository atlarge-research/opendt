---
sidebar_position: 3
---

# calibrator

Optimizes topology parameters by comparing simulation output against actual power measurements.

## Purpose

The calibrator performs grid search over topology parameters to find values that minimize the error between predicted and actual power consumption. It publishes the best-performing topology to Kafka for use by the simulator.

## How It Works

1. **Accumulate tasks** - Collect tasks from `dc.workload`
2. **Track power** - Record actual power from `dc.power`
3. **Grid search** - Run parallel simulations with different parameter values
4. **Compare** - Calculate MAPE against actual power
5. **Select** - Choose the parameter value with lowest error
6. **Publish** - Send calibrated topology to `sim.topology`

## Calibrated Properties

The calibrator can tune any numeric topology parameter. Common targets:

| Property | Path | Description |
|----------|------|-------------|
| asymUtil | cpuPowerModel.asymUtil | Asymptotic utilization coefficient |
| calibrationFactor | cpuPowerModel.calibrationFactor | MSE model scaling factor |

## Components

| File | Purpose |
|------|---------|
| main.py | Service orchestration |
| calibration_engine.py | Parallel OpenDC simulations |
| mape_comparator.py | Error calculation |
| power_tracker.py | Actual power tracking |
| topology_manager.py | Topology subscription and publishing |

## Configuration

Enable calibration in your config file:

```yaml
global:
  calibration_enabled: true
```

The calibrator only runs when this flag is set.

## Output

Results are written to `data/<RUN_ID>/calibrator/`:

```
calibrator/
├── agg_results.parquet
└── opendc/
    └── run_<N>/
```

## Logs

```bash
make logs-calibrator
```
