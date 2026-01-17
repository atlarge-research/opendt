---
sidebar_position: 4
---

# api

REST API for querying simulation data and controlling the datacenter topology.

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
| interval_seconds | int | 60 | Sampling interval |
| start_time | datetime | - | Start time filter (optional) |

**Returns:** Timeseries of `timestamp`, `simulated_power`, `actual_power`

### GET /api/co2_emission

Query carbon emission data based on power draw and grid carbon intensity.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| interval_seconds | int | 60 | Sampling interval |
| start_time | datetime | - | Start time filter (optional) |

**Returns:** Timeseries of `timestamp`, `carbon_emission`

### PUT /api/topology

Update the simulated datacenter topology.

Publishes the new topology to `sim.topology` Kafka topic. The simulator will use this topology for future simulations.

## Data Sources

The API reads from:

- `data/<RUN_ID>/simulator/agg_results.parquet` - Simulation results
- `workload/<WORKLOAD>/consumption.parquet` - Actual power data

## Logs

```bash
make logs-api
```
