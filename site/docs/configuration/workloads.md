---
sidebar_position: 3
---

# Workloads

Workload data defines the tasks and power measurements that OpenDT simulates.

## Workload Directory

Workloads are stored in the `workload/` directory. Each workload has its own subdirectory:

```
workload/
└── SURF/
    ├── tasks.parquet
    ├── fragments.parquet
    ├── consumption.parquet
    ├── carbon.parquet
    └── topology.json
```

## Required Files

| File | Description |
|------|-------------|
| tasks.parquet | Task definitions with submission times and resource requirements |
| fragments.parquet | Task execution profiles showing resource usage over time |
| consumption.parquet | Actual power measurements from the real datacenter |
| carbon.parquet | Grid carbon intensity data |
| topology.json | Datacenter hardware configuration |

## Selecting a Workload

Set the workload in your configuration file:

```yaml
services:
  dc-mock:
    workload: "SURF"
```

The value is the directory name under `workload/`.

## Creating Custom Workloads

To add a new workload:

1. Create a directory under `workload/`
2. Add the required Parquet files
3. Create a `topology.json` matching your datacenter hardware
4. Reference the directory name in your configuration

## Data Format

### tasks.parquet

| Column | Type | Description |
|--------|------|-------------|
| id | int | Unique task identifier |
| submission_time | timestamp | When the task was submitted |
| duration | int | Task duration in milliseconds |
| cpu_count | int | Number of CPU cores |
| cpu_capacity | float | CPU speed in MHz |
| mem_capacity | int | Memory in MB |

### fragments.parquet

| Column | Type | Description |
|--------|------|-------------|
| id | int | Fragment identifier |
| task_id | int | Parent task ID |
| duration | int | Fragment duration in milliseconds |
| cpu_count | int | CPUs used |
| cpu_usage | float | CPU utilization |

### consumption.parquet

| Column | Type | Description |
|--------|------|-------------|
| timestamp | timestamp | Measurement time |
| power_draw | float | Power in Watts |
| energy_usage | float | Energy in Joules |
