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

After the simulation completes (or during it, for intermediate results), activate the virtual environment and run the
plot generator:

```bash
source .venv/bin/activate
python reproducibility-capsule/generate_plot.py
```

The interactive script:

1. Asks which experiment to plot (1 or 2)
2. Shows the available runs, completed or in progress
3. Offers the plots as a checkbox:
   - Experiment 1: Power Prediction Accuracy (Ground Truth vs. FootPrinter vs. OpenDT), Sustainability/Performance/Efficiency
     Overview, and Job Completion Efficiency (jobs per kWh)
   - Experiment 2: MAPE Over Time (calibrated vs. non-calibrated), which also needs a run of experiment 1, plus all
     Experiment 1 plots

Plots are saved to `reproducibility-capsule/output/experiment_<number>/<workload>_<plot>.pdf`.

## Output

The Power Prediction Accuracy plot shows:

- **Left Y-axis**: Power draw [kW] of the Ground Truth (actual measurements), FootPrinter (baseline predictor), and
  OpenDT (digital twin prediction)
- **Right Y-axis**: OpenDT's cumulative MAPE [%]
- **X-axis**: Time

The script also prints the MAPE of FootPrinter and of OpenDT.

## Reference Data

The plots compare OpenDT with two references:

- `reproducibility-capsule/data/SURF/footprinter.parquet` - FootPrinter predictions
- `workload/SURF/consumption.parquet` - Ground truth measurements
