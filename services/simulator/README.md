# simulator

Core simulation engine that consumes workload data and produces power predictions using OpenDC.

## Purpose

The simulator aggregates tasks into time windows, invokes the OpenDC simulator, and outputs power consumption predictions. It maintains cumulative state to ensure accurate long-running simulations.

## Processing Flow

1. **Consume** - Read tasks from `dc.workload` topic
2. **Aggregate** - Group tasks into time windows based on submission timestamp
3. **Close** - When heartbeat timestamp exceeds window end, close the window
4. **Simulate** - Invoke OpenDC with all tasks from beginning (cumulative)
5. **Output** - Write results to `agg_results.parquet`

## Windowing

Tasks are grouped into windows based on `simulation_frequency_minutes`:

```
Window 0: [00:00 - 00:05)  →  Tasks with submission_time in this range
Window 1: [00:05 - 00:10)  →  ...
```

Windows close when a heartbeat arrives with a timestamp past the window end.

### Cumulative Simulation

Each window simulates all tasks from the beginning of the workload, not just tasks in that window. This ensures accurate power predictions for long-running workloads.

## OpenDC Integration

The simulator invokes the OpenDC binary to perform actual power calculations:

```
opendc/bin/OpenDCExperimentRunner
```

### Input Files

Created for each simulation run:
- `experiment.json` - OpenDC configuration
- `topology.json` - Datacenter topology
- `tasks.parquet` - Task definitions
- `fragments.parquet` - Task execution profiles

### Output Files

Parsed after simulation:
- `powerSource.parquet` - Power consumption over time
- `host.parquet` - Host-level metrics

## Output

Results are written to `data/<RUN_ID>/simulator/`:

```
simulator/
├── agg_results.parquet    # Aggregated power predictions
└── opendc/
    └── run_<N>/           # Individual simulation archives
        ├── input/
        └── output/
```

### agg_results.parquet

| Column | Description |
|--------|-------------|
| timestamp | Simulation timestamp |
| power_draw | Predicted power in Watts |
| carbon_intensity | Grid carbon intensity |

## Configuration

From the main config file:

```yaml
services:
  simulator:
    simulation_frequency_minutes: 5  # Window size
```

## Logs

```
make logs-simulator
```

## Related

- [Concepts](../../docs/CONCEPTS.md) - Time windows, cumulative simulation
- [Configuration](../../docs/CONFIGURATION.md) - Full configuration reference
- [dc-mock](../dc-mock/README.md) - Data source
