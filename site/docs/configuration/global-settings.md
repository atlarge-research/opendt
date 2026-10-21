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

The value must be above 0, or -1; without it, the speed is 10. The control panel changes the speed while the twin runs.

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

These are the replay times; the simulator can finish later, as each window re-simulates the trace from its start.

## calibration_enabled

Sets whether the calibrator tunes the power model from the start. The calibrator runs when the configuration has a
`services.calibrator` section (see [calibrator](/docs/services/calibrator)); `calibration_enabled: true` without that
section fails to load. The control panel switches calibration on and off while the twin runs.

```yaml
global:
  calibration_enabled: true
```

When calibrating:

- Grid searches run one after another over `linspace_points` values of `calibrated_property`, from `min_value` to
  `max_value`
- When the best value changes, the calibrated topology is published to `sim.topology`
- The simulator uses it from the next window

When not calibrating:

- The simulator uses the workload's topology, or the last one changed in the dashboard
