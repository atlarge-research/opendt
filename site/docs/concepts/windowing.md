---
sidebar_position: 3
---

# Windowing

OpenDT aggregates tasks into **time windows** for batch simulation. This approach balances simulation accuracy with computational efficiency.

## How Windows Work

Tasks are assigned to windows based on their submission timestamp:

```
Window 0: [00:00 - 00:05)  →  Tasks with submission_time in this range
Window 1: [00:05 - 00:10)  →  ...
Window 2: [00:10 - 00:15)  →  ...
```

The window size is controlled by `simulation_frequency_minutes` in the configuration.

## Window Lifecycle

1. **Open**: Window accepts tasks as they arrive
2. **Fill**: Tasks accumulate in the window buffer
3. **Close**: Heartbeat timestamp exceeds window end time
4. **Simulate**: All accumulated tasks are processed by OpenDC
5. **Output**: Results are written to `agg_results.parquet`

## Heartbeats

**Heartbeat messages** are synthetic timestamps published by dc-mock to signal time progression. They enable deterministic window closing even when no tasks arrive during a period.

Without heartbeats, windows would only close when new tasks arrive, leading to unpredictable timing in sparse workloads.

## Cumulative Simulation

OpenDT uses **cumulative simulation**: each window simulates all tasks from the beginning of the workload, not just tasks in that window.

This approach ensures accurate power predictions because:

- Long-running tasks affect power across multiple windows
- Scheduler state persists between windows
- Host allocations remain consistent

## Tuning Window Size

| Window Size | Trade-offs |
|-------------|------------|
| Small (1-5 min) | More granular results, higher computational cost |
| Large (30-60 min) | Fewer simulations, less granular results |

For long experiments, larger windows reduce total runtime while still capturing overall trends.
