"""Power draw plot: the ground truth measured at SURF and OpenDT's predictions."""

from __future__ import annotations

import matplotlib.pyplot as plt

from .data import TRACE_START, measured_power, to_utc

# The colours of the OpenDT paper figures (reproducibility-capsule/plots/config.py), colour-blind friendly.
plt.rcParams["axes.prop_cycle"] = plt.cycler(
    color=["#009E73", "#E69F00", "#338ec1", "#D55E00", "#9557a5", "#56B4E9", "#CC79A7"]
)


def legend_above(ax):
    """The key in one row, centred just above the axes, in a thin black square frame."""
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1),
        ncol=len(ax.get_legend_handles_labels()[1]),
        fancybox=False,
        edgecolor="black",
        framealpha=1,
        borderpad=0.3,
    )


def plot_power(*results, start=TRACE_START, end=None, ax=None):
    """Ground truth (grey) and the predicted power draw of each SimResult, in kW."""
    end = to_utc(end) if end is not None else max(r.until for r in results)
    ax = ax or plt.subplots(figsize=(10, 4))[1]
    (measured_power(start, end) / 1000).plot(ax=ax, color="#999999", label="Ground Truth")
    for result in results:
        (result.power["power_draw"][to_utc(start) : end] / 1000).plot(ax=ax, label=result.label)
    ax.set_xlabel("Time [UTC]")
    ax.set_ylabel("Power Draw [kW]")
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    legend_above(ax)
    return ax
