---
sidebar_position: 2
---

# Windowing

OpenDT aggregates tasks into **time windows** for batch simulation.

## How Windows Work

Tasks are assigned to windows based on their submission timestamp, from the minute of the first task (t0):

```
Window 0: [t0, t0 + 5 min)        →  Tasks with submission_time in this range
Window 1: [t0 + 5, t0 + 10 min)   →  ...
Window 2: [t0 + 10, t0 + 15 min)  →  ...
```

The window size is `services.simulator.simulation_frequency_minutes` (default: 15; 5 in `config/default.yaml`, 60 in
the experiments).

## Window Lifecycle

1. **Open**: Window accepts tasks as they arrive
2. **Fill**: Tasks accumulate in the window buffer
3. **Close**: A heartbeat reaches the window end time
4. **Simulate**: OpenDC runs all tasks so far, cut an hour past the window's end (`HORIZON` in
   `odt_common/result_cache.py`), and, at once, a second run on the whole tasks gives the jobs' finish times; with the
   same topology, scheduler, and task count as the previous window, and within its hour, that run is copied instead
5. **Output**: The window's own slice of the results is appended to `agg_results.parquet`; the full runs stay in
   `simulator/opendc/run_<N>/`

## Heartbeats

**Heartbeat messages** are synthetic timestamps published by dc-mock to signal time progression; only they close
windows. dc-mock sends one every `services.dc-mock.heartbeat_frequency_minutes` (default: 1), as a message on
`dc.workload`, up to the last job's submission.

## Cumulative Simulation

Each window simulates all tasks from the beginning of the workload, not just the tasks in that window, as long-running
tasks affect power across multiple windows. Each run rebuilds the scheduler state and the host allocations from the
trace start; a new topology therefore applies, from the next window, to the whole trace so far.

## Tuning Window Size

| Window Size | Trade-offs |
|-------------|------------|
| Small (1-5 min) | More granular results, higher computational cost |
| Large (30-60 min) | Fewer simulations, less granular results |

For long experiments, larger windows reduce total runtime while still capturing overall trends.
