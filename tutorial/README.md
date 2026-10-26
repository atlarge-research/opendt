# OpenDT Tutorial

OpenDT is an open-source digital twin for monitoring and operating datacenters. In this tutorial, OpenDT twins the
SURF-SARA cluster of SURF over one week of October 2022, with the OpenDC simulator at its core.

1. [Dynamic autoscaling](1.autoscaling.ipynb): how many hosts does SURF need?
2. [Simulation calibration](2.calibration.ipynb): can the digital twin correct itself?
3. [Workload migration, CO2 aware](3.co2_migration.ipynb): where should SURF run its workload?

## Setup

Open a [GitHub Codespace](https://codespaces.new/atlarge-research/opendt), or, locally (Python 3.11+, make, and Docker
for the live twin):

```
git clone https://github.com/atlarge-research/opendt.git
cd opendt
make setup
make up config=tutorial/resources/configs/live_twin.yaml
```

The live twin needs Docker on the laptop (a codespace has none): Docker Desktop with at least 8 GB, and port 9092 (the
host port of OpenDT's Kafka) free; the first `make up` builds the Docker images, which takes a few minutes.
Then run the notebooks with the `.venv` kernel, in VS Code or PyCharm (or in JupyterLab, with
`env -u VIRTUAL_ENV uv run --with jupyterlab jupyter lab tutorial/`), and open the live twin in Grafana
(http://localhost:3000); `make down` stops it.
The notebooks' simulations ship precomputed, so they need no Java; a simulation of our own (e.g., with 333 hosts) runs
OpenDC, which needs Java 21 (e.g., from [Adoptium](https://adoptium.net), with `JAVA_HOME` set).

## Doing the Tutorial

1. Run the three notebooks in order, in pairs; each takes about 10 minutes, and each question unfolds its answer
   when a choice is clicked.
2. Then, on the live twin in Grafana (http://localhost:3000, Tutorial screen), set Speed to 60x in the Twin box and go
   through its 11 steps: each changes the running twin (e.g., the hosts, the CO2 zone) and asks one of the notebooks'
   questions about what follows.
   In a classroom, the instructor can run the twin on the projector.

## Data and Citation

SURF traces: [Versluis et al., FGCS 2023](https://doi.org/10.1016/j.future.2022.12.022). Carbon intensity:
Electricity Maps ([ODbL](../workload/SURF/carbon_zones/LICENSE.md)). Figures: the OpenDT paper (CC BY 4.0).

```bibtex
@inproceedings{DBLP:conf/wosp/NicolaeTKLI26,
  author       = {Radu Nicolae and
                  Jules van der Toorn and
                  Stavriana Kraniti and
                  Houcen Liu and
                  Alexandru Iosup},
  editor       = {Roberto Verdecchia and
                  Catia Trubiani and
                  Radu Calinescu and
                  Ana Lucia Verbanescu},
  title        = {OpenDT: Exploring Datacenter Performance and Sustainability with a
                  Self-Calibrating Digital Twin},
  booktitle    = {Companion of the 17th {ACM/SPEC} International Conference on Performance
                  Engineering, {ICPE} Companion 2026, Florence, Italy, May 4-8, 2026},
  pages        = {142--147},
  publisher    = {{ACM}},
  year         = {2026},
  url          = {https://doi.org/10.1145/3777911.3800634},
  doi          = {10.1145/3777911.3800634},
  timestamp    = {Wed, 03 Jun 2026 10:10:46 +0200},
  biburl       = {https://dblp.org/rec/conf/wosp/NicolaeTKLI26.bib},
  bibsource    = {dblp computer science bibliography, https://dblp.org}
}
```