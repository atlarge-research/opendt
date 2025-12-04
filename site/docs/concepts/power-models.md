---
sidebar_position: 2
---

# Power Models

The **CPUPowerModel** defines how CPU utilization translates to power consumption. Different model types suit different hardware characteristics.

## Model Types

| Model | Description | Best For |
|-------|-------------|----------|
| mse | Mean Squared Error based model | General purpose, default |
| asymptotic | Non-linear curve with asymptotic behavior | High-utilization workloads |
| linear | Linear interpolation between idle and max power | Simple approximations |

## Parameters

All power models share these common parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| idlePower | float | Power draw at 0% utilization (Watts) |
| maxPower | float | Power draw at 100% utilization (Watts) |

### MSE Model

The MSE model uses a calibration factor to scale predictions:

| Parameter | Description |
|-----------|-------------|
| calibrationFactor | Scaling multiplier for power calculation |

### Asymptotic Model

The asymptotic model provides non-linear scaling:

| Parameter | Description |
|-----------|-------------|
| asymUtil | Curve coefficient (0-1), controls the shape of the utilization curve |

## Example Configuration

```json
{
  "cpuPowerModel": {
    "modelType": "mse",
    "idlePower": 25.0,
    "maxPower": 174.0,
    "calibrationFactor": 10.0
  }
}
```

## Calibration

When calibration is enabled, OpenDT automatically tunes power model parameters to minimize the error between predicted and actual power consumption.

The calibrator runs parallel simulations with different parameter values, calculates MAPE (Mean Absolute Percentage Error) against actual measurements, and publishes the best-performing configuration.
