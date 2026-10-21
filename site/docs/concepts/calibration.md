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
5. **Publish**: Send the calibrated topology to `sim.topology`, when the best value changes
6. **Apply**: Simulator uses calibrated topology for future windows

## MAPE Calculation

Mean Absolute Percentage Error measures prediction accuracy:

```
MAPE = mean(|actual - predicted| / actual) × 100%
```

The calibrator computes it over the last `mape_window_minutes` of power, on a 60-s grid.

Lower MAPE indicates better prediction accuracy; 10% is the community-accepted error rate for datacenter simulation.

## Calibrated Properties

The calibrator tunes one numeric parameter of the hosts, by its path from the host, on all hosts:

| Property | Path | Description |
|----------|------|-------------|
| asymUtil | cpuPowerModel.asymUtil | Asymptotic utilization coefficient (asymptotic power model only) |
| calibrationFactor | cpuPowerModel.calibrationFactor | Exponent r of the MSE power model; the one for SURF's hosts |

## Enabling Calibration

Add a `services.calibrator` section to the configuration file (see [calibrator](/docs/services/calibrator)), and set
`calibration_enabled: true` to calibrate from the start:

```yaml
global:
  calibration_enabled: true
```

The control panel switches calibration on and off while the twin runs.
