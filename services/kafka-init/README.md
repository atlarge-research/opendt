# kafka-init

Creates and configures Kafka topics before application services start.

## Purpose

kafka-init is an initialization container that ensures all required Kafka topics exist with proper retention and compaction settings. It runs once and exits, blocking other services until topics are ready.

## Topics Created

| Topic | Type | Retention | Purpose |
|-------|------|-----------|---------|
| dc.workload | Stream | 24 hours | Task submissions and heartbeats |
| dc.power | Stream | 1 hour | Power consumption telemetry |
| dc.topology | Compacted | - | Real datacenter topology |
| sim.topology | Compacted | - | Calibrated topology |
| sim.results | Stream | 7 days | Simulation predictions |
| sys.config | Compacted | - | Runtime configuration |

### Topic Types

**Stream topics:** Retain all messages for a configured duration. Used for event data.

**Compacted topics:** Keep only the latest value per key. Used for state data (topology, configuration).

## Configuration

Topics are configured in the main config file under `kafka.topics`:

```yaml
kafka:
  topics:
    workload:
      name: "dc.workload"
      config:
        retention.ms: "86400000"
```

## Startup Flow

1. Wait for Kafka to be healthy (with retries)
2. Create topics if they don't exist
3. Apply topic configurations
4. Exit with code 0 (success) or 1 (failure)

Other services wait for kafka-init to complete before starting.

## Logs

```
docker compose logs kafka-init
```

## Related

- [Configuration](../../docs/CONFIGURATION.md) - Topic configuration reference
