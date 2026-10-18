# Grafana

Visualization dashboards for OpenDT metrics.

## Access

- **URL:** http://localhost:3000
- **Authentication:** Disabled (anonymous admin access)

Four screens, each with a control panel at the top left (in place of Grafana's time picker): the screen, the time
window, the interval of the totals, the decisions markers, and the twin's levers (CO₂ zone, scheduler, speed factor,
parallel runs of the calibrator, hosts). Nothing changes before Apply: then the levers go to the twin and the screen
follows. Full screen switches the browser's full screen on and off, without Grafana's bars.

- **OpenDT, detailed** (the home page): ten tiles of the twin's state, power, CO₂ vs. carbon intensity, and hosts;
  then a row each for performance (P1-P5), utilization (U1-U5), sustainability (S1-S5, per interval), and twin
  accuracy (T1-T5). The Plots row picks the plots to show. Markers on every graph show the decisions (changes of
  hosts, r, CO₂ zone, and scheduler; automatic or manual), the legends the latest values, and the right axis which way
  is better (BETTER with an arrow).
- **OpenDT, simple:** the physical twin (power draw, jobs arriving) next to the digital twin (total runtime, jobs
  started within 10 minutes, hosts per CPU utilization, decisions).
- **OpenDT, topology:** the host groups (SURF's node and OpenDC web's host templates), what runs now, and the kinds
  to choose from.
- **OpenDT, tutorial:** the 12 steps of the tutorial (`tutorial/resources/tutorial.yaml`), one at a time, chosen by
  its tag: a question of the notebooks, what to do in the control panel, the solution folded, and the step's plots;
  the twin's state at the top.
- **OpenDT Dashboard** (classic): power and carbon emissions.

The dashboards use Grafana's v2 format and its new layout (public preview in 12.4, enabled in the image), which
shows or hides each plot. The panels query the OpenDT API at `http://api:8000`, from the Grafana server; the forms
send their requests from the browser, to the API's port on the host, `http://localhost:3001` (`GET /api/status`,
`PATCH /api/control`).

## Changing a screen

The screens are built by the code in `dashboards/`:

- `plots.py`: what each plot shows, one definition per plot;
- `steps.py`: what each step of the tutorial shows, from `tutorial/resources/tutorial.yaml`;
- `screens.py`: where each panel sits on each screen;
- `form.py` and `js/`: the control panel and the plot picker (Business Forms) and their code;
- `panels.py`: the building blocks (endpoints, colours, Grafana's panel types);
- `layout.py`: Grafana's v2 dashboard format.

After a change, `python3 services/grafana/dashboards/build.py` writes the dashboards into
`provisioning/dashboards/`; a test (`services/grafana/tests`) fails while they are out of date.

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
