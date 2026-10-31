# simulator

Core simulation engine that consumes workload data and produces power predictions using OpenDC.

- `simulator/main.py` - the service: one OpenDC run per window of operation
- `simulator/result_processor.py` - each window's power, appended to agg_results.parquet

What it reads and writes, its settings, and its logs: [simulator in the docs](https://atlarge-research.github.io/opendt/docs/services/simulator) (in the repository,
`site/docs/services/simulator.md`). Its tests run with the others: `make test`.
