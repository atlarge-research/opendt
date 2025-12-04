---
sidebar_position: 2
---

# Global Settings

The `global:` section contains settings that affect the entire system.

## speed_factor

Controls how fast the simulation runs relative to real time.

| Value | Behavior |
|-------|----------|
| 1 | Real-time (1 second simulation = 1 second wall clock) |
| 300 | 300x speed (1 hour simulation = 12 seconds wall clock) |
| -1 | Maximum speed (no delays between messages) |

```yaml
global:
  speed_factor: 300
```

### Estimating Runtime

With the SURF workload (~7 days of data):

| Speed Factor | Approximate Runtime |
|--------------|---------------------|
| 1 | 7 days |
| 60 | ~2.8 hours |
| 300 | ~34 minutes |
| -1 | ~10 minutes |

## calibration_enabled

Enables the calibrator service for automatic parameter tuning.

```yaml
global:
  calibration_enabled: true
```

When `true`:

- The calibrator container starts
- Grid search runs periodically to optimize topology parameters
- Calibrated topologies are published to `sim.topology`
- Simulator uses calibrated values for predictions

When `false`:

- Calibrator does not start
- Simulator uses the original topology without modifications
