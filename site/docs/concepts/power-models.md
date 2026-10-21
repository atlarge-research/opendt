---
sidebar_position: 2
---

# Power Models

The **CPUPowerModel** defines how CPU utilization translates to power consumption. Different model types suit different hardware characteristics.

## Model Types

| Model | Power at CPU utilization u (from 0 to 1) |
|-------|---------------------------------------|
| mse | P(u) = idlePower + (maxPower - idlePower)(2u - u^r), with r the `calibrationFactor` |
| asymptotic | P(u) = idlePower + (maxPower - idlePower)/2 (1 + u - e^(-u/asymUtil)), with u³ in place of u when `dvfs` is on |

GPUs take OpenDC's other models in `gpuPowerModel` (e.g., "linear", "cubic").

## Parameters

All power models share these common parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| power | float | Nominal power (Watts, required) |
| idlePower | float | Power draw at 0% utilization (Watts) |
| maxPower | float | Power draw at 100% utilization (Watts) |

### MSE Model

The MSE model shapes the curve between idle and maximum power with an exponent:

| Parameter | Description |
|-----------|-------------|
| calibrationFactor | Exponent r, from 0 to 50 (default: 0.5; SURF's hosts use 4) |

### Asymptotic Model

The asymptotic model provides non-linear scaling:

| Parameter | Description |
|-----------|-------------|
| asymUtil | Curve coefficient (0-1), controls the shape of the utilization curve |
| dvfs | Dynamic voltage and frequency scaling (default: false) |

## Example Configuration

```json
{
  "cpuPowerModel": {
    "modelType": "mse",
    "power": 300.0,
    "idlePower": 25.0,
    "maxPower": 174.0,
    "calibrationFactor": 4
  }
}
```

## Calibration

When calibration is enabled, OpenDT automatically tunes power model parameters to minimize the error between predicted and actual power consumption.

The calibrator runs parallel simulations with different parameter values, calculates MAPE (Mean Absolute Percentage Error) against actual measurements, and publishes the best-performing configuration.
