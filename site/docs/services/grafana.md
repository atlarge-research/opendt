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

Three screens, each with the levers of the twin on top: Dashboard (the home page), Topology, and Tutorial; see
`services/grafana/README.md`. They always run in Grafana's kiosk mode (no menus). The classic OpenDT Dashboard
(`power_dashboard.json`) still shows power and CO₂.

The panels query the OpenDT API at `http://api:8000`; the boxes on top send their changes from the browser to
`http://localhost:3001`.

## Building the Screens

The screens are built by the code in `services/grafana/dashboards/`. After a change there, or in `tiles.yaml` (the
shares and the ⓘ text of each panel), rebuild the provisioned dashboards:

```bash
python3 services/grafana/dashboards/build.py
```

A test fails while the provisioned JSON is out of date.

## Provisioning

Dashboards in `services/grafana/provisioning/dashboards/` are auto-provisioned on startup; Grafana re-reads them every
10 s. Each `make up` deletes the `opendt-grafana-storage` volume, so dashboards saved from the UI are lost.

## Data Sources

The [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) is pre-configured to query JSON endpoints from the OpenDT API.

## Image

The image pins Grafana 12.4.13 and its plugins, so the dashboard needs no internet at start; after a change of version,
`make up build=true` rebuilds it.
