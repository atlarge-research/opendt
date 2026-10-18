# Grafana

Visualization dashboards for OpenDT metrics.

## Access

- **URL:** http://localhost:3000
- **Authentication:** Disabled (anonymous admin access)

Three screens, linked at the top left of each, next to the control panel (carbon zone, scheduler, replay speed,
and a full-screen button):

- **OpenDT** (the home page, detailed): the twin's state, power, CO2 vs. carbon intensity, and hosts; then a row each
  for scheduling, utilization, energy and sustainability (per period, chosen at the top), and twin accuracy. The
  Layout row picks the plots to show. Markers on every graph show the topology changes, the legends the latest
  values, and the right axis whether higher or lower is better.
- **OpenDT, simple:** the physical system (measured power, jobs arriving) next to the twin (time to full
  completion, jobs started within 10 minutes, hosts per CPU utilization, decisions).
- **OpenDT, topology:** the server groups (SURF's node and OpenDC web's host templates), what runs now, and the kinds
  to choose from.
- **OpenDT Dashboard** (classic): power and carbon emissions.

The dashboards use Grafana's v2 format and its new layout (public preview in 12.4, enabled in the image), which
shows or hides each plot. The panels query the OpenDT API at `http://api:8000`, from the Grafana server; the forms
send their requests from the browser, to the API's port on the host, `http://localhost:3001` (`GET /api/status`,
`PATCH /api/control`).

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
