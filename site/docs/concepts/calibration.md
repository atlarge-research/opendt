---
sidebar_position: 4
---

# Calibration

When enabled, the **calibrator** service optimizes topology parameters by comparing simulation output against actual power measurements.

## Why Calibrate?

Power models are approximations of real hardware behavior. Initial parameter values from datasheets may not accurately reflect actual power consumption under real workloads.

Calibration automatically finds parameter values that minimize prediction error, improving accuracy over time.

## Calibration Process

```
                  ┌─────────────────────────────────────┐
                  │           Grid Search               │
                  │  ┌─────┐  ┌─────┐  ┌─────┐          │
                  │  │Sim 1│  │Sim 2│  │Sim 3│  ...     │
                  │  │ P=A │  │ P=B │  │ P=C │          │
                  │  └──┬──┘  └──┬──┘  └──┬──┘          │
                  │     │        │        │             │
                  │     ▼        ▼        ▼             │
                  │  ┌─────────────────────────┐        │
                  │  │    Compare with Actual  │        │
                  │  │    Calculate MAPE       │        │
                  │  └───────────┬─────────────┘        │
                  │              │                      │
                  │              ▼                      │
                  │      Select Lowest Error            │
                  └──────────────┬──────────────────────┘
                                 │
                                 ▼
                      Publish Calibrated Topology
```

1. **Accumulate**: Collect tasks and actual power readings
2. **Search**: Run parallel simulations with different parameter values
3. **Compare**: Calculate MAPE for each configuration
4. **Select**: Choose the parameter value with lowest error
5. **Publish**: Send calibrated topology to `sim.topology`
6. **Apply**: Simulator uses calibrated topology for future windows

## MAPE Calculation

Mean Absolute Percentage Error measures prediction accuracy:

```
MAPE = mean(|actual - predicted| / actual) × 100%
```

Lower MAPE indicates better prediction accuracy. A well-calibrated model typically achieves MAPE under 5%.

## Calibrated Properties

The calibrator can tune any numeric topology parameter. Common targets:

| Property | Path | Description |
|----------|------|-------------|
| asymUtil | cpuPowerModel.asymUtil | Asymptotic utilization coefficient |
| calibrationFactor | cpuPowerModel.calibrationFactor | MSE model scaling factor |

## Enabling Calibration

Set `calibration_enabled: true` in your configuration file:

```yaml
global:
  calibration_enabled: true
```

The calibrator only runs when this flag is set.
