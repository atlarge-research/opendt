---
sidebar_position: 6
---

# Reproducibility Capsule

The reproducibility capsule provides scripts to reproduce the experiments from the OpenDT paper.

## Experiments

| Experiment | Description | Configuration |
|------------|-------------|---------------|
| Experiment 1 | Power prediction without calibration | `experiment_1.yaml` |
| Experiment 2 | Power prediction with active calibration | `experiment_2.yaml` |

## Running Experiments

### 1. Start OpenDT

Run with the experiment configuration:

```bash
# Experiment 1 (without calibration)
make up config=config/experiments/experiment_1.yaml

# Experiment 2 (with calibration)
make up config=config/experiments/experiment_2.yaml
```

### 2. Wait for Completion

With `speed_factor: 300` and the SURF workload (~7 days), each experiment takes approximately 1 hour.

Monitor progress via the Grafana dashboard at http://localhost:3000.

### 3. Generate Plots

After the simulation completes:

```bash
python reproducibility-capsule/generate_plot.py
```

The interactive script will:

1. Prompt you to select an experiment (1 or 2)
2. Show available data sources with timestamps
3. Generate a plot comparing:
   - Ground Truth (actual power)
   - FootPrinter baseline
   - OpenDT prediction

Plots are saved to `reproducibility-capsule/output/`.

## Output

Generated plots show:

- **Left Y-axis**: Power draw (kW)
- **Right Y-axis**: MAPE percentage
- **X-axis**: Time

Three time series are plotted:

- Ground Truth (actual measurements)
- FootPrinter (baseline predictor)
- OpenDT (digital twin prediction)

MAPE values for both FootPrinter and OpenDT are displayed in the legend.

## Reference Data

The `reproducibility-capsule/data/` directory contains reference data for the baseline comparisons:

- `footprinter.parquet` - FootPrinter predictions
- `real_world.parquet` - Ground truth measurements
