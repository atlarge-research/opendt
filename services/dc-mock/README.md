# dc-mock

Simulates a datacenter by replaying historical workload and power data to Kafka.

- `dc_mock/main.py` - the service: the topology, then the two producers
- `dc_mock/producers/workload_producer.py` - the tasks and heartbeats
- `dc_mock/producers/power_producer.py` - the measured power
- `dc_mock/producers/base.py` - the replay's clock, at the current speed
- `dc_mock/speed.py` - the speed, as the control panel changes it

What it reads and writes, its settings, and its logs: [dc-mock in the docs](https://atlarge-research.github.io/opendt/docs/services/dc-mock) (in the repository,
`site/docs/services/dc-mock.md`). Its tests run with the others: `make test`.
