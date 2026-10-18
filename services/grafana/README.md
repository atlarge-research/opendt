# Grafana

Visualization dashboards for OpenDT metrics.

## Access

- **URL:** http://localhost:3000
- **Authentication:** Disabled (anonymous admin access)

The OpenDT dashboard is the home page.

## Dashboards

- **OpenDT:** the control panel (hosts, carbon zone, and replay speed of the running twin), the twin's status, and
  power; then a row each for scheduling (time to full completion, time in queue, jobs, and the jobs not done yet),
  utilization (CPU of the hosts, demand vs. capacity, hosts in use), energy and sustainability (CO2 vs. carbon
  intensity, energy, operational vs. embodied CO2), and twin accuracy (r and MAPE of the calibrator). Markers on
  every graph show the topology changes (hosts, r, carbon zone); the legends show the latest values.
- **OpenDT Dashboard** (classic): power and carbon emissions.

The panels query the OpenDT API at `http://api:8000`, from the Grafana server. The control panel sends its requests
from the browser, to the API's port on the host, `http://localhost:3001` (`GET /api/status`, `PATCH /api/control`).

## Image

The image pins Grafana 12.4.13, the [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/)
3.11.1, and [Business Forms](https://grafana.com/grafana/plugins/volkovlabs-form-panel/) 6.3.5 (the control panel),
so Grafana starts without internet; after a version change, `make up build=true` rebuilds it.

## Provisioning

Dashboards in `provisioning/dashboards/` are auto-provisioned on startup. These are read-only templates.

To create an editable copy:
1. Open the dashboard
2. Click title → **Save As**
3. Save with a new name

Custom dashboards are persisted in the Docker volume.

## Persistence

Dashboard data is stored in the `opendt-grafana-storage` Docker volume. To reset:

```
make clean-volumes
```
