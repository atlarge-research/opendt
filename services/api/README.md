# api

REST API for querying simulation data and controlling the datacenter topology.

## Access

- **API Docs (Swagger):** http://localhost:3001/docs
- **API Docs (ReDoc):** http://localhost:3001/redoc
- **Health Check:** http://localhost:3001/health

## Endpoints

### GET /health

Service health status.

### GET /api/power

Query aligned power data from simulation and actual consumption.

**Parameters:**
- `interval_seconds` (int, default: 60) - Sampling interval
- `start_time` (datetime, optional) - Start time filter

**Returns:** Timeseries of `timestamp`, `simulated_power`, `actual_power`

### GET /api/co2_emission

Query carbon emission data based on power draw and grid carbon intensity.

**Parameters:**
- `interval_seconds` (int, default: 60) - Sampling interval
- `start_time` (datetime, optional) - Start time filter

**Returns:** Timeseries of `timestamp`, `carbon_emission`

### PUT /api/topology

Update the simulated datacenter topology.

Publishes the new topology to `sim.topology` Kafka topic. The simulator will use this topology for future simulations.

### The screens and the control panel

What the Grafana screens read, in Infinity's `{"data": [...]}` form, from the twin's windows of operation
(`api/twin.py`), and how the control panel changes the twin (`api/levers.py`):

- `GET /api/status`: the twin's time, hosts, CO₂ zone, scheduler, and runtime settings, as one object
- `PATCH /api/control`: hosts, CO₂ zone (a new topology), scheduler, speed factor, parallel runs (`sys.config`)
- `GET /api/cluster?start&end&points`: hosts, jobs, CPU, idle power, energy, and CO₂ per sample
- `GET /api/totals?period`: energy, CO₂, and embodied CO₂ per minute, hour, day, week, month, or year
- `GET /api/scheduling`: per window, the time until all jobs are done and the median time in queue
- `GET /api/jobs`: the jobs not done yet, with the hours left
- `GET /api/arrivals`: the jobs submitted per hour
- `GET /api/events?markers`: the decisions (hosts, r, CO₂ zone, scheduler), automatic or manual
- `GET /api/servers`, `GET /api/server_kinds`: the host groups now, and the kinds to choose from
- `GET /api/accuracy?minutes`: the MAPE and the error of OpenDT's power vs. the ground truth, and r

## Data Sources

The API reads from:
- `data/<RUN_ID>/simulator/agg_results.parquet` - Simulation results
- `workload/<WORKLOAD>/consumption.parquet` - Actual power data

## Logs

```
make logs-api
```
