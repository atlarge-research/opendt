---
sidebar_position: 2
---

# Global Settings

The `global:` section contains settings that affect the entire system.

## speed_factor

Controls how fast the replay runs relative to real time.

| Value | Behavior |
|-------|----------|
| 1 | Real-time (1 second simulation = 1 second wall clock) |
| 300 | 300x speed (1 hour simulation = 12 seconds wall clock) |
| -1 | Maximum speed (no delays between messages) |

```yaml
global:
  speed_factor: 300
```

The value must be above 0, or -1; without it, the speed is 10. The control panel changes the speed while the twin runs.

### Estimating Runtime

The replay of the SURF workload (~7 days of data) takes:

| Speed Factor | Approximate Runtime |
|--------------|---------------------|
| 1 | 7 days |
| 60 | ~2.8 hours |
| 300 | ~34 minutes |

The simulator can finish later, as each window re-simulates the trace from its start. At maximum speed, the OpenDT paper
twins the 7 days within 46 minutes, on a common machine.

## calibration_enabled

Sets whether the calibrator tunes the power model from the start. The calibrator runs only with a `services.calibrator`
section (see [calibrator](/docs/services/calibrator)); `calibration_enabled: true` without that section fails to load.

```yaml
global:
  calibration_enabled: true
```
