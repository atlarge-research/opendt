---
sidebar_position: 3
---

# Windowing

OpenDT aggregates tasks into **time windows** for batch simulation. This approach balances simulation accuracy with computational efficiency.

## How Windows Work

Tasks are assigned to windows based on their submission timestamp, from the minute of the first task (t0):

```
Window 0: [t0, t0 + 5 min)        →  Tasks with submission_time in this range
Window 1: [t0 + 5, t0 + 10 min)   →  ...
Window 2: [t0 + 10, t0 + 15 min)  →  ...
```

The window size is controlled by `services.simulator.simulation_frequency_minutes` in the configuration (default: 15; 5
in `config/default.yaml`, 60 in the experiments).

## Window Lifecycle

1. **Open**: Window accepts tasks as they arrive
2. **Fill**: Tasks accumulate in the window buffer
3. **Close**: Heartbeat timestamp reaches the window end time
4. **Simulate**: All tasks so far are processed by OpenDC; with the same topology, scheduler, and task count as the
   previous window, that run is copied instead
5. **Output**: The window's own slice of the results is appended to `agg_results.parquet`; the full runs stay in
   `simulator/opendc/run_<N>/`

## Heartbeats

**Heartbeat messages** are synthetic timestamps published by dc-mock to signal time progression. They enable deterministic window closing even when no tasks arrive during a period. dc-mock sends one every
`services.dc-mock.heartbeat_frequency_minutes` (default: 1), as a WorkloadMessage on `dc.workload`.

Without heartbeats, windows would only close when new tasks arrive, leading to unpredictable timing in sparse workloads.

## Cumulative Simulation

OpenDT uses **cumulative simulation**: each window simulates all tasks from the beginning of the workload, not just tasks in that window.

This approach ensures accurate power predictions because:

- Long-running tasks affect power across multiple windows
- Each run rebuilds the scheduler state and the host allocations from the trace start
- A new topology applies from the next window, to the whole trace so far

## Tuning Window Size

| Window Size | Trade-offs |
|-------------|------------|
| Small (1-5 min) | More granular results, higher computational cost |
| Large (30-60 min) | Fewer simulations, less granular results |

For long experiments, larger windows reduce total runtime while still capturing overall trends.
