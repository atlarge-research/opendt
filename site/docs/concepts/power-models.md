---
sidebar_position: 4
---

# Power Models

The **CPUPowerModel** defines how CPU utilization translates to power consumption.

## Model Types

| Model | Power at CPU utilization u (from 0 to 1) |
|-------|---------------------------------------|
| mse | P(u) = idlePower + (maxPower - idlePower)(2u - u^r), with r the `calibrationFactor` |
| asymptotic | P(u) = idlePower + (maxPower - idlePower)/2 (1 + u - e^(-u/asymUtil)), with u³ in place of u when `dvfs` is on |

GPUs take OpenDC's other models in `gpuPowerModel` (e.g., "linear", "cubic"); the GPU prefabs use "cubic".

## Parameters

All power models share these common parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| power | float | Nominal power (Watts, required) |
| idlePower | float | Power draw at 0% utilization (Watts) |
| maxPower | float | Power draw at 100% utilization (Watts) |

### MSE Model

| Parameter | Description |
|-----------|-------------|
| calibrationFactor | Exponent r, from 0 to 50 (default: 0.5; SURF's hosts use 4) |

### Asymptotic Model

| Parameter | Description |
|-----------|-------------|
| asymUtil | Curve coefficient (0-1), controls the shape of the utilization curve |
| dvfs | Dynamic voltage and frequency scaling (default: false) |

The calibrator tunes `calibrationFactor` while the twin runs; see [Calibration](/docs/concepts/calibration).
