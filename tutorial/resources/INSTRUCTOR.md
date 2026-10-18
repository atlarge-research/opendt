# Instructor Run-Sheet

ASCI course on distributed systems, Friday 30 October 2026, 1 hour, fewer than 20 students.

## Before Class

- One week before: send the students the README (Option 1) and ask them to create the codespace and run the first cell
  of notebook 1 (`Setup OK`) at least one day before class.
- One day before: run notebooks 1-3 on the laptop (about 15 s each with an empty cache on an M3 Max; the results stay
  cached in `resources/output/`).
- For the live demo: start Docker Desktop, run `make up config=tutorial/resources/configs/live_twin.yaml` once (the
  first start builds the Docker images), then `make down`.

## Timeline

| Time | Part | Notebook |
|---|---|---|
| 0:00-0:15 | Talk and live demo | |
| 0:15-0:25 | Use case 1: dynamic autoscaling | 1.autoscaling.ipynb |
| 0:25-0:45 | Use case 2: simulation calibration | 2.calibration.ipynb |
| 0:45-0:55 | Use case 3: CO2-aware workload migration | 3.co2_migration.ipynb |
| 0:55-1:00 | Wrap-up: the three questions and their answers | |

Each notebook is self-contained: at 0:25 and 0:45, all students open the next notebook, also those who did not finish
the previous one.

## Talk: Three Use Cases, Three Questions

| Use case | Question | Notebook |
|---|---|---|
| Dynamic autoscaling | How many hosts does SURF need? | 1 |
| Simulation calibration | Can the digital twin correct itself? | 2 |
| CO2-aware workload migration (advisor-on-the-side) | Where should SURF run its workload? | 3 |

## Live Demo (about 5 minutes)

1. `make up config=tutorial/resources/configs/live_twin.yaml`, then open http://localhost:3000: the detailed screen,
   with the control panel at the top left (Screen: Detailed, Simple, Topology, Tutorial; Full screen). Set the speed factor to
   60x: at max, the simulator falls behind the replay and a change shows only minutes later.
   The Tutorial screen (Screen: Tutorial) asks the questions of the three use cases on the live twin, one step at
   a time (`tutorial/resources/tutorial.yaml`); its solutions are folded.
2. Change the hosts in the control panel (Hosts 2,770, Apply), on the Topology screen (the SURF-SARA row's pencil,
   Count 2,770, Save), or from a terminal:
   `curl -X PUT -H "Content-Type: application/json" --data @tutorial/resources/configs/topology_2770_hosts.json http://localhost:3001/api/topology`.
   The predicted power draw jumps to about 4x; notebook 1 explains why. A dashed marker shows the change on every graph.
3. Calibration: Hosts 277 and Calibration On in the control panel, then Apply (the range of r, the values of r, the
   parallel runs, and the MAPE window are there too); the Twin accuracy row shows r and the hourly MAPE (in the test
   run, r 4, then 9, then 6, and the MAPE from 14% to about 1% within six trace hours); `make logs-calibrator` shows
   the MAPE of each candidate.
4. `make down`.

Known issues:

- Freshly built images get kafka-python 3.x (`kafka-python>=2.0.2` is not pinned), which rejected the `buffer_memory`
  setting in `libs/common/odt_common/utils/kafka.py`: fixed on the tutorial branch (commit c2df7c5); images built before
  the fix need `make up build=true`.
- Docker Desktop needs at least 8 GB: with calibration, the calibrator container alone used 4.7 GB in the test run (it
  picked r = 9, then 7, then 8 in the first minutes). Each parallel run of the calibrator takes about 1.3 GB; with 4,
  Docker killed dc-mock for memory, so keep Parallel runs at 2 or lower in the control panel.
- Port 9092: on the demo laptop, a local Java service listens on 127.0.0.1:9092, the host port of OpenDT's Kafka;
  stop it before `make up`.
- `make up` deletes the Kafka and Grafana volumes of the previous run.
- The time left of each job is foreknowledge: in the replay, each job arrives with its whole CPU trace; a real twin
  needs runtime estimates (e.g., the walltime users request).
- With other servers than SURF's and the calibrator on, the calibrator fits r so that the other servers match SURF's
  measured power; show what-ifs with the calibrator off.
- The dashboards use Grafana's new layout (public preview in 12.4); if a screen misbehaves, the classic dashboard
  ("OpenDT Dashboard") still shows power and CO₂.
- On a projector of 1,280 pixels or less, use Full screen: next to Grafana's menu, the control panel is too narrow
  for its fields.
- When every candidate's MAPE is infinite, the calibrator still picks r = 3.0 and publishes it (seen in stored runs
  after about 1.5 trace days); keep the calibration demo within the first trace day.
- The local `config/default.yaml` spells `linespace_points`; OpenDT ignores this field and tests 9 values (the
  tutorial configs spell `linspace_points`).

## Plan B

- A codespace does not start: the student follows with a neighbour, or reads the notebooks on GitHub.
- Simulations are slow on 2 cores: notebooks 2 and 3 simulate the full week 7 and 4 times; start the simulation cell
  first, then discuss the question while it runs. If the kernel runs out of memory, set `OPENDT_TUTORIAL_WORKERS=1`.
- The live demo fails: show `resources/images/grafana_dashboard.png` and the bonus section of notebook 1, which rebuilds
  the same view from simulations.

## Key Numbers (for the wrap-up)

- Notebook 1: MAPE 6.0% on the first day; 10x the hosts draw about 4x the power (84 vs. 22 kW); 1/2 of the hosts
  saves only 16% and jobs wait; switching off idle hosts (10 spare) saves 16% of the energy.
- Notebook 2: the best r for the week is 7 (MAPE 4.5% vs. 6.4% for r = 4); the best r per day changes between 5 and
  9; recalibrating every hour gives a MAPE of 3.6% (91% of the hours within 10%), but calibration is worse than no
  calibration in 5 of 168 hours.
- Notebook 3: same energy on every grid (3,424 kWh); CO2 from 1,172 kg (RO) to 2,959 kg (PL); RO saves only 6% vs.
  NL, and NL is greener than RO in 57 of 169 hours; following the greenest grid every hour gives 1,065 kg with 11
  migrations.
