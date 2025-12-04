---
sidebar_position: 3
---

# Running OpenDT

## Start the System

Start all services with the default configuration:

```bash
make up
```

Or specify a configuration file:

```bash
make up config=config/experiments/experiment_1.yaml
```

## Access the Dashboard

Once services are running:

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Grafana Dashboard |
| http://localhost:3001 | API Documentation |

The Grafana dashboard shows real-time power consumption data as the simulation progresses.

## Monitor Progress

View logs from a specific service:

```bash
make logs-simulator
make logs-dc-mock
make logs-api
make logs-calibrator
```

## Stop the System

Stop all running services:

```bash
make down
```

## Clean Up

Remove all data and volumes to start fresh:

```bash
make clean-volumes
```

This removes simulation results and resets Grafana to its initial state.
