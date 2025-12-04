# calibrator

Optimizes topology parameters by comparing simulation output against actual power measurements.

## Purpose

The calibrator performs grid search over topology parameters (e.g., `asymUtil`) to find values that minimize the error between predicted and actual power consumption. It publishes the best-performing topology to Kafka for use by the simulator.

## How It Works

1. **Accumulate tasks** - Collect tasks from `dc.workload` over a calibration window
2. **Track power** - Record actual power consumption from `dc.power`
3. **Grid search** - Run parallel simulations with different parameter values
4. **Compare** - Calculate MAPE against actual power for each simulation
5. **Select** - Choose the parameter value with lowest error
6. **Publish** - Send calibrated topology to `sim.topology`

## Calibrated Properties

The calibrator can tune any numeric topology parameter. Common targets:

| Property | Path | Description |
|----------|------|-------------|
| asymUtil | cpuPowerModel.asymUtil | Asymptotic utilization coefficient |

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

Enable calibration in the config file:

```yaml
global:
  calibration_enabled: true
```

The calibrator only runs when this flag is set.

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

Note: The calibrator runs with the `calibration` Docker Compose profile. It will not start unless `calibration_enabled: true` is set.

## Related

- [Concepts](../../docs/CONCEPTS.md) - Calibration process details
- [Configuration](../../docs/CONFIGURATION.md) - Full configuration reference
- [simulator](../simulator/README.md) - Consumes calibrated topologies
