# Reproducibility Capsule

This folder contains everything needed to reproduce the experiments from the OpenDT paper.

## Running Experiments

OpenDT experiments are started using Docker Compose with a specific configuration file:

```bash
# Experiment 1: Power prediction without calibration
make up config=config/experiments/experiment_1.yaml

# Experiment 2: Power prediction with active calibration
make up config=config/experiments/experiment_2.yaml
```

### Experiment Duration

The time required depends on the workload duration and the configured speed factor. With the SURF workload (~7 days of data) and `speed_factor: 300`, experiments complete in approximately **1 hour**.

Monitor progress via Grafana at http://localhost:3000 or check logs:

```bash
make logs-simulator
```

## Generating Plots

First, activate the virtual environment:

```bash
source .venv/bin/activate
```

Then use the interactive plot generator to create publication-ready figures:

```bash
python reproducibility-capsule/generate_plot.py
```

The script will:

1. Ask which experiment to generate plots for
2. Show available data sources (completed or in-progress runs)
3. Let you select which plots to generate using an interactive checkbox

### Available Plots

**Experiment 1** (no calibration):

- **Power Prediction Accuracy** - Ground Truth vs FootPrinter vs OpenDT
- **Sustainability/Performance/Efficiency Overview** - 3-panel plot with power, performance, and efficiency
- **Job Completion Efficiency** - Jobs per kWh over time

**Experiment 2** (with calibration):

- **MAPE Over Time** - Compares calibrated vs non-calibrated MAPE
- All Experiment 1 plots

> Note that for Experiment 2's MAPE Over Time plot, you need data from both experiment 1 and experiment 2.

You can run the plot generator **during** an experiment to visualize intermediate results.

### Output

Generated plots are saved to:

```
reproducibility-capsule/output/experiment_<number>/<workload>_<plot_type>.pdf
```

## Baseline Data

The `data/` folder contains pre-computed baseline results:

- `footprinter.parquet` - Results from the FootPrinter simulator
- `real_world.parquet` - Ground truth power consumption data

These are used as comparison baselines in the generated plots.
