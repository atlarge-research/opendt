# Simulation Worker Service

The `sim-worker` service is the core simulation engine of OpenDT. It consumes workload and topology streams from Kafka, aggregates tasks into time windows, and runs the OpenDC simulator to predict power consumption.

## Architecture

The sim-worker consists of three main components:

### 1. OpenDC Runner (`opendc_runner.py`)

A wrapper around the OpenDC ExperimentRunner binary that:
- Converts Pydantic models (Task, Fragment, Topology) to OpenDC input formats (Parquet and JSON)
- Invokes the OpenDC Java binary
- Parses simulation results from output Parquet files
- Returns structured metrics (energy consumption, CPU utilization, power draw, runtime)

### 2. Window Manager (`window_manager.py`)

A time-based windowing system that:
- Aggregates incoming tasks into fixed-duration windows (default: 5 minutes)
- Uses **event time** (task submission_time) rather than processing time
- Automatically closes windows when tasks arrive beyond the window boundary
- Maintains cumulative task history for progressive simulation
- Tracks topology updates and applies them to open windows

**Window Lifecycle:**
```
Window 0: [00:00 - 00:05)  ← First task at 00:03:15 creates this window
Window 1: [00:05 - 00:10)  ← Task at 00:05:00 closes Window 0, creates Window 1
Window 2: [00:10 - 00:15)  ← Task at 00:12:30 closes Window 1, creates Window 2
```

### 3. Simulation Worker (`main.py`)

The main event loop that:
- Consumes from `dc.workload` and `dc.topology` Kafka topics
- Feeds tasks to the window manager
- Runs simulations when windows close (via callback)
- Maintains two topology states:
  - **Real topology**: The actual datacenter configuration from `dc.topology`
  - **Simulated topology**: An operator-defined "what-if" scenario (initially same as real)
- Publishes results to `sim.results` topic

## Simulation Logic

When a window closes, the worker:

1. **Aggregates tasks**: Collects all tasks from window 0 up to the closed window (cumulative)
2. **Runs real simulation**: Simulates with the real topology from `dc.topology`
3. **Runs simulated scenario**: (Optional) Simulates with the operator's hypothetical topology
4. **Publishes results**: Sends both results to Kafka for comparison

This allows for "shadow mode" comparison: real vs. predicted power consumption under different configurations.

## Configuration

The service uses the shared `opendt_common.config` system:

```yaml
simulation:
  window_size_minutes: 5  # Time window duration

kafka:
  bootstrap_servers: "kafka:29092"
  topics:
    workload:
      name: "dc.workload"
    topology:
      name: "dc.topology"
```

Additional environment variables:
- `WORKER_ID`: Unique worker identifier (default: "worker-1")
- `CONSUMER_GROUP`: Kafka consumer group (default: "sim-workers")
- `CONFIG_FILE`: Path to YAML config file

## Input Schema

### Workload Messages (`dc.workload`)

```json
{
  "id": 2132895,
  "submission_time": "2022-10-07T00:39:21",
  "duration": 12000,
  "cpu_count": 16,
  "cpu_capacity": 3360.0,
  "mem_capacity": 100000,
  "fragments": [
    {
      "id": 2132895,
      "duration": 30000,
      "cpu_count": 16,
      "cpu_usage": 147.0
    }
  ]
}
```

### Topology Messages (`dc.topology`)

```json
{
  "timestamp": "2022-10-07T09:14:30",
  "topology": {
    "clusters": [
      {
        "name": "A01",
        "hosts": [
          {
            "name": "A01-Host",
            "count": 277,
            "cpu": {
              "coreCount": 16,
              "coreSpeed": 2100
            },
            "memory": {
              "memorySize": 128000000
            },
            "cpuPowerModel": {
              "modelType": "asymptotic",
              "power": 400.0,
              "idlePower": 32.0,
              "maxPower": 180.0,
              "asymUtil": 0.3,
              "dvfs": false
            }
          }
        ]
      }
    ]
  }
}
```

## Output Schema

Published to `sim.results`:

```json
{
  "worker_id": "worker-1",
  "window_id": 0,
  "window_start": "2022-10-07T00:00:00",
  "window_end": "2022-10-07T00:05:00",
  "task_count": 42,
  "timestamp": "2024-01-15T10:30:00",
  "real_topology": {
    "energy_kwh": 1.2345,
    "cpu_utilization": 0.65,
    "max_power_draw": 5432.1,
    "runtime_hours": 0.083,
    "status": "success"
  },
  "simulated_topology": {
    "energy_kwh": 1.1234,
    "cpu_utilization": 0.62,
    "max_power_draw": 5123.4,
    "runtime_hours": 0.083,
    "status": "success"
  }
}
```

## OpenDC Integration

The service requires the OpenDC binaries to be available at:
```
/app/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner
```

### Java Requirements
- Java 21 (OpenJDK)
- `JAVA_HOME` set to `/usr/lib/jvm/java-21-openjdk-amd64`

The Dockerfile includes these dependencies automatically.

## Development

### Local Testing

```bash
# Build the service
docker compose build sim-worker

# Run with logs
docker compose up sim-worker

# Check simulation results
docker compose exec sim-worker ls -la /app/output/
```

### Adding New Features

To modify the simulation logic:
1. Update `opendc_runner.py` for OpenDC invocation changes
2. Update `window_manager.py` for windowing logic changes
3. Update `main.py` for Kafka integration or topology management changes

## Future Enhancements

1. **Dynamic Topology Updates**: Allow operators to update the simulated topology via API/Kafka
2. **Persistent Windows**: Store window state in Redis for fault tolerance
3. **Distributed Workers**: Scale horizontally with Kafka partitioning
4. **Adaptive Windows**: Dynamically adjust window size based on workload intensity
5. **Historical Replay**: Support replaying historical data at arbitrary speeds
