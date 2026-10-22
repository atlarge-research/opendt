"""Render the fixed figures of the live twin's Tutorial screen, from the notebooks' precomputed simulations; the
dashboards embed them (services/grafana/dashboards/build.py).

From the repository root: python tutorial/resources/make_figures.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the tutorial folder, for `resources`
from resources import TRACE_START, plot_power, simulate  # noqa: E402

IMAGES = Path(__file__).with_name("images")

if __name__ == "__main__":
    # step 1: notebook 1's first day, OpenDT vs. the ground truth, and the MAPE of each hour
    day1 = simulate(until=TRACE_START + pd.Timedelta("24h"), label="OpenDT")
    figure = plot_power(day1, hourly_mape=True).figure
    figure.set_size_inches(12, 5)
    figure.savefig(IMAGES / "tutorial_step1.png", dpi=150, bbox_inches="tight", metadata={"Software": None})
