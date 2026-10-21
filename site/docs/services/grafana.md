---
sidebar_position: 5
---

# grafana

Visualization dashboards for OpenDT metrics.

## Access

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Grafana Dashboard |

Authentication is disabled by default (anonymous admin access).

## Dashboards

Four screens: Detailed (the home page), Simple, Topology, and Tutorial, each with a control panel; see
`services/grafana/README.md`. They are built by the code in `services/grafana/dashboards/`.

Data is queried from the OpenDT API at `http://api:8000`.

## Provisioning

Dashboards in `services/grafana/provisioning/dashboards/` are auto-provisioned on startup. These are read-only templates.

To create an editable copy:

1. Open the dashboard
2. Click title → **Save As**
3. Save with a new name

Custom dashboards are persisted in the Docker volume.

## Data Sources

The [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) is pre-configured to query JSON endpoints from the OpenDT API.

## Persistence

Dashboard data is stored in the `opendt-grafana-storage` Docker volume.

To reset Grafana to its initial state:

```bash
make clean-volumes
```
