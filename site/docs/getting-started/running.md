---
sidebar_position: 3
---

# Running OpenDT

## Start the System

```bash
make up                                              # config/default.yaml
make up config=config/experiments/experiment_1.yaml  # another configuration
```

`config/default.yaml` replays the week in real time (`speed_factor: 1`); the experiments replay at 300x. The Twin box,
on top of each screen, changes the speed while the twin runs.

The first `make up` builds the Docker images, which takes a few minutes; `make up build=true` rebuilds them.

## Access the Dashboard

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Grafana Dashboard |
| http://localhost:3001 | API Documentation |

Grafana opens on the Dashboard screen; its tabs at the top left switch to the Topology and Tutorial screens. See
[grafana](/docs/services/grafana).

## Monitor Progress

```bash
make logs-simulator
make logs-dc-mock
make logs-api
make logs-calibrator
```

The calibrator runs only when the configuration has a `services.calibrator` section (e.g.,
`config/experiments/experiment_2.yaml`).

## Stop the System

```bash
make down
```

## Clean Up

```bash
make clean-volumes
```

This stops the containers and deletes the Kafka and Grafana volumes. `make up` runs it first; each run's results stay in
`data/<RUN_ID>/`.
