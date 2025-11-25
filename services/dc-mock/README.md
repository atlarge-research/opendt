# dc-mock Service

The **dc-mock** service simulates a real datacenter by replaying historical workload and power consumption data to Kafka topics. It acts as the data source for the entire OpenDT system.

## Overview

**Purpose**: Replay historical datacenter data with configurable speed factor  
**Type**: Kafka Producer  
**Language**: Python 3.11+  
**Framework**: Threading + kafka-python

## Responsibilities

1. **Workload Replay**: Stream task submissions from `tasks.parquet` and `fragments.parquet`
2. **Power Telemetry**: Stream power consumption from `consumption.parquet`
3. **Topology Broadcasting**: Periodically publish datacenter topology from `topology.json`
4. **Heartbeat Generation**: Send periodic heartbeat messages for window synchronization

## Architecture

```
data/SURF/
├── tasks.parquet       ─┐
├── fragments.parquet   ─┤─> WorkloadProducer ─> dc.workload
├── consumption.parquet ─┤─> PowerProducer ───> dc.power
└── topology.json       ─┘─> TopologyProducer ─> dc.topology
```

### Producers

#### 1. WorkloadProducer

**File**: [`dc_mock/producers/workload_producer.py`](./dc_mock/producers/workload_producer.py)

- Reads `tasks.parquet` and `fragments.parquet`
- Joins tasks with their fragments
- Publishes `WorkloadMessage` objects to `dc.workload`
- Emits **heartbeat messages** every `heartbeat_cadence_minutes` (simulation time)
- Respects `speed_factor` for time progression

**Message Types**:
```python
# Task message
{
    "message_type": "task",
    "timestamp": "2022-10-07T00:39:21",
    "task": {
        "id": 2132895,
        "submission_time": "2022-10-07T00:39:21",
        "duration": 12000,
        "cpu_count": 16,
        "cpu_capacity": 33600.0,
        "mem_capacity": 100000,
        "fragments": [...]
    }
}

# Heartbeat message
{
    "message_type": "heartbeat",
    "timestamp": "2022-10-07T00:45:00",
    "task": null
}
```

#### 2. PowerProducer

**File**: [`dc_mock/producers/power_producer.py`](./dc_mock/producers/power_producer.py)

- Reads `consumption.parquet`
- Publishes `Consumption` objects to `dc.power`
- Provides ground truth for comparing simulation predictions

**Message Format**:
```python
{
    "power_draw": 19180.0,      # Watts
    "energy_usage": 575400.0,   # Joules
    "timestamp": "2022-10-08T06:35:30"
}
```

#### 3. TopologyProducer

**File**: [`dc_mock/producers/topology_producer.py`](./dc_mock/producers/topology_producer.py)

- Reads `topology.json`
- Publishes `TopologySnapshot` to `dc.topology` every 30 seconds (real-time)
- Uses compacted topic with key `"datacenter"` to keep latest only

**Message Format**:
```python
{
    "timestamp": "2022-10-07T09:14:30",
    "topology": {
        "clusters": [...]
    }
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to YAML configuration | `/app/config/simulation.yaml` |
| `WORKER_ID` | Unique producer identifier | `dc-mock-1` |

### YAML Configuration

**File**: `config/default.yaml`

```yaml
workload: "SURF"  # Maps to data/SURF/

simulation:
  speed_factor: 300  # 300x real-time
  heartbeat_cadence_minutes: 1  # Heartbeat every 1 minute (sim time)

kafka:
  bootstrap_servers: "kafka:29092"
  topics:
    workload:
      name: "dc.workload"
    power:
      name: "dc.power"
    topology:
      name: "dc.topology"
```

### Speed Factor Behavior

- `speed_factor: 1.0` - Real-time replay (1 second sim = 1 second real)
- `speed_factor: 300.0` - 300x faster (1 hour sim = 12 seconds real)
- `speed_factor: -1` - Maximum speed (no sleep between messages)

**Formula**:
```python
sleep_time = (next_timestamp - current_timestamp) / speed_factor
```

## Data Format

### Input Files

Located in `data/<WORKLOAD_NAME>/`:

#### `tasks.parquet`

Required columns:
- `id` (int): Task identifier
- `submission_time` (datetime): When task was submitted
- `duration` (int): Task duration in milliseconds
- `cpu_count` (int): Number of CPUs requested
- `cpu_capacity` (float): CPU speed in MHz
- `mem_capacity` (int): Memory in MB

#### `fragments.parquet`

Required columns:
- `id` (int): Fragment identifier
- `task_id` (int): Parent task ID
- `duration` (int): Fragment duration in milliseconds
- `cpu_count` (int): CPUs used
- `cpu_usage` (float): CPU utilization value

#### `consumption.parquet`

Required columns:
- `timestamp` (datetime): Measurement time
- `power_draw` (float): Instantaneous power in Watts
- `energy_usage` (float): Accumulated energy in Joules

#### `topology.json`

See [Data Models documentation](../../docs/DATA_MODELS.md#topology-models) for schema.

## Running

### Via Docker Compose

```bash
# Start all services
make up

# View dc-mock logs
make logs-dc-mock

# Or directly:
docker compose logs -f dc-mock
```

### Standalone (Development)

```bash
cd services/dc-mock
source ../../.venv/bin/activate

CONFIG_FILE=../../config/default.yaml \
python -m dc_mock.main
```

## Heartbeat Mechanism

### Purpose

Heartbeats solves the problem: How does the consumer know when to close a window?

Without heartbeats:
- Consumer can't distinguish between "no new tasks" and "Kafka delay"
- Windows might close prematurely or stay open indefinitely

With heartbeats:
- Producer sends heartbeat every N minutes (simulation time)
- Consumer knows time has progressed even without task arrivals
- Windows can be closed deterministically based on heartbeat timestamps

### Implementation

```python
next_heartbeat_time = first_task_time.floor('1min')

for task in sorted_tasks:
    # Emit heartbeats for all minutes before this task
    while next_heartbeat_time < task.submission_time:
        heartbeat = WorkloadMessage(
            message_type="heartbeat",
            timestamp=next_heartbeat_time,
            task=None
        )
        publish(heartbeat)
        next_heartbeat_time += timedelta(minutes=heartbeat_cadence)
    
    # Emit the task
    task_message = WorkloadMessage(
        message_type="task",
        timestamp=task.submission_time,
        task=task
    )
    publish(task_message)
```

### Configuration

```yaml
simulation:
  heartbeat_cadence_minutes: 1  # Send heartbeat every 1 minute (sim time)
```

**Trade-offs**:
- **Shorter cadence** (e.g., 1 minute): More accurate window closing, more Kafka messages
- **Longer cadence** (e.g., 5 minutes): Fewer messages, less precise window boundaries

## Monitoring

### Logs

```bash
# View producer activity
docker compose logs -f dc-mock

# Expected output:
# INFO - Starting WorkloadProducer...
# INFO - Loaded 12,345 tasks from tasks.parquet
# INFO - Starting PowerProducer...
# INFO - Starting TopologyProducer...
# INFO - Published heartbeat: 2022-10-07T00:01:00
# INFO - Published task 2132895 to dc.workload
# INFO - Published power telemetry to dc.power: 19180.0 W
```

### Kafka Topic Inspection

```bash
# List topics
make kafka-topics

# Consume from workload topic
docker exec -it opendt-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dc.workload \
  --from-beginning \
  --max-messages 10

# Consume from topology topic (compacted)
docker exec -it opendt-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dc.topology \
  --from-beginning
```

## Testing

```bash
# Run tests
cd services/dc-mock
pytest

# Run specific test
pytest tests/test_producers.py::test_workload_producer
```

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md) - System design
- [Data Models](../../docs/DATA_MODELS.md) - Message formats
- [Simulation Worker](../sim-worker/README.md) - Consumer of these messages
