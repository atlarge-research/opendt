# kafka-init

Creates and configures Kafka topics before application services start.

## Purpose

kafka-init creates the Kafka topics of the configuration, with their retention and compaction settings. It runs once and exits; dc-mock, the simulator, and the calibrator start after it.

## Topics Created

| Topic | Type | Retention | Purpose |
|-------|------|-----------|---------|
| dc.workload | Stream | 24 hours | Task submissions and heartbeats |
| dc.power | Stream | 1 hour | Power consumption telemetry |
| dc.topology | Compacted | - | Real datacenter topology |
| sim.topology | Compacted | - | Simulated topology: the calibrator's r and the dashboard's changes |
| sim.results | Stream | 7 days | Created, not used (the results are files in `data/<RUN_ID>/simulator/`) |
| sys.config | Compacted | - | Runtime settings from the control panel |

### Topic Types

**Stream topics:** Retain all messages for a configured duration. Used for event data.

**Compacted topics:** Keep only the latest value per key. Used for state data (topology, configuration).

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

## Startup Flow

1. Wait for Kafka to answer (30 attempts, 2 s apart); exit with 1 if it does not
2. Create the topics that do not exist yet, with their settings

dc-mock, the simulator, and the calibrator wait for kafka-init to complete; the API waits for Kafka's health check.

## Logs

```
docker compose logs kafka-init
```
