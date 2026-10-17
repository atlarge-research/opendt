# OpenDT Tutorial

Hands-on notebooks on OpenDT, the open-source digital twin for datacenters.
The notebooks run the simulation engine of OpenDT (the OpenDC simulator) on one week of real-world telemetry from SURF,
the Dutch national supercomputing center; they do not need Docker.
We prepared them for the ASCI course on distributed systems (30 October 2026).

| Notebook | Use case | Question | Time |
|---|---|---|---|
| [1.autoscaling.ipynb](1.autoscaling.ipynb) | Dynamic autoscaling | How many hosts does SURF need? | 10 min |
| [2.calibration.ipynb](2.calibration.ipynb) | Simulation calibration | Can the digital twin correct itself? | 20 min |
| [3.co2_migration.ipynb](3.co2_migration.ipynb) | CO2-aware workload migration | Where should SURF run its workload? | 10 min |
| [4.live_twin.ipynb](4.live_twin.ipynb) (bonus) | The live digital twin | What does OpenDT look like when it runs? | 15 min, requires Docker |

## Getting Started

### Option 1: GitHub Codespaces (recommended)

1. Open [codespaces.new/atlarge-research/opendt?ref=tutorial](https://codespaces.new/atlarge-research/opendt?ref=tutorial)
   and create the codespace. The setup installs Python, Java 21, and OpenDT, which takes a few minutes; create the
   codespace before class.
2. Open `tutorial/1.autoscaling.ipynb`, select the kernel "OpenDT (.venv)", and run the first cell: it prints
   `Setup OK`.

Codespaces is free within the monthly quota of a personal GitHub account (120 core-hours per month on GitHub Free;
the tutorial uses a machine with 2 cores). A codespace stops after 30 minutes without activity.

### Option 2: Local Setup

Requirements: Python 3.11 or newer, Java 21 or newer, [uv](https://docs.astral.sh/uv/), and make. On Windows, use
Codespaces or WSL2.

```
git clone https://github.com/atlarge-research/opendt.git
cd opendt
git switch tutorial
make setup
```

Then, open the notebooks in VS Code (with the Jupyter extension) and select the Python environment `.venv`, or install
JupyterLab with `uv pip install jupyterlab` and start it with `.venv/bin/jupyter lab`.

### Troubleshooting

- *OpenDC needs Java 21 or newer:* install Java 21 (e.g., from [Adoptium](https://adoptium.net)) and set `JAVA_HOME`.
- *`make setup` fails because `.venv` already exists:* run `make clean-env`, then `make setup` again.
- *Simulations are slow, or the kernel runs out of memory:* run fewer simulations at the same time, e.g., with
  `export OPENDT_TUTORIAL_WORKERS=1` before starting Jupyter.

## Folder Structure

- The four notebooks.
- `resources/`: the data and scripts of the notebooks: the Python helpers that run the simulation engine of OpenDT,
  the carbon intensity traces, the configurations of the live twin, the images, and the tests. Simulation results are
  cached in `resources/output/`; delete this folder to simulate again from scratch.

The run-sheet for the session is [resources/INSTRUCTOR.md](resources/INSTRUCTOR.md).

## Data and Licenses

- The SURF workload and power traces (`workload/SURF/`) come from Versluis et al., "Less is not more: We need rich
  datasets to explore", Future Generation Computer Systems 142 (2023), doi:
  [10.1016/j.future.2022.12.022](https://doi.org/10.1016/j.future.2022.12.022).
- The carbon intensity traces come from Electricity Maps, under the Open Database License; see
  [resources/carbon_traces/LICENSE.md](resources/carbon_traces/LICENSE.md).
- The figures of OpenDT come from the OpenDT paper (CC BY 4.0).

## Citation

```bibtex
@inproceedings{nicolae2026opendt,
  author    = {Radu Nicolae and Jules van der Toorn and Stavriana Kraniti and Houcen Liu and Alexandru Iosup},
  title     = {{OpenDT}: Exploring Datacenter Performance and Sustainability with a Self-Calibrating Digital Twin},
  booktitle = {Companion of the 17th {ACM/SPEC} International Conference on Performance Engineering ({ICPE} Companion '26)},
  year      = {2026},
  doi       = {10.1145/3777911.3800634}
}

@misc{nicolae2026opendtreport,
  author = {Radu Nicolae and Jules van der Toorn and Stavriana Kraniti and Houcen Liu and Alexandru Iosup},
  title  = {{OpenDT}: Exploring Datacenter Performance and Sustainability with a Self-Calibrating Digital Twin},
  note   = {Technical Report},
  year   = {2026},
  url    = {https://atlarge-research.com/pdfs/2026-hcp-opendt-techrep.pdf}
}
```

## Learn More

- [OpenDT documentation](https://atlarge-research.github.io/opendt/docs/)
- [OpenDT paper](https://atlarge-research.com/pdfs/2026-icpe-opendt.pdf) and
  [technical report](https://atlarge-research.com/pdfs/2026-hcp-opendt-techrep.pdf)
- [OpenDC](https://opendc.org), the simulator inside OpenDT
