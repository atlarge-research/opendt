# Kafka Infrastructure Initialization Service

This service is responsible for initializing Kafka infrastructure before application services start.

## Purpose

- Creates Kafka topics based on configuration in `config/default.yaml`
- Applies topic-specific settings (partitions, replication factor, retention policies)
- Ensures topics are ready before producer/consumer services start
- Fails fast if topic creation fails (exit code 1)

## Configuration

Topics are defined in `config/default.yaml`:

```yaml
kafka:
  bootstrap_servers: "kafka:29092"
  topics:
    workload:
      name: "dc.workload"
      partitions: 1
      replication_factor: 1
      config:
        retention.ms: "86400000"  # 24h
    power:
      name: "dc.power"
      partitions: 4
      config:
        retention.ms: "3600000"  # 1h
```

## Dependencies

- `opendt_common`: Shared configuration and Kafka utilities
- `kafka-python`: Kafka admin client
- `pydantic`: Configuration validation

## Usage

This service runs automatically via Docker Compose before other services start:

```yaml
depends_on:
  kafka-init:
    condition: service_completed_successfully
```

## Exit Codes

- `0`: Success - all topics created
- `1`: Failure - topic creation failed
