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

## Data Sources

The API reads from:
- `data/<RUN_ID>/simulator/agg_results.parquet` - Simulation results
- `workload/<WORKLOAD>/consumption.parquet` - Actual power data

## Logs

```
make logs-api
```
