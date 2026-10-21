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
| cpu_capacity | float | CPU capacity in MHz (SURF: 33,600 for every task, a whole host) |
| mem_capacity | int | Memory capacity in MB |
| fragments | list | Execution profile segments |

### Fragment

A **Fragment** describes resource usage during a segment of task execution. Tasks can have varying resource usage over time.

| Field | Type | Description |
|-------|------|-------------|
| task_id | int | Parent task ID (`id` in the Parquet file) |
| duration | int | Segment duration in milliseconds |
| cpu_count | int | CPUs used in this segment |
| cpu_usage | float | CPU usage in MHz |

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
        ├── name: "H01"
        ├── count: 277 (number of identical hosts)
        ├── CPU
        │   ├── coreCount: 16
        │   └── coreSpeed: 2100 MHz
        ├── Memory
        │   └── memorySize: 128000000
        ├── CPUPowerModel
        │   ├── modelType: "mse"
        │   ├── power: 300 W
        │   ├── idlePower: 25 W
        │   ├── maxPower: 174 W
        │   └── calibrationFactor: 4
        └── GPU and GPUPowerModel (optional)
```

Each cluster also has a `powerSource.carbonTracePath`, the carbon intensity trace of its grid.

## Model Definitions

All data models are defined using Pydantic v2 in `libs/common/odt_common/models/`:

| Model | File | Description | Topic |
|-------|------|-------------|-------|
| Task | task.py | Workload task | - |
| Fragment | fragment.py | Task execution segment | - |
| WorkloadMessage | workload_message.py | A task or a heartbeat | `dc.workload` |
| Consumption | consumption.py | Power measurement | `dc.power` |
| TopologySnapshot | topology.py | The datacenter's topology at a time | `dc.topology` |
| Topology | topology.py | Datacenter topology | `sim.topology` |
| DynamicConfigEvent | `config.py` | A runtime setting from the control panel | `sys.config` |

These models provide:

- Runtime type validation
- JSON serialization/deserialization
- Automatic API documentation
