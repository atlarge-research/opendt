---
sidebar_position: 4
---

# api

REST API for querying simulation data and controlling the running twin.

## Access

| URL | Description |
|-----|-------------|
| http://localhost:3001/docs | API Documentation (Swagger) |
| http://localhost:3001/redoc | API Documentation (ReDoc) |
| http://localhost:3001/health | Health check endpoint |

## Endpoints

### GET /health

Service health status.

### GET /api/power

Query aligned power data from simulation and actual consumption.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| interval_seconds | int | 60 | Sampling interval, from 1 to 3,600 |
| start_time | datetime | - | Start time filter (optional) |

**Returns:** Timeseries of `timestamp`, `simulated_power`, `actual_power`

### GET /api/co2_emission

Query carbon emission data based on power draw and grid carbon intensity.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| interval_seconds | int | 60 | Sampling interval, from 1 to 3,600 |
| start_time | datetime | - | Start time filter (optional) |

**Returns:** Timeseries of `timestamp`, `carbon_intensity` [gCO2/kWh], `power_draw` [W], and `carbon_emission` [gCO2/h]

### PUT /api/topology

Update the simulated datacenter topology.

Publishes the new topology to the `sim.topology` Kafka topic. The simulator runs it from its next window of operation.

### Endpoints of the Dashboard

The screens in Grafana read and change the twin through these endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/progress | While the twin starts: the step it is at and a tip |
| GET | /api/status | The control panel's values: the twin's time and topology, and the runtime settings |
| PATCH | /api/control | Change the running twin (fields below) |
| GET | /api/cluster | Hosts, jobs, CPU of the hosts, energy, and CO2, over time (`start`, `end`, `points`) |
| GET | /api/totals | Energy [kWh], CO2 [kg], and embodied CO2 [kg] per period |
| GET | /api/scheduling | Per window: the hours until all jobs submitted so far are done, and the median time in queue |
| GET | /api/jobs | The jobs not done yet, with their predicted start and finish |
| GET | /api/events | Changes of servers, r, carbon zone, and scheduler, for the markers on the graphs |
| GET | /api/arrivals | Jobs submitted per hour |
| GET | /api/accuracy | Per period: the MAPE [%] and the mean error [kW] of OpenDT's power vs. the ground truth, and r |
| GET, POST | /api/hosts | The host groups of the Topology table; POST saves a row (changed, added, or removed) |
| GET | /api/components | The names the Topology tables' lists offer (CPUs, GPUs, racks) |
| GET, POST | /api/prefabs | The prefab CPUs, GPUs, and racks; POST saves a row |

`PATCH /api/control` takes any of these fields; the fields left out stay as they are:

| Field | Description |
|-------|-------------|
| hosts | Hosts of the first host group |
| carbon_zone | Carbon zone of the power source (NL, DE, PL, RO) |
| scheduler | OpenDC's placement scheduler (e.g., Mem, CoreMem, ActiveServers) |
| speed_factor | Replay speed (above 0, or -1 for maximum) |
| parallel_simulations | Parallel runs of the calibrator |
| calibration | Calibration on or off |
| calibration_min, calibration_max | The range of r the calibrator tries |
| calibration_points | The values of r in that range |
| mape_window | Minutes of power the MAPE is computed over |

## Data Sources

The API reads from:

- `data/<RUN_ID>/simulator/agg_results.parquet` - Simulation results
- `data/<RUN_ID>/simulator/opendc/run_<N>/` - The OpenDC output of each window of operation (the screens)
- `workload/<WORKLOAD>/consumption.parquet` - Actual power data
- `workload/<WORKLOAD>/tasks.parquet` - The jobs of the trace
- `data/prefabs.json` - The prefabs as edited (without it, the shipped `services/api/api/prefabs.yaml`)

## Logs

```bash
make logs-api
```
