# Grafana

Visualization dashboards for OpenDT metrics.

## Access

- **URL:** http://localhost:3000
- **Authentication:** Disabled (anonymous admin access)

Three screens, each with a control panel on top, in place of Grafana's time picker: at the top left, the view (the
screen, the time window, the decisions markers, and the interval of the totals); on the right, the twin's levers
(hosts, scheduler, CO₂ zone, speed, calibration, range and values of r, and MAPE window; the parallel runs are only
shown). The view changes at once; the levers, after Apply. The screens always run in Grafana's kiosk mode (no menus,
no bars), and start on Day.

- **OpenDT, dashboard** (the home page): the decisions and four groups of the twin's numbers now (power, jobs and
  hosts, sustainability, accuracy); then a row each for performance, utilization, sustainability (per interval), and
  twin accuracy; the first panel of each row is its Overview. The ☰ Plots button picks the plots to show. Markers on
  every graph show the decisions (changes of hosts, r, CO₂ zone, and scheduler; automatic or manual).
- **OpenDT, topology:** the datacenter, its racks and their hosts, edited in place (a row's pencil, + to add one by
  picking a rack prefab, the bin to delete one); the hosts available and in use; and the prefabs the racks come from:
  racks, CPUs, and GPUs, as OpenDT ships them at first (SURF's node, OpenDC web's host templates, the Dell servers of
  OpenDC's RADiCe experiments) and then the user's, kept in `data/prefabs.json` (without it, as shipped again).
- **OpenDT, tutorial:** the 11 steps of the tutorial (`tutorial/resources/tutorial.yaml`), one at a time, chosen by
  its number or by Back and Next: a change to the twin, a question with four choices (a click says if it holds), a
  hint, and a solution, folded, then the step's plots; the twin's state in boxes on the left.
- **OpenDT Dashboard** (classic, no control panel): power and carbon emissions.

The dashboards use Grafana's v2 format and its new layout (public preview in 12.4, enabled in the image), which
shows or hides each plot. The panels query the OpenDT API at `http://api:8000`, from the Grafana server; the control
panel sends its changes from the browser, to the API's port on the host, `http://localhost:3001` (`PATCH /api/control`,
and `GET /api/progress` while the twin starts).

## Changing a screen

The screens are built by the code in `dashboards/`:

- `plots.py`: what each plot shows, one definition per plot;
- `steps.py`: what each step of the tutorial shows, from `tutorial/resources/tutorial.yaml`;
- `screens.py`: where each panel sits on each screen;
- `form.py` and `js/`: the control panel and the plot picker (Business Text panels) and their code;
- `panels.py`: the building blocks (endpoints, colours, Grafana's panel types);
- `layout.py`: Grafana's v2 dashboard format.

After a change, `python3 services/grafana/dashboards/build.py` writes the dashboards into
`provisioning/dashboards/`; a test (`services/grafana/tests`) fails while they are out of date.

## Image

The image pins Grafana 12.4.13, the [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/)
3.11.1, [Business Text](https://grafana.com/grafana/plugins/marcusolsson-dynamictext-panel/) 6.3.0 (the control panel),
and [Business Table](https://grafana.com/grafana/plugins/volkovlabs-table-panel/) 3.6.8 (the Topology tables), so Grafana starts without internet; after a version change, `make up build=true` rebuilds it.

## Provisioning

Dashboards in `provisioning/dashboards/` are auto-provisioned on startup; Grafana re-reads them every 10 s. Each
`make up` deletes the `opendt-grafana-storage` volume, as `make clean-volumes` does, so dashboards saved from the UI
are lost.
