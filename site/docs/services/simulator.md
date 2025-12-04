---
sidebar_position: 2
---

# simulator

Core simulation engine that consumes workload data and produces power predictions using OpenDC.

## Purpose

The simulator aggregates tasks into time windows, invokes the OpenDC simulator, and outputs power consumption predictions. It maintains cumulative state to ensure accurate long-running simulations.

## Processing Flow

1. **Consume** - Read tasks from `dc.workload` topic
2. **Aggregate** - Group tasks into time windows
3. **Close** - When heartbeat timestamp exceeds window end
4. **Simulate** - Invoke OpenDC with all tasks from beginning
5. **Output** - Write results to `agg_results.parquet`

## Cumulative Simulation

Each window simulates all tasks from the beginning of the workload, not just tasks in that window. This ensures accurate power predictions for long-running workloads.

## OpenDC Integration

The simulator invokes the OpenDC binary for power calculations:

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
├── agg_results.parquet
└── opendc/
    └── run_<N>/
```

### agg_results.parquet

| Column | Description |
|--------|-------------|
| timestamp | Simulation timestamp |
| power_draw | Predicted power in Watts |
| carbon_intensity | Grid carbon intensity |

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| simulation_frequency_minutes | int | 5 | Window size for task aggregation |

Larger windows mean fewer OpenDC invocations but less granular results.

## Logs

```bash
make logs-simulator
```
