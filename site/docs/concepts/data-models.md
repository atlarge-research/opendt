---
sidebar_position: 1
---

# Data Models

OpenDT uses Pydantic models to define the structure of all data flowing through the system.

## Workload Data

### Task

A **Task** represents a job submitted to the datacenter. Each task requests compute resources for a specific duration.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| submission_time | datetime | When the task was submitted |
| duration | int | Total duration in milliseconds |
| cpu_count | int | Number of CPU cores requested |
| cpu_capacity | float | CPU speed in MHz |
| mem_capacity | int | Memory capacity in MB |
| fragments | list | Execution profile segments |

A task represents a request for compute cycles:

```
Total Cycles = cpu_count × cpu_capacity × duration
```

### Fragment

A **Fragment** describes resource usage during a segment of task execution. Tasks can have varying resource usage over time.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Fragment identifier |
| task_id | int | Parent task ID |
| duration | int | Segment duration in milliseconds |
| cpu_count | int | CPUs used in this segment |
| cpu_usage | float | CPU utilization value |

## Power Data

### Consumption

A **Consumption** record represents actual power telemetry from the datacenter.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | datetime | Measurement time |
| power_draw | float | Instantaneous power in Watts |
| energy_usage | float | Accumulated energy in Joules |

## Topology

The **Topology** defines the datacenter hardware that the simulator uses to calculate power. It is hierarchical: Clusters contain Hosts, which have CPUs, Memory, and a Power Model.

```
Topology
└── Cluster (e.g., "C01")
    └── Host
        ├── count: 277 (number of identical hosts)
        ├── CPU
        │   ├── coreCount: 16
        │   └── coreSpeed: 2100 MHz
        ├── Memory
        │   └── memorySize: 128 GB
        └── CPUPowerModel
            ├── modelType: "mse"
            ├── idlePower: 25 W
            ├── maxPower: 174 W
            └── calibrationFactor: 10.0
```

## Model Definitions

All data models are defined using Pydantic v2 in `libs/common/odt_common/models/`:

| Model | File | Description |
|-------|------|-------------|
| Task | task.py | Workload task |
| Fragment | fragment.py | Task execution segment |
| Consumption | consumption.py | Power measurement |
| Topology | topology.py | Datacenter topology |
| WorkloadMessage | workload_message.py | Kafka message wrapper |

These models provide:

- Runtime type validation
- JSON serialization/deserialization
- Automatic API documentation
