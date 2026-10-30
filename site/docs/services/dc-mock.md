---
sidebar_position: 1
---

# dc-mock

Simulates a datacenter by replaying historical workload and power data to Kafka.

## Purpose

dc-mock acts as the data source for OpenDT. It publishes the workload's tasks, power, and topology to Kafka at
`global.speed_factor`; a speed change from the control panel applies from where the replay is.

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

Published to `dc.topology` (compacted topic) once, before the replay, with the datacenter hardware configuration.

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| workload | string | - | Required: workload directory under `workload/` (e.g., "SURF") |
| heartbeat_frequency_minutes | int | 1 | Heartbeat interval in simulation time |

A shorter heartbeat interval closes windows sooner but sends more Kafka messages. It must be at most the simulator's
`simulation_frequency_minutes`: a heartbeat closes one window at most, so a longer interval makes the twin fall behind.

## Logs

```bash
make logs-dc-mock
```
