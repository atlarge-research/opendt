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
```json
{
  "message_type": "task",
  "timestamp": "2022-10-07T00:39:21",
  "task": { ... }
}
```

**Heartbeat message:**
```json
{
  "message_type": "heartbeat",
  "timestamp": "2022-10-07T00:45:00",
  "task": null
}
```

Heartbeats signal time progression to downstream consumers, enabling deterministic window closing.

### Power Messages

Published to `dc.power`:
```json
{
  "power_draw": 19180.0,
  "energy_usage": 575400.0,
  "timestamp": "2022-10-08T06:35:30"
}
```

### Topology Messages

Published to `dc.topology` (compacted topic):
```json
{
  "timestamp": "2022-10-07T09:14:30",
  "topology": { ... }
}
```

## Configuration

From the main config file:

```yaml
global:
  speed_factor: 300  # Simulation speed multiplier

services:
  dc-mock:
    workload: "SURF"  # Directory under workload/
    heartbeat_frequency_minutes: 1
```

### Speed Factor

| Value | Behavior |
|-------|----------|
| 1 | Real-time replay |
| 300 | 300x faster (1 hour = 12 seconds) |
| -1 | Maximum speed (no delays) |

## Logs

```
make logs-dc-mock
```

## Related

- [Concepts](../../docs/CONCEPTS.md) - Data model details
- [Configuration](../../docs/CONFIGURATION.md) - Full configuration reference
