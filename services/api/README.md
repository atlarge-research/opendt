# api

REST API for querying simulation data and controlling the datacenter topology; its documentation runs at http://localhost:3001/docs.

- `api/main.py` - the routes
- `api/twin.py` - the twin's run folder: windows, topology, accuracy
- `api/levers.py` - the control panel's changes
- `api/hosts.py` - the host groups of the Topology screen
- `api/prefabs.py` - the preconfigured components
- `api/power_query.py` - the simulated and measured power
- `api/carbon_query.py` - the CO2 emissions
- `api/startup.py` - the start screen's progress and tips

What it reads and writes, its settings, and its logs: [api in the docs](https://atlarge-research.github.io/opendt/docs/services/api) (in the repository,
`site/docs/services/api.md`). Its tests run with the others: `make test`.
