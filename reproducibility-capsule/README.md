# Reproducibility Capsule

This folder contains everything needed to reproduce the experiments from the OpenDT paper.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ with dependencies installed (`pip install -e .` from repo root)

## Running Experiments

OpenDT experiments are started using Docker Compose with a specific configuration file:

```bash
# Experiment 1: Power prediction without calibration
make up config=config/experiments/experiment_1.yaml

# Experiment 2: Power prediction with active calibration
make up config=config/experiments/experiment_2.yaml
```

### Experiment Duration

The time required to complete an experiment depends on:

1. **Workload duration** - The length of the historical workload being simulated
2. **Speed factor** - The simulation speedup configured in the experiment YAML

For example, with the SURF workload (~7 days of data) and a `speed_factor` of 300, the experiment takes approximately **1 hour** to complete.

You can monitor progress via the Grafana dashboard at http://localhost:3000 or by checking the Docker logs:

```bash
make logs-simulator
```

## Generating Plots

Use the interactive plot generator to create publication-ready figures:

```bash
python reproducibility-capsule/generate_plot.py
```

The script will:

1. Ask which experiment you want to generate a plot for
2. Show available data sources (completed or in-progress runs)
3. Generate a PDF plot comparing Ground Truth, FootPrinter, and OpenDT
4. Display MAPE (Mean Absolute Percentage Error) for both FootPrinter and OpenDT

### Intermediate Results

You can run the plot generator **during** an experiment to visualize intermediate results. The script will use whatever simulation data is available at that point.

### Final Results

After the experiment completes, run the script again to generate the final plots with the full dataset.

### Output

Generated plots are saved to:

```
reproducibility-capsule/output/experiment_<number>_<workload>.pdf
```

## Baseline Data

The `data/` folder contains pre-computed baseline results:

- `footprinter.parquet` - Results from the FootPrinter simulator
- `real_world.parquet` - Ground truth power consumption data

These are used as comparison baselines in the generated plots.
