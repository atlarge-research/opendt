---
sidebar_position: 1
---

# dc-mock

Simulates a datacenter by replaying historical workload and power data to Kafka.

## Purpose

dc-mock acts as the data source for OpenDT. It reads Parquet files from the configured workload directory and publishes messages to Kafka topics at the replay speed: `global.speed_factor` at the start (1 real time, -1 maximum),
then each change from the control panel, continuing from where the replay is.

## Data Sources

Reads from `workload/<WORKLOAD_NAME>/`:

| File | Topic | Description |
|------|-------|-------------|
| tasks.parquet + fragments.parquet | dc.workload | Task submissions with execution profiles |
| consumption.parquet | dc.power | Power consumption telemetry (timestamps plus `consumption_offset_ms` from `workload.yaml`) |
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
| workload | string | - | Required: workload directory under `workload/` (e.g., "SURF") |
| heartbeat_frequency_minutes | int | 1 | Heartbeat interval in simulation time |

Lower heartbeat frequency provides more granular window closing but increases Kafka message volume.

## Logs

```bash
make logs-dc-mock
```
