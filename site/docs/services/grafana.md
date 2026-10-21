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

Three screens, each with the levers of the twin on top: Detailed (the home page), Topology, and Tutorial; see
`services/grafana/README.md`. They are built by the code in `services/grafana/dashboards/`. The classic OpenDT Dashboard
(`power_dashboard.json`) still shows power and CO₂.

Data is queried from the OpenDT API at `http://api:8000`; the control panel sends its changes from the browser to
`http://localhost:3001`.

## Building the Screens

After a change in `services/grafana/dashboards/` or in `tiles.yaml` (the shares and the ⓘ text of each panel), rebuild the
provisioned dashboards:

```bash
python3 services/grafana/dashboards/build.py
```

A test fails while the provisioned JSON is out of date.

## Provisioning

Dashboards in `services/grafana/provisioning/dashboards/` are auto-provisioned on startup; Grafana re-reads them every
10 s.

To create an editable copy:

1. Open the dashboard
2. Click title → **Save As**
3. Save with a new name

Custom dashboards stay in the Docker volume until the next `make up`, which deletes it, as `make clean-volumes` does.

## Data Sources

The [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) is pre-configured to query JSON endpoints from the OpenDT API.

## Image

The image pins Grafana 12.4.13 and its plugins, so the dashboard needs no internet at start; after a change of version,
`make up build=true` rebuilds it.

## Persistence

Dashboard data is stored in the `opendt-grafana-storage` Docker volume.

To reset Grafana to its initial state:

```bash
make clean-volumes
```
