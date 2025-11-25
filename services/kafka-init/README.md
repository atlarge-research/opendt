# kafka-init Service

The **kafka-init** service is an infrastructure initialization container that creates and configures Kafka topics before application services start. It ensures all required topics exist with proper retention, compaction, and partitioning settings.

## Overview

**Purpose**: Initialize Kafka infrastructure  
**Type**: Initialization Container (runs once and exits)  
**Language**: Python 3.11+  
**Dependencies**: kafka-python, opendt-common

## Responsibilities

1. **Wait for Kafka**: Retry connection until Kafka broker is ready
2. **Load Configuration**: Read topic definitions from YAML
3. **Create Topics**: Create all configured topics with settings
4. **Apply Policies**: Set retention, compaction, and other topic configs
5. **Fail Fast**: Exit with error if topic creation fails

## Architecture

```
┌────────────────────────────────────────────┐
│          kafka-init Container              │
│                                            │
│  1. Read config/default.yaml               │
│  2. Parse topic definitions                │
│  3. Connect to Kafka (with retries)        │
│  4. Create topics if not exist             │
│  5. Apply topic configurations             │
│  6. Exit (0 = success, 1 = failure)        │
│                                            │
│  Blocks other services until complete      │
└────────────────────────────────────────────┘
                     │
                     v
         ┌─────────────────────┐
         │   Kafka Broker      │
         │   Topics Created:   │
         │   • dc.workload     │
         │   • dc.power        │
         │   • dc.topology     │
         │   • sim.topology    │
         │   • sim.results     │
         │   • sys.config      │
         └─────────────────────┘
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to YAML configuration | `/app/config/simulation.yaml` |
| `PYTHONUNBUFFERED` | Unbuffered Python output | `1` |

### Topic Configuration

**File**: `config/default.yaml`

```yaml
kafka:
  bootstrap_servers: "kafka:29092"
  topics:
    workload:
      name: "dc.workload"
      config:
        retention.ms: "86400000"  # 24 hours
    
    power:
      name: "dc.power"
      config:
        retention.ms: "3600000"   # 1 hour
    
    topology:
      name: "dc.topology"
      config:
        cleanup.policy: "compact"
        min.compaction.lag.ms: "3600000"  # 1 hour
    
    sim_topology:
      name: "sim.topology"
      config:
        cleanup.policy: "compact"
        min.compaction.lag.ms: "0"  # Immediate compaction
    
    system:
      name: "sys.config"
      config:
        cleanup.policy: "compact"
    
    results:
      name: "sim.results"
      config:
        retention.ms: "604800000"  # 7 days
```

### Topic Types

**Stream Topics** (retention-based):
- `dc.workload` - Task submissions (24h retention)
- `dc.power` - Power telemetry (1h retention)
- `sim.results` - Simulation predictions (7d retention)

**Compacted Topics** (key-based):
- `dc.topology` - Real datacenter topology
- `sim.topology` - Simulated topology
- `sys.config` - Runtime configuration

## Implementation

### Main Flow

**File**: [`kafka_init/main.py`](./kafka_init/main.py)

```python
def main():
    # 1. Load configuration
    config = load_config_from_env()
    
    # 2. Wait for Kafka to be ready
    admin_client = wait_for_kafka(config)
    
    # 3. Create topics
    for topic_key, topic_config in config.kafka.topics.items():
        create_topic_if_not_exists(admin_client, topic_config)
    
    # 4. Exit successfully
    sys.exit(0)
```

### Kafka Connection Retry

```python
def wait_for_kafka(config, max_retries=30, retry_delay=2):
    """Wait for Kafka broker to be ready."""
    for attempt in range(max_retries):
        try:
            admin = KafkaAdminClient(
                bootstrap_servers=config.kafka.bootstrap_servers,
                client_id="kafka-init"
            )
            admin.list_topics()  # Test connection
            return admin
        except KafkaError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise
```

### Topic Creation

```python
def create_topic_if_not_exists(admin, topic_config):
    """Create topic with specified configuration."""
    topic_name = topic_config.name
    
    # Check if topic already exists
    existing_topics = admin.list_topics()
    if topic_name in existing_topics:
        logger.info(f"Topic {topic_name} already exists")
        return
    
    # Create topic with config
    new_topic = NewTopic(
        name=topic_name,
        num_partitions=topic_config.get("partitions", 1),
        replication_factor=topic_config.get("replication_factor", 1),
        topic_configs=topic_config.config or {}
    )
    
    admin.create_topics([new_topic])
    logger.info(f"✅ Created topic: {topic_name}")
```

## Running

### Via Docker Compose (Automatic)

```bash
# Start services (kafka-init runs automatically)
make up

# kafka-init runs before other services start
# It will exit once topics are created
```

### Check Status

```bash
# View kafka-init logs
docker compose logs kafka-init

# Expected output:
# INFO - Loading configuration from /app/config/simulation.yaml
# INFO - Connecting to Kafka at kafka:29092
# INFO - ✅ Created topic: dc.workload
# INFO - ✅ Created topic: dc.power
# INFO - ✅ Created topic: dc.topology
# INFO - ✅ Created topic: sim.topology
# INFO - ✅ Created topic: sys.config
# INFO - ✅ Created topic: sim.results
# INFO - All topics created successfully

# List created topics
make kafka-topics
# Or:
docker exec -it opendt-kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list
```

### Standalone (Development)

```bash
cd services/kafka-init
source ../../.venv/bin/activate

# Set environment
export CONFIG_FILE=../../config/default.yaml

# Run initialization
python -m kafka_init.main
```

### Verify Topic Configuration

```bash
# Describe specific topic
docker exec -it opendt-kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic dc.topology

# Output shows:
#   Topic: dc.topology
#   PartitionCount: 1
#   ReplicationFactor: 1
#   Configs: cleanup.policy=compact,min.compaction.lag.ms=3600000
```

## Docker Compose Integration

### Dependency Chain

```yaml
services:
  kafka-init:
    depends_on:
      kafka:
        condition: service_healthy
    restart: "no"  # Don't restart (runs once)
  
  dc-mock:
    depends_on:
      kafka-init:
        condition: service_completed_successfully
  
  sim-worker:
    depends_on:
      kafka-init:
        condition: service_completed_successfully
```

**Flow**:
1. Kafka starts and waits for health check
2. kafka-init starts and creates topics
3. kafka-init exits with code 0 (success)
4. Application services (dc-mock, sim-worker) start

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success - All topics created | Services start |
| 1 | Failure - Topic creation failed | Services blocked, check logs |

## Troubleshooting

### Issue: "Connection refused to Kafka"

**Cause**: Kafka not ready yet

**Solution**: kafka-init automatically retries for 60 seconds. Check Kafka logs:
```bash
docker compose logs kafka | grep "started"
```

### Issue: "Topic already exists"

**Cause**: Normal behavior if topics were created previously

**Solution**: No action needed. kafka-init skips existing topics.

### Issue: Services not starting after kafka-init

**Cause**: kafka-init exited with error (code 1)

**Solution**:
```bash
# Check kafka-init logs
docker compose logs kafka-init

# Look for error messages
# Common issues:
#  - Invalid topic config (fix config/default.yaml)
#  - Kafka permissions (check Kafka ACLs)
#  - Network issues (verify Docker network)

# Fix issue and restart
make down
make up
```

### Issue: "Invalid topic configuration"

**Cause**: Syntax error in `config/default.yaml`

**Solution**:
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/default.yaml'))"

# Check topic config format:
# - retention.ms must be string: "86400000"
# - cleanup.policy must be "delete" or "compact"
```

## Topic Configuration Reference

### Retention Policies

**Time-based retention** (stream topics):
```yaml
config:
  retention.ms: "86400000"  # Keep messages for 24 hours
```

**Size-based retention**:
```yaml
config:
  retention.bytes: "1073741824"  # Keep up to 1GB
```

**Compaction** (key-based retention):
```yaml
config:
  cleanup.policy: "compact"           # Keep latest value per key
  min.compaction.lag.ms: "3600000"    # Wait 1h before compacting
```

### Partitioning

```yaml
workload:
  name: "dc.workload"
  partitions: 4           # 4 partitions for parallel consumption
  replication_factor: 1   # 1 replica (single-broker cluster)
```

**Considerations**:
- More partitions = higher throughput
- Partitions enable parallel consumption
- Replication factor must be ≤ number of brokers

### Other Settings

```yaml
config:
  # Message size limits
  max.message.bytes: "10485760"  # 10MB max message

  # Compression
  compression.type: "gzip"

  # Segment rolling
  segment.ms: "86400000"  # New segment every 24h
```

## Development

### Adding a New Topic

1. **Update config**:
```yaml
# In config/default.yaml
kafka:
  topics:
    my_new_topic:
      name: "my.new.topic"
      config:
        retention.ms: "3600000"
```

2. **Update common library** (if needed):
```python
# In libs/common/opendt_common/config.py
class KafkaConfig(BaseModel):
    topics: dict[str, TopicConfig]
    
    class Topics:
        my_new_topic: TopicConfig
```

3. **Restart services**:
```bash
make down
make up
```

4. **Verify creation**:
```bash
make kafka-topics
# Should see "my.new.topic" in list
```

### Testing

```bash
# Test configuration parsing
python -m pytest libs/common/tests/test_config.py

# Test topic creation (requires Kafka)
docker compose up -d kafka
docker compose run --rm kafka-init
docker compose down
```

## Monitoring

### Logs

```bash
# View logs
docker compose logs kafka-init

# Successful run:
# INFO - Connecting to Kafka at kafka:29092
# INFO - ✅ Created topic: dc.workload
# INFO - ✅ Created topic: dc.power
# INFO - All topics created successfully

# Failed run:
# ERROR - Failed to create topic dc.workload: TopicExistsError
# ERROR - Topic creation failed
```

### Container Status

```bash
# Check if kafka-init completed successfully
docker compose ps kafka-init

# STATUS should show "exited (0)"
```
