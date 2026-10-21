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
    ├── carbon_zones/        # NL, DE, PL, RO
    ├── topology.json
    └── workload.yaml
```

## Files

| File | Required | Description |
|------|----------|-------------|
| tasks.parquet | Yes | Task definitions with submission times and resource requirements |
| fragments.parquet | Yes | Task execution profiles showing resource usage over time |
| topology.json | Yes | Datacenter hardware configuration |
| consumption.parquet | No | Actual power measurements, the ground truth |
| carbon_zones/ | No | Carbon intensity per zone (NL, DE, PL, RO) [gCO2eq/kWh], for the CO₂ zone lever |
| carbon.parquet | No | Grid carbon intensity, used by the tutorial |
| workload.yaml | No | Name, description, and `timestamps.consumption_offset_ms`, added to the power timestamps |

## Selecting a Workload

Set the workload in your configuration file:

```yaml
services:
  dc-mock:
    workload: "SURF"
```

The value is the directory name under `workload/`; the containers see that directory at `/app/workload`.

## Creating Custom Workloads

To add a new workload:

1. Create a directory under `workload/`
2. Add the required files
3. Create a `topology.json` matching your datacenter hardware
4. Reference the directory name in your configuration

## Data Format

### tasks.parquet

| Column | Type | Description |
|--------|------|-------------|
| id | string | Unique task identifier, a number (e.g., "2152647") |
| submission_time | timestamp | When the task was submitted |
| duration | int | Task duration in milliseconds |
| cpu_count | int | Number of CPU cores |
| cpu_capacity | float | CPU capacity in MHz (SURF: 33,600 for every task, 16 cores x 2,100 MHz) |
| mem_capacity | int | Memory in MB |

### fragments.parquet

| Column | Type | Description |
|--------|------|-------------|
| id | string | ID of the task |
| duration | int | Fragment duration in milliseconds |
| cpu_count | int | CPUs used |
| cpu_usage | float | CPU usage in MHz |

### consumption.parquet

| Column | Type | Description |
|--------|------|-------------|
| timestamp | int | Milliseconds since the first task's submission (plus `consumption_offset_ms`) |
| power_draw | float | Power in Watts |
| energy_usage | float | Energy in Joules, per 30-s sample |
| host | string | Source of the measurement (not used by OpenDT) |
