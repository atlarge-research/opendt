# sim-worker Service

The **sim-worker** is the core simulation engine of OpenDT. It consumes workload and topology streams from Kafka, aggregates tasks into time windows, invokes the OpenDC simulator, and outputs power consumption predictions.

## Overview

**Purpose**: Bridge between Kafka streams and OpenDC simulator  
**Type**: Kafka Consumer + Simulation Orchestrator  
**Language**: Python 3.11+  
**External Dependencies**: OpenDC (Java-based simulator)

## Key Features

- ✅ Event-time windowing with heartbeat-driven closing
- ✅ Cumulative simulation (re-simulates from beginning each window)
- ✅ Result caching (topology hash + task count)
- ✅ Multiple operating modes (normal, debug, experiment)
- ✅ Topology management (real vs. simulated)
- ✅ Automatic plot generation (experiment mode)
- ✅ OpenDC I/O archiving for reproducibility

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      sim-worker                             │
│                                                             │
│  ┌──────────────┐     ┌─────────────────┐                   │
│  │   Kafka      │────>│ Window Manager  │                   │
│  │   Consumer   │     │  - Aggregation  │                   │
│  │              │     │  - Heartbeats   │                   │
│  │ Topics:      │     │  - Closing      │                   │
│  │  - workload  │     └────────┬────────┘                   │
│  │  - topology  │              │                            │
│  │  - sim.topo  │              v                            │
│  │  - power     │     ┌─────────────────┐                   │
│  └──────────────┘     │ OpenDC Runner   │                   │
│                       │  - Parquet I/O  │                   │
│                       │  - Subprocess   │                   │
│                       │  - Parsing      │                   │
│                       └────────┬────────┘                   │
│                                │                            │
│                                v                            │
│                       ┌─────────────────┐                   │
│                       │ Result Cache    │                   │
│                       │ Experiment Mgr  │                   │
│                       └────────┬────────┘                   │
│                                │                            │
│                                v                            │
│                ┌───────────────┴───────────────┐            │
│                │                               │            │
│          Kafka Topic                     Local Files        │
│          sim.results                  (debug/experiment)    │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Main Worker (`main.py`)

**Responsibilities**:
- Kafka consumer event loop
- Message routing (workload, topology, sim.topology, power)
- Window lifecycle management
- Mode selection (normal/debug/experiment)
- Coordination between components

**Key Classes**:
- `SimulationWorker`: Main orchestrator

### 2. OpenDC Runner (`runner/opendc_runner.py`)

**Responsibilities**:
- Convert Pydantic models to OpenDC input formats
- Invoke OpenDC binary via subprocess
- Parse OpenDC output Parquet files
- Return structured results with timeseries

**Key Classes**:
- `OpenDCRunner`: Simulation invocation and I/O
- `SimulationResults`: Structured output model
- `TimeseriesData`: Power/CPU timeseries points

**Input Files Created**:
- `experiment.json` - OpenDC experiment configuration
- `topology.json` - Datacenter topology
- `tasks.parquet` - Task definitions (int32 IDs, non-nullable)
- `fragments.parquet` - Task execution profiles

**Output Files Parsed**:
- `powerSource.parquet` - Power consumption over time
- `host.parquet` - Host-level metrics
- `service.parquet` - Service-level metrics

### 3. Window Manager (`window_manager.py`)

**Responsibilities**:
- Event-time windowing based on task submission timestamps
- Contiguous window creation (no gaps)
- Heartbeat-based window closing
- Task accumulation per window
- Topology tracking

**Key Classes**:
- `TimeWindow`: Individual window with tasks and metadata
- `WindowManager`: Window lifecycle management

**Windowing Logic**:
```
First task at 22:13:15 → Create window [22:13:00 - 22:18:00)
Heartbeat at 22:18:00 → Close window 0, create window 1 [22:18:00 - 22:23:00)
Task at 22:31:45 → Close windows 1-3, create window 4 [22:28:00 - 22:33:00)
```

### 4. Result Cache (`result_cache.py`)

**Responsibilities**:
- Cache simulation results based on inputs
- Avoid redundant OpenDC invocations
- Invalidate cache on topology changes

**Caching Strategy**:
```python
cache_key = SHA256(topology_json) + cumulative_task_count

if cache.can_reuse(topology, task_count):
    return cache.get_cached_results()
else:
    results = run_simulation(...)
    cache.update(topology, task_count, results)
```

**Invalidation**:
- When simulated topology updated via API
- Cache cleared manually via `cache.clear()`

### 5. Experiment Manager (`experiment_manager.py`)

**Responsibilities** (Experiment Mode Only):
- Record actual power from `dc.power`
- Write simulation results to Parquet
- Archive OpenDC I/O files per window
- Generate power comparison plots

**Output Structure**:
```
output/
└── my_experiment/
    └── run_1/
        ├── results.parquet
        ├── power_plot.png
        └── opendc/
            └── window_0000/
                ├── input/
                │   ├── summary.json
                │   ├── experiment.json
                │   ├── topology.json
                │   ├── tasks.parquet
                │   └── fragments.parquet
                └── output/
                    ├── summary.json
                    ├── powerSource.parquet
                    ├── host.parquet
                    └── service.parquet
```

## Simulation Flow

### 1. Task Ingestion

```python
# WorkloadMessage received from dc.workload
message = {
    "message_type": "task",  # or "heartbeat"
    "timestamp": "2022-10-07T00:39:21",
    "task": { /* Task object */ }
}

# Route to window manager
window_manager.add_task(task)
```

### 2. Window Closing

```python
# Heartbeat received
heartbeat = {
    "message_type": "heartbeat",
    "timestamp": "2022-10-07T00:45:00"
}

# Close all windows ending before heartbeat timestamp
closed_windows = window_manager.close_windows_before(heartbeat.timestamp)

# Process each closed window
for window in closed_windows:
    process_window(window)
```

### 3. Simulation Invocation

```python
# Collect cumulative tasks (all from beginning)
all_tasks = []
for w in windows[0:current_window_id + 1]:
    all_tasks.extend(w.tasks)

# Check cache
if result_cache.can_reuse(simulated_topology, len(all_tasks)):
    results = result_cache.get_cached_results()
    logger.info("✅ Using cached results")
else:
    # Run OpenDC
    results = opendc_runner.run_simulation(
        tasks=all_tasks,
        topology=simulated_topology,
        experiment_name=f"window-{window.window_id}-simulated"
    )
    result_cache.update(simulated_topology, len(all_tasks), results)
```

### 4. Result Handling

**Normal Mode**:
```python
# Publish to Kafka
send_message(
    producer=producer,
    topic="sim.results",
    message=results.model_dump(mode="json")
)
```

**Debug Mode**:
```python
# Write to local files
output_dir = f"output/run-{worker_id}-{timestamp}/window_{window_id:04d}/"
Path(output_dir).mkdir(parents=True, exist_ok=True)

with open(output_dir / "results.json", "w") as f:
    json.dump(results.model_dump(mode="json"), f, indent=2)
```

**Experiment Mode**:
```python
# Write to parquet + generate plot
experiment_manager.write_simulation_results(window, results, all_tasks)
experiment_manager.archive_opendc_files(window, results, all_tasks)
experiment_manager.generate_power_plot()
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_FILE` | Path to YAML configuration | `/app/config/simulation.yaml` |
| `WORKER_ID` | Unique worker identifier | `worker-1` |
| `CONSUMER_GROUP` | Kafka consumer group | `sim-workers` |
| `DEBUG_MODE` | Enable debug mode | `false` |
| `EXPERIMENT_NAME` | Experiment identifier | `default` |
| `EXPERIMENT_OUTPUT_DIR` | Experiment output path | `/app/output` |

### YAML Configuration

**File**: `config/default.yaml`

```yaml
simulation:
  window_size_minutes: 5
  heartbeat_cadence_minutes: 1
  experiment_mode: false  # Set true for experiment mode

kafka:
  bootstrap_servers: "kafka:29092"
  topics:
    workload:
      name: "dc.workload"
    topology:
      name: "dc.topology"
    sim_topology:
      name: "sim.topology"
    power:
      name: "dc.power"
    results:
      name: "sim.results"
```

## Operating Modes

### Normal Mode

```bash
make up
```

- Publishes results to Kafka
- No local files
- Production mode

### Debug Mode

```bash
make up-debug
```

- Writes JSON files per window
- No Kafka publishing
- Development mode

### Experiment Mode

```bash
make experiment name=my_experiment
```

- Writes Parquet + plots
- Archives OpenDC I/O
- Research mode

## OpenDC Integration

### Binary Location

```
services/sim-worker/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner
```

### Java Requirements

- **Version**: OpenJDK 21
- **JAVA_HOME**: Auto-detected at runtime
  - macOS: `/usr/libexec/java_home`
  - Linux: `/usr/lib/jvm/java-21-openjdk-amd64`

### Invocation

```python
result = subprocess.run(
    [opendc_binary, "--experiment-path", experiment_json_path],
    env={"JAVA_HOME": detected_java_home},
    capture_output=True,
    text=True,
    timeout=120
)
```

### Input Schema

**experiment.json**:
```json
{
  "name": "window-0-simulated",
  "topologies": [{"pathToFile": "/tmp/opendc-.../topology.json"}],
  "workloads": [{
    "pathToFile": "/tmp/opendc-.../workload",
    "type": "ComputeWorkload"
  }],
  "exportModels": [{
    "exportInterval": 150,
    "filesToExport": ["powerSource", "host", "task", "service"],
    "computeExportConfig": {
      "powerSourceExportColumns": ["energy_usage", "power_draw"]
    }
  }],
  "outputFolder": "/tmp/opendc-.../output"
}
```

### Output Parsing

```python
# Read powerSource.parquet for timeseries
power_table = pq.read_table(output_dir / "powerSource.parquet")
power_df = power_table.to_pandas()

# Extract energy and power
energy_kwh = power_df["energy_usage"].sum() / 3_600_000
max_power = power_df["power_draw"].max()

# Build timeseries
power_draw_series = [
    TimeseriesData(timestamp=int(row["timestamp"]), value=float(row["power_draw"]))
    for _, row in power_df.iterrows()
]
```

## Running

### Via Docker Compose

```bash
# Start all services
make up

# View sim-worker logs
make logs-sim-worker

# Execute command in container
docker compose exec sim-worker bash
```

### Standalone (Development)

```bash
cd services/sim-worker
source ../../.venv/bin/activate

# Set environment
export CONFIG_FILE=../../config/default.yaml
export WORKER_ID=dev-worker
export EXPERIMENT_OUTPUT_DIR=../../output

# Run worker
python -m sim_worker.main
```

### Testing

```bash
cd services/sim-worker
pytest tests/

# Run specific test
pytest tests/test_opendc_simple.py -v

# With detailed logs
pytest tests/ -o log_cli=true -o log_cli_level=DEBUG
```

## Monitoring

### Logs

```bash
# Tail logs
docker compose logs -f sim-worker

# Expected output:
# INFO - Initialized SimulationWorker 'worker-1'
# INFO - Subscribed: dc.workload, dc.topology, sim.topology
# INFO - 📦 Created window 0: [2022-10-07 00:00:00 - 2022-10-07 00:05:00)
# INFO - 🔒 Closed window 0 with 42 tasks
# INFO - Running simulation for window 0 with 42 cumulative tasks
# INFO - ✅ Simulation (simulated) for window 0: energy=1.649 kWh
```

### Metrics

```bash
# Check window statistics (from logs)
docker compose logs sim-worker | grep "Stats:"

# Output:
# INFO - 📊 Stats: 314 tasks processed, 35 windows simulated
```

### Kafka Lag

```bash
# Check consumer lag
docker exec -it opendt-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group sim-workers
```

## Troubleshooting

### Issue: "OpenDC simulation failed with exit code 1"

**Cause**: Invalid input data or topology

**Solution**:
1. Enable debug mode: `make up-debug`
2. Check `output/run-*/window_*/tasks.json` for task data
3. Verify topology structure
4. Check OpenDC logs in sim-worker container

### Issue: "JAVA_HOME is set to an invalid directory"

**Cause**: Java not installed or wrong path

**Solution**:
```bash
# Check Java in container
docker compose exec sim-worker java -version

# Should show: openjdk version "21"

# If missing, rebuild:
make down
make up build=true
```

### Issue: Windows staying open indefinitely

**Cause**: No heartbeats or heartbeat cadence too long

**Solution**:
```yaml
# In config file
simulation:
  heartbeat_cadence_minutes: 1  # Decrease if needed
```

### Issue: Cache not working (redundant simulations)

**Cause**: Topology changing between windows

**Solution**:
```bash
# Check logs for cache hits
docker compose logs sim-worker | grep "cached"

# Verify topology stability
docker exec -it opendt-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic sim.topology \
  --from-beginning
```

## Performance

### Throughput

- **Windows/minute**: ~10-20 (depends on OpenDC speed)
- **OpenDC invocation time**: ~2-5 seconds per window
- **Caching improvement**: 95%+ time savings when topology stable

### Resource Usage

- **Memory**: ~1-2 GB (includes OpenDC subprocess)
- **CPU**: Medium (OpenDC is CPU-intensive during simulation)
- **Disk**: Variable (experiment mode creates large archives)

### Optimization Tips

1. **Enable caching**: Ensure topology doesn't change unnecessarily
2. **Longer windows**: Use 15-minute windows for fewer simulations
3. **Increase heartbeat cadence**: Reduce Kafka message overhead
4. **Parquet compression**: Reduces I/O time

## Development

### Adding New Features

**To modify windowing logic**:
1. Edit `sim_worker/window_manager.py`
2. Update `TimeWindow` or `WindowManager` classes
3. Add tests in `tests/test_window_manager.py`

**To change OpenDC invocation**:
1. Edit `sim_worker/runner/opendc_runner.py`
2. Update input file generation or output parsing
3. Test with `tests/test_opendc_simple.py`

**To add new operating mode**:
1. Add mode flag to `SimulationWorker.__init__`
2. Implement result handling in `_handle_results`

### Code Structure

```
sim_worker/
├── __init__.py
├── main.py                  # Main worker + Kafka integration
├── window_manager.py        # Windowing logic
├── result_cache.py          # Caching mechanism
├── experiment_manager.py    # Experiment mode logic
└── runner/
    ├── __init__.py
    ├── opendc_runner.py     # OpenDC invocation
    ├── models.py            # Result models
    └── java_home.py         # Java detection
```

## Related Documentation

- [Architecture Overview](../../docs/ARCHITECTURE.md) - System design
- [Data Models](../../docs/DATA_MODELS.md) - Input/output schemas
- [dc-mock Service](../dc-mock/README.md) - Data producer
- [opendt-api Service](../opendt-api/README.md) - Topology management

---

For questions or contributions, see the [Contributing Guide](../../CONTRIBUTING.md).
