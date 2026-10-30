---
sidebar_position: 6
---

# kafka

Message broker for inter-service communication, at `kafka:29092` from the containers; it has no port on the host.

## Topics

| Topic | Type | Description |
|-------|------|-------------|
| dc.workload | Stream | Task submissions and heartbeats |
| dc.power | Stream | Power consumption telemetry |
| dc.topology | Compacted | Real datacenter topology |
| sim.topology | Compacted | Simulated topology: the calibrator's r and the dashboard's changes |
| sim.results | Stream | Created, not used (the results are files in `data/<RUN_ID>/simulator/`) |
| sys.config | Compacted | Runtime settings changed from the control panel (e.g., speed, scheduler, calibration) |

## Topic Types

**Stream topics** retain all messages for a configured duration. Used for event data that should be processed sequentially.

**Compacted topics** keep only the latest value per key. Used for state data like topology and configuration.

## kafka-init

The `kafka-init` container creates and configures topics before other services start. It runs once and exits, blocking dependent services until topics are ready; Kafka does not create topics on its own.

## Configuration

Topics are configured under `kafka.topics` in the config file. The services look them up by their keys (`workload`,
`power`, `topology`, `sim_topology`, `system`), so each topic's `name` and `config` may change, not its key:

```yaml
kafka:
  topics:
    workload:
      name: "dc.workload"
      config:
        retention.ms: "86400000"
    topology:
      name: "dc.topology"
      config:
        cleanup.policy: "compact"
```

### Topic Configuration Options

| Option | Description |
|--------|-------------|
| retention.ms | How long messages are retained (milliseconds) |
| cleanup.policy | "delete" (time-based) or "compact" (key-based) |
| min.compaction.lag.ms | Minimum time before compaction |
