# dc-mock

Simulates a datacenter by replaying historical workload and power data to Kafka.

## Purpose

dc-mock acts as the data source for OpenDT. It reads Parquet files from the configured workload directory and publishes messages to Kafka topics, respecting the configured speed factor.

## Data Sources

Reads from `workload/<WORKLOAD_NAME>/`:

| File | Topic | Description |
|------|-------|-------------|
| tasks.parquet + fragments.parquet | dc.workload | Task submissions with execution profiles |
| consumption.parquet | dc.power | Power consumption telemetry |
| topology.json | dc.topology | Datacenter hardware configuration |

## Message Types

### Workload Messages

Published to `dc.workload`. Two types:

**Task message:**
```
{
  "message_type": "task",
  "timestamp": "2022-10-07T00:39:21",
  "task": { <task object> }
}
```

**Heartbeat message:**
```
{
  "message_type": "heartbeat",
  "timestamp": "2022-10-07T00:45:00",
  "task": null
}
```

Heartbeats signal time progression to downstream consumers, enabling deterministic window closing.

### Power Messages

Published to `dc.power`:
```
{
  "power_draw": 19180.0,
  "energy_usage": 575400.0,
  "timestamp": "2022-10-08T06:35:30"
}
```

### Topology Messages

Published to `dc.topology` (compacted topic):
```
{
  "timestamp": "2022-10-07T09:14:30",
  "topology": { <topology object> }
}
```

## Configuration

Settings under `services.dc-mock` in the config file:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| workload | string | "SURF" | Workload directory name under `workload/` |
| heartbeat_frequency_minutes | int | 1 | Heartbeat interval in simulation time |

### heartbeat_frequency_minutes

Controls how often dc-mock publishes heartbeat messages. Lower values provide more granular window closing but increase Kafka message volume.

## Workload Data Format

Each workload directory must contain:

```
workload/SURF/
├── tasks.parquet       # Task definitions
├── fragments.parquet   # Task execution profiles
├── consumption.parquet # Actual power measurements
├── carbon.parquet      # Grid carbon intensity
└── topology.json       # Datacenter topology
```

To use a custom workload, create a directory with these files and set `services.dc-mock.workload` to the directory name.

## Logs

```
make logs-dc-mock
```
