---
sidebar_position: 1
---

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

**Task message**: Contains task data for the simulator to process.

**Heartbeat message**: Signals time progression, enabling window closing even during sparse workload periods.

### Power Messages

Published to `dc.power` with actual power measurements from the workload.

### Topology Messages

Published to `dc.topology` (compacted topic) with the datacenter hardware configuration.

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| workload | string | "SURF" | Workload directory under `workload/` |
| heartbeat_frequency_minutes | int | 1 | Heartbeat interval in simulation time |

Lower heartbeat frequency provides more granular window closing but increases Kafka message volume.

## Logs

```bash
make logs-dc-mock
```
