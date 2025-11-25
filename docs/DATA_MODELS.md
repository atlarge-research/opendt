# Data Models

This document describes all data models used in OpenDT, their structure, validation rules, and usage patterns.

## Table of Contents

- [Overview](#overview)
- [Workload Models](#workload-models)
- [Topology Models](#topology-models)
- [Telemetry Models](#telemetry-models)
- [Message Wrappers](#message-wrappers)
- [Simulation Results](#simulation-results)
- [Data Physics](#data-physics)

## Overview

All data models in OpenDT are defined using **Pydantic v2** for:
- Runtime type validation
- JSON serialization/deserialization
- Automatic API documentation
- Data integrity guarantees

**Location**: [`../libs/common/opendt_common/models/`](../libs/common/opendt_common/models/)

## Workload Models

### Task

Represents a workload submission to the datacenter.

**File**: [`task.py`](../libs/common/opendt_common/models/task.py)

```python
class Task(BaseModel):
    """A workload task submitted to the datacenter."""
    
    id: int                     # Unique task identifier
    submission_time: datetime   # When task was submitted (ISO 8601)
    duration: int               # Total duration in milliseconds
    cpu_count: int              # Number of CPU cores requested
    cpu_capacity: float         # CPU speed in MHz
    mem_capacity: int           # Memory capacity in MB
    fragments: list[Fragment]   # Execution profile fragments
```

**Physical Interpretation**:
A task represents a request for compute cycles:
```
Total Cycles = cpu_count × cpu_capacity × duration × 1000
```

**Example**:
```json
{
  "id": 2132895,
  "submission_time": "2022-10-07T00:39:21",
  "duration": 12000,
  "cpu_count": 16,
  "cpu_capacity": 33600.0,
  "mem_capacity": 100000,
  "fragments": [...]
}
```

---

### Fragment

Represents a fine-grained execution profile segment of a task.

**File**: [`fragment.py`](../libs/common/opendt_common/models/fragment.py)

```python
class Fragment(BaseModel):
    """A time segment of task execution with specific resource usage."""
    
    id: int                  # Fragment identifier
    task_id: int             # Parent task ID
    duration: int            # Fragment duration in milliseconds
    cpu_count: int           # Number of CPUs used in this fragment
    cpu_usage: float         # CPU utilization for this fragment
```

**Purpose**: Fragments describe non-uniform resource usage over time. For example:
- First 1000ms: 100% CPU utilization (cpu_usage = 16.0 for 16 cores)
- Next 2000ms: 50% CPU utilization (cpu_usage = 8.0 for 16 cores)

**Example**:
```json
{
  "id": 1,
  "task_id": 2132895,
  "duration": 5000,
  "cpu_count": 16,
  "cpu_usage": 147.0
}
```

---

### WorkloadMessage

Wrapper for messages on `dc.workload` topic, distinguishing tasks from heartbeats.

**File**: [`workload_message.py`](../libs/common/opendt_common/models/workload_message.py)

```python
class WorkloadMessage(BaseModel):
    """Wrapper for messages on dc.workload topic."""
    
    message_type: Literal["task", "heartbeat"]  # Message type discriminator
    timestamp: datetime                          # Simulation timestamp
    task: Task | None = None                     # Task data (only if type="task")
```

**Usage**:

Task message:
```json
{
  "message_type": "task",
  "timestamp": "2022-10-07T00:39:21",
  "task": { /* Task object */ }
}
```

Heartbeat message:
```json
{
  "message_type": "heartbeat",
  "timestamp": "2022-10-07T00:45:00",
  "task": null
}
```

**Purpose**: Heartbeats signal time progression to consumers, enabling deterministic window closing even when no tasks arrive.

## Topology Models

### Topology

Root model representing datacenter infrastructure.

**File**: [`topology.py`](../libs/common/opendt_common/models/topology.py)

```python
class Topology(BaseModel):
    """Datacenter topology definition."""
    
    clusters: list[Cluster]  # List of clusters (min 1 required)
    
    # Helper methods
    def total_host_count() -> int
    def total_core_count() -> int
    def total_memory_bytes() -> int
```

**Example**:
```json
{
  "clusters": [
    {
      "name": "A01",
      "hosts": [/* Host objects */]
    }
  ]
}
```

---

### Cluster

Represents a logical group of hosts.

```python
class Cluster(BaseModel):
    """Cluster of hosts in a datacenter."""
    
    name: str              # Cluster identifier
    hosts: list[Host]      # List of host configurations (min 1 required)
```

---

### Host

Represents a physical server configuration (possibly replicated).

```python
class Host(BaseModel):
    """Host (physical server) in a datacenter cluster."""
    
    name: str                        # Host identifier/name
    count: int                       # Number of identical hosts
    cpu: CPU                         # CPU specification
    memory: Memory                   # Memory specification
    cpuPowerModel: CPUPowerModel     # Power consumption model
```

**Example**:
```json
{
  "name": "A01-Host",
  "count": 277,
  "cpu": { "coreCount": 16, "coreSpeed": 2100 },
  "memory": { "memorySize": 128000000 },
  "cpuPowerModel": { /* Power model */ }
}
```

---

### CPU

CPU hardware specification.

```python
class CPU(BaseModel):
    """CPU specification for a host."""
    
    coreCount: int      # Number of CPU cores (> 0)
    coreSpeed: float    # CPU speed in MHz (> 0)
```

---

### Memory

Memory hardware specification.

```python
class Memory(BaseModel):
    """Memory specification for a host."""
    
    memorySize: int     # Memory size in bytes (> 0)
```

---

### CPUPowerModel

Defines how CPU utilization translates to power consumption.

```python
class CPUPowerModel(BaseModel):
    """CPU power consumption model."""
    
    modelType: Literal["asymptotic", "linear", "square", "cubic", "sqrt"]
    power: float           # Nominal power consumption in Watts (> 0)
    idlePower: float       # Power at 0% utilization in Watts (≥ 0)
    maxPower: float        # Power at 100% utilization in Watts (> 0)
    asymUtil: float = 0.5  # Asymptotic utilization coefficient (0-1)
    dvfs: bool = False     # Dynamic Voltage/Frequency Scaling enabled
```

**Power Model Types**:
- **asymptotic**: Realistic non-linear curve (recommended)
- **linear**: Simple linear interpolation between idle and max
- **square**: Quadratic relationship
- **cubic**: Cubic relationship
- **sqrt**: Square root relationship

**Example**:
```json
{
  "modelType": "asymptotic",
  "power": 400.0,
  "idlePower": 32.0,
  "maxPower": 180.0,
  "asymUtil": 0.3,
  "dvfs": false
}
```

---

### TopologySnapshot

Timestamped wrapper for topology on `dc.topology` topic.

```python
class TopologySnapshot(BaseModel):
    """Timestamped topology snapshot for Kafka messages."""
    
    timestamp: datetime    # When snapshot was captured (ISO 8601)
    topology: Topology     # The datacenter topology
```

**Purpose**: Adds temporal context to topology updates, enabling time-travel and audit trails.

**Example**:
```json
{
  "timestamp": "2022-10-07T09:14:30",
  "topology": { /* Topology object */ }
}
```

## Telemetry Models

### Consumption

Power consumption telemetry from datacenter.

**File**: [`consumption.py`](../libs/common/opendt_common/models/consumption.py)

```python
class Consumption(BaseModel):
    """Power consumption measurement from datacenter."""
    
    power_draw: float       # Instantaneous power in Watts
    energy_usage: float     # Accumulated energy in Joules
    timestamp: datetime     # Measurement timestamp (ISO 8601)
```

**Example**:
```json
{
  "power_draw": 19180.0,
  "energy_usage": 575400.0,
  "timestamp": "2022-10-08T06:35:30"
}
```

**Units**:
- `power_draw`: Watts (W)
- `energy_usage`: Joules (J) - accumulated since last snapshot
- To convert Joules to kWh: `kWh = joules / 3,600,000`

## Simulation Results

### SimulationResults

Output from OpenDC simulator.

**File**: [`sim_worker/runner/models.py`](../services/sim-worker/sim_worker/runner/models.py)

```python
class SimulationResults(BaseModel):
    """Results from OpenDC simulation."""
    
    status: str                            # "success" or "error"
    error: str | None = None               # Error message if failed
    
    # Summary Statistics
    energy_kwh: float = 0.0               # Total energy in kilowatt-hours
    cpu_utilization: float = 0.0          # Average CPU utilization (0.0-1.0)
    max_power_draw: float = 0.0           # Maximum power in Watts
    runtime_hours: float = 0.0            # Simulated runtime duration
    
    # Timeseries Data
    power_draw_series: list[TimeseriesData] = []      # Power over time
    cpu_utilization_series: list[TimeseriesData] = [] # CPU util over time
    
    # Metadata
    temp_dir: str | None = None           # Temporary directory path
    opendc_output_dir: str | None = None  # OpenDC output directory
```

---

### TimeseriesData

Timeseries data point.

```python
class TimeseriesData(BaseModel):
    """Single timeseries data point."""
    
    timestamp: int    # Milliseconds offset from simulation start
    value: float      # Measured value
```

**Example**:
```json
{
  "timestamp": 150000,
  "value": 18750.5
}
```

## Data Physics

### Task Execution

A task's resource requirements define the total compute cycles needed:

```python
total_cycles = cpu_count × cpu_capacity × duration × 1000
```

**Example**:
- 16 cores × 3360 MHz × 12 seconds = 644,352,000 cycles

### Fragment Profiling

Fragments break down task execution into segments with varying resource usage:

1. **Bursty Task**: 
   - Fragment 1 (0-1s): 100% CPU
   - Fragment 2 (1-10s): 20% CPU
   - Fragment 3 (10-12s): 80% CPU

2. **Steady Task**:
   - Single fragment (0-12s): 75% CPU

This allows accurate power modeling for real-world workload patterns.

### Energy Integration

Total energy consumed:
```
Energy (Joules) = ∫ Power(t) dt
Energy (kWh) = Joules / 3,600,000
```

## Validation Rules

### Field Constraints

Pydantic enforces validation at runtime:

- **Positive integers**: `gt=0` (cpu_count, duration, count)
- **Non-negative floats**: `ge=0` (idlePower)
- **Positive floats**: `gt=0` (cpu_capacity, maxPower)
- **Ranges**: `ge=0, le=1` (asymUtil, cpu_utilization)
- **Min length**: `min_length=1` (clusters, hosts, fragments)
- **Datetime**: ISO 8601 format required

### Example Validation

```python
from opendt_common.models import Task

# Valid task
task = Task(
    id=1,
    submission_time="2022-10-07T00:39:21",
    duration=1000,
    cpu_count=8,
    cpu_capacity=2400.0,
    mem_capacity=64000,
    fragments=[]
)

# Invalid task (negative duration)
try:
    Task(
        id=2,
        duration=-100,  # ❌ Will raise ValidationError
        ...
    )
except ValidationError as e:
    print(e)
```

## Usage Patterns

### Serialization

```python
from opendt_common.models import Task

# To JSON
task_json = task.model_dump(mode="json")
task_str = task.model_dump_json()

# From JSON
task = Task(**json_data)
task = Task.model_validate_json(json_string)
```

### Kafka Integration

```python
from opendt_common.utils.kafka import send_message
from opendt_common.models import TopologySnapshot

snapshot = TopologySnapshot(
    timestamp=datetime.now(),
    topology=topology
)

send_message(
    producer=producer,
    topic="dc.topology",
    message=snapshot.model_dump(mode="json"),
    key="datacenter"
)
```

## Related Documentation

- [Architecture Overview](./ARCHITECTURE.md) - System design and data flow
- [Dashboard Documentation](../services/dashboard/README.md) - Web UI and REST API using these models
- [Simulation Worker](../services/sim-worker/README.md) - How models are used in simulation

---

For model source code, see [`libs/common/opendt_common/models/`](../libs/common/opendt_common/models/).
