---
sidebar_position: 2
---

# simulator

Core simulation engine that consumes workload data and produces power predictions using OpenDC.

## Purpose

The simulator aggregates tasks into time windows, invokes the OpenDC simulator, and outputs power consumption predictions. It maintains cumulative state to ensure accurate long-running simulations.

## Processing Flow

1. **Consume** - Read tasks from the `dc.workload` topic, the topology from `dc.topology` and `sim.topology` (applied
   from the next window), and the scheduler from `sys.config`
2. **Aggregate** - Group tasks into time windows
3. **Close** - When the heartbeat timestamp reaches the window end
4. **Simulate** - Invoke OpenDC with all tasks from the beginning; with the same topology, scheduler, and task count as
   the previous window, that run is copied instead (`cached: true`)
5. **Output** - Append the window's own slice of the results to `agg_results.parquet`

## Cumulative Simulation

Each window simulates all tasks from the beginning of the workload, not just tasks in that window. This ensures accurate power predictions for long-running workloads.

## OpenDC Integration

The simulator invokes the OpenDC binary for power calculations:

```
opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner --experiment-path ...
```

It is called by `libs/common/odt_common/odc_runner/runner.py`, with a timeout of 120 s per run.

### Input Files

Created for each simulation run:

- `experiment.json` - OpenDC configuration
- `topology.json` - Datacenter topology
- `tasks.parquet` - Task definitions
- `fragments.parquet` - Task execution profiles

### Output Files

OpenDC exports `powerSource`, `host`, `task`, and `service` every 150 s. The simulator parses `powerSource.parquet`
(power consumption over time); the API reads the others for the screens.

## Output

Results are written to `data/<RUN_ID>/simulator/`:

```
simulator/
├── agg_results.parquet
└── opendc/
    └── run_<N>/
        ├── input/
        ├── output/
        └── metadata.json
```

`metadata.json` is written last: a run without it is still running.

### agg_results.parquet

| Column | Description |
|--------|-------------|
| timestamp | Simulation timestamp |
| run_number | The window's OpenDC run |
| power_draw | Predicted power in Watts |
| energy_usage | Predicted energy in Joules |
| carbon_intensity | Grid carbon intensity |
| carbon_emission | Predicted carbon emission |
| cached | Whether the run was copied from the previous window |

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| simulation_frequency_minutes | int | 15 | Window size for task aggregation (5 in `config/default.yaml`, 60 in the experiments) |
| background_load_nodes | int | - | Required: hosts of the first group reserved for background load, removed from the simulation |

Larger windows mean fewer OpenDC invocations but less granular results.

## Logs

```bash
make logs-simulator
```
