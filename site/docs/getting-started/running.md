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

The first `make up` builds the Docker images, which takes a few minutes; `make up build=true` rebuilds them without
cache.

## Access the Dashboard

Once services are running:

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Grafana Dashboard |
| http://localhost:3001 | API Documentation |

Grafana opens on the Detailed screen: the power draw, CO₂ emissions, hosts, and the twin's accuracy, as the twin replays
the workload. The tabs at the top left switch to the Topology and Tutorial screens; see [grafana](/docs/services/grafana).

## Monitor Progress

View logs from a specific service:

```bash
make logs-simulator
make logs-dc-mock
make logs-api
make logs-calibrator
```

The calibrator runs only when the configuration has calibration on or a `calibrator` section (e.g.,
`config/experiments/experiment_2.yaml`).

## Stop the System

Stop all running services:

```bash
make down
```

## Clean Up

Delete the Kafka and Grafana volumes:

```bash
make clean-volumes
```

This stops the containers, deletes the Kafka and Grafana volumes, and resets Grafana to its initial state. Each
`make up` runs it first, so every run starts fresh; the results of each run stay in `data/<run id>/`.
