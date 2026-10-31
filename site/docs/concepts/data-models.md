---
sidebar_position: 5
---

# Data Models

OpenDT uses Pydantic models, in `libs/common/odt_common/models/` (DynamicConfigEvent in `odt_common/config.py`), to
define the data flowing between the services:

| Model | File | Description | Topic |
|-------|------|-------------|-------|
| Task | task.py | A job: submission time, duration, CPUs, memory, and its fragments | - |
| Fragment | fragment.py | A segment of a task's execution: duration, CPUs, and CPU usage | - |
| (no model) | dc-mock's workload_producer.py | A task or a heartbeat: `message_type`, `timestamp`, and the task | `dc.workload` |
| Consumption | consumption.py | A power measurement, at an absolute time | `dc.power` |
| TopologySnapshot | topology.py | The datacenter's topology at a time | `dc.topology` |
| Topology | topology.py | Datacenter topology | `sim.topology` |
| DynamicConfigEvent | config.py | A runtime setting from the control panel | `sys.config` |

The models follow the files of [Workloads](/docs/configuration/workloads) and [Topology](/docs/configuration/topology),
with two differences: a fragment's `id` (its task) becomes `task_id`, and task ids become integers.
