---
sidebar_position: 6
---

# kafka

Message broker for inter-service communication.

## Topics

| Topic | Type | Description |
|-------|------|-------------|
| dc.workload | Stream | Task submissions and heartbeats |
| dc.power | Stream | Power consumption telemetry |
| dc.topology | Compacted | Real datacenter topology |
| sim.topology | Compacted | Calibrated topology |
| sim.results | Stream | Simulation predictions |
| sys.config | Compacted | Runtime configuration |

## Topic Types

**Stream topics** retain all messages for a configured duration. Used for event data that should be processed sequentially.

**Compacted topics** keep only the latest value per key. Used for state data like topology and configuration.

## kafka-init

The `kafka-init` container creates and configures topics before other services start. It runs once and exits, blocking dependent services until topics are ready.

## Configuration

Topics are configured under `kafka.topics` in the config file:

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
