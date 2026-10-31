---
sidebar_position: 2
---

# simulator

Core simulation engine that consumes workload data and produces power predictions using OpenDC.

## Purpose

The simulator runs OpenDC twice per window of operation, at once: on the tasks so far, up to an hour past the window
(power, hosts, and services), and on the whole tasks (the jobs' finish times); see [Windowing](/docs/concepts/windowing).
It reads the tasks from `dc.workload`, the topology from `dc.topology` and `sim.topology`, and the scheduler from
`sys.config`. From the next window, it runs the last topology on `sim.topology` (from the dashboard, the API, or the
calibrator), else the workload's.

## OpenDC Integration

The simulator invokes the OpenDC binary for power calculations:

```
opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner --experiment-path ...
```

It is called by `libs/common/odt_common/odc_runner/runner.py`, with a timeout of 120 s per run.

### Input Files

Created for each window, in `run_<N>/input/`:

- `topology.json` - Datacenter topology
- `experiment.json` and `now/` (`tasks.parquet`, `fragments.parquet`) - The tasks up to an hour past the window
- `future.json` and `future/` - The whole tasks

### Output Files

OpenDC exports `powerSource`, `host`, and `service` into `output/now/`, and `task` into `output/future/`, every 150 s.
The simulator parses `powerSource.parquet` (power consumption over time); the API reads the others for the screens.

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

`metadata.json` is written last: a run without it is still running, or failed.

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
| simulation_frequency_minutes | int | 15 | Window size (5 in `config/default.yaml`, 60 in the experiments) |

## Logs

```bash
make logs-simulator
```
