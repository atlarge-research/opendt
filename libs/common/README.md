# odt_common

Shared library containing Pydantic models, configuration, and utilities used across OpenDT services.

## Installation

```
pip install -e libs/common
```

Or with test dependencies:

```
pip install -e "libs/common[test]"
```

## Contents

### Models (`odt_common.models`)

Pydantic v2 models for data validation and serialization.

| Model | File | Description |
|-------|------|-------------|
| Task | task.py | Workload task submission |
| Fragment | fragment.py | Task execution segment |
| Consumption | consumption.py | Power consumption measurement |
| Topology | topology.py | Datacenter topology (clusters, hosts, CPUs) |
| WorkloadMessage | workload_message.py | Kafka message wrapper |

### Configuration (`odt_common.config`)

Configuration loading from YAML files.

```python
from odt_common import load_config_from_env

config = load_config_from_env()
print(config.workload)  # "SURF"
print(config.kafka.bootstrap_servers)  # "kafka:29092"
```

### Utilities (`odt_common.utils`)

Kafka producer/consumer helpers.

```python
from odt_common.utils import get_kafka_producer, get_kafka_consumer
from odt_common.utils.kafka import send_message
```

### OpenDC Runner (`odt_common.odc_runner`)

OpenDC binary invocation and result parsing.

```python
from odt_common.odc_runner import OpenDCRunner

runner = OpenDCRunner()
results = runner.run_simulation(tasks, topology)
```

### Task Accumulator (`odt_common.task_accumulator`)

Window-based task accumulation for simulation.

### Result Cache (`odt_common.result_cache`)

Caching layer to avoid redundant simulations.

## Testing

```
cd libs/common
pytest tests/
```
