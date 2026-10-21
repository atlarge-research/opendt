---
sidebar_position: 3
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

The [calibrator](/docs/services/calibrator) page has the steps, the property it tunes, and its settings.

## MAPE Calculation

Mean Absolute Percentage Error measures prediction accuracy:

```
MAPE = mean(|actual - predicted| / actual) × 100%
```

The calibrator computes it over the last `mape_window_minutes` of power, on a 60-s grid. Lower MAPE indicates better
prediction accuracy; 10% is the community-accepted error rate for datacenter simulation.
