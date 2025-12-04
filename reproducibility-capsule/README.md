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

Use the interactive plot generator to create publication-ready figures:

```bash
python reproducibility-capsule/generate_plot.py
```

The script will:

1. Ask which experiment to generate a plot for
2. Show available data sources (completed or in-progress runs)
3. Generate a PDF comparing Ground Truth, FootPrinter, and OpenDT
4. Display MAPE (Mean Absolute Percentage Error) for both FootPrinter and OpenDT

You can run the plot generator **during** an experiment to visualize intermediate results.

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
