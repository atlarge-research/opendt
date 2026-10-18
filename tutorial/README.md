# OpenDT Tutorial

These notebooks are the hands-on part of the OpenDT session in the ASCI course on distributed systems (Friday, 30
October 2026).
OpenDT is an open-source digital twin for monitoring and operating datacenters; here, it twins the SURF-SARA cluster of
SURF over one week of October 2022, with the OpenDC simulator at its core.

We go through the three use cases of the talk, one notebook each, in about 40 minutes; going slowly is fine, and not
everything has to be covered:

1. [Dynamic autoscaling](1.autoscaling.ipynb): how many hosts does SURF need? (10 minutes)
2. [Simulation calibration](2.calibration.ipynb): can the digital twin correct itself? (20 minutes)
3. [Workload migration, CO2 aware](3.co2_migration.ipynb): where should SURF run its workload? (10 minutes)

The [bonus notebook](4.live_twin.ipynb) runs the live digital twin of the demo, with Docker.

## Setup

The easiest is GitHub Codespaces, a day before class:
[codespaces.new/atlarge-research/opendt?ref=tutorial](https://codespaces.new/atlarge-research/opendt?ref=tutorial)
(2 cores are enough, and a free GitHub account has 120 core-hours per month).
The setup installs Python, Java 21, and OpenDT in a few minutes; then, in `tutorial/1.autoscaling.ipynb`, we select the
kernel "OpenDT (.venv)" and run the first cell, which prints `Setup OK`.

Locally, with Python 3.11+, Java 21+, [uv](https://docs.astral.sh/uv/), and make (on Windows, in WSL2):

```
git clone https://github.com/atlarge-research/opendt.git
cd opendt
git switch tutorial
make setup
```

The notebooks then open in VS Code, with the `.venv` environment (or in JupyterLab, after `uv pip install jupyterlab`,
with `.venv/bin/jupyter lab`).
When something fails: OpenDC needs Java 21 (e.g., from [Adoptium](https://adoptium.net), with `JAVA_HOME` set);
`make setup` stops when `.venv` already exists, so `make clean-env` comes first; and on a slow machine,
`export OPENDT_TUTORIAL_WORKERS=1` runs one simulation at a time.

## What Is Where

`resources/` holds the data and scripts of the notebooks (the helpers around the OpenDC simulator of OpenDT, the
configurations of the live twin, the images, and the tests); simulations are cached in
`resources/output/`. The run-sheet of the session is [resources/INSTRUCTOR.md](resources/INSTRUCTOR.md).

## Data, Licenses, and Citation

The SURF traces come from Versluis et al., "Less is not more: We need rich datasets to explore", Future Generation
Computer Systems 142 (2023), [doi:10.1016/j.future.2022.12.022](https://doi.org/10.1016/j.future.2022.12.022); the
carbon intensity traces come from Electricity Maps, under the Open Database License
([details](../workload/SURF/carbon_zones/LICENSE.md)); and the figures come from the OpenDT paper (CC BY 4.0).
More in the [OpenDT documentation](https://atlarge-research.github.io/opendt/docs/).

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
