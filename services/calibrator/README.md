# calibrator

Optimizes topology parameters by comparing simulation output against actual power measurements.

- `calibrator/main.py` - the service: one sweep after the other
- `calibrator/calibration_engine.py` - the sweep: one OpenDC run per value
- `calibrator/mape_comparator.py` - the MAPE of a run against the measured power
- `calibrator/result_processor.py` - each sweep's records
- `calibrator/power_tracker.py` - the measured power, from Kafka
- `calibrator/topology_manager.py` - the topologies it reads and publishes

What it reads and writes, its settings, and its logs: [calibrator in the docs](https://atlarge-research.github.io/opendt/docs/services/calibrator) (in the repository,
`site/docs/services/calibrator.md`). Its tests run with the others: `make test`.
