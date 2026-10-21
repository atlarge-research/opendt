"""Power draw plot: the ground truth measured at SURF and OpenDT's predictions, and their MAPE per hour."""

from __future__ import annotations

import matplotlib.pyplot as plt

from .data import measured_power
from .metrics import error
from .sim import SimResult

# The colours of the OpenDT paper figures (reproducibility-capsule/plots/config.py), colour-blind friendly;
# a line style per colour keeps the plots readable in grayscale.
plt.rcParams.update(
    {
        "axes.prop_cycle": plt.cycler(
            color=["#009E73", "#E69F00", "#338ec1", "#D55E00", "#9557a5", "#56B4E9", "#CC79A7"],
            linestyle=["-", "--", ":", "-.", (0, (5, 1)), (0, (3, 1, 1, 1, 1, 1)), (0, (1, 1))],
        ),
        "figure.figsize": (10, 4),
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.axisbelow": True,
        "legend.fancybox": False,
        "legend.edgecolor": "black",
        "legend.framealpha": 1,
        "legend.borderpad": 0.3,
    }
)


def legend_above(ax):
    """The key in one row, centred just above the axes."""
    ax.legend(
        loc="lower center", bbox_to_anchor=(0.5, 1), ncol=len(ax.get_legend_handles_labels()[1])
    )


def plot_power(*results, hourly_mape=False, energy=False):
    """Ground truth (grey) and the predicted power draw of each SimResult or power series [W], in kW;
    with `hourly_mape`, the MAPE of each hour under it, on the same time axis; with `energy` (SimResults
    only), the energy of each run, and per finished job, on the right."""
    lines = [
        r.power["power_draw"].rename(r.label) if isinstance(r, SimResult) else r for r in results
    ]
    if hourly_mape:
        ax, below = plt.subplots(2, sharex=True, figsize=(10, 6.5), height_ratios=(2, 1))[1]
    elif energy:
        panels = plt.figure(figsize=(12.5, 4.5), layout="constrained").subplot_mosaic(
            [["power", "total"], ["power", "per_job"]], width_ratios=(3, 1)
        )
        ax = panels["power"]
    else:
        ax = plt.subplots()[1]
    end = max(line.index[-1] for line in lines)
    (measured_power(end=end) / 1000).plot(
        ax=ax, color="#999999", linestyle="-", label="Ground Truth"
    )
    for line in lines:
        (line / 1000).plot(ax=ax, label=line.name)
    ax.set(xlabel="Time [UTC]", ylabel="Power Draw [kW]", ylim=(0, None))
    legend_above(ax)
    if hourly_mape:
        xlim = ax.get_xlim()  # pandas fits the shared time axis to each plot's data
        for line in lines:
            error(line).resample("1h").transform("mean").plot(ax=below, label=line.name)
        below.axhline(
            10,
            color="red",
            linewidth=0.8,
            linestyle=":",
            label="Community-Accepted Threshold (10%)",
        )
        below.set(xlabel="Time [UTC]", ylabel="MAPE [%]", xlim=xlim, ylim=(0, None))
        legend_above(below)
    if energy:
        colors = [line.get_color() for line in ax.lines[1:]]  # each run as its power line
        energy_bars(results, panels["total"], panels["per_job"], colors)
    return ax


def energy_bars(runs, total, per_job, colors):
    """One bar per run: its energy until `until`, and that energy per job finished by then [kWh]."""
    summaries = [run.summary() for run in runs]
    names = [run.label for run in runs]
    total.barh(names, [s["energy_kwh"] for s in summaries], color=colors)
    per_job.barh(names, [s["energy_kwh"] / s["jobs_finished"] for s in summaries], color=colors)
    total.set(xlabel="Energy [kWh]")
    total.xaxis.set_major_formatter("{x:,.0f}")
    per_job.set(xlabel="Energy per Finished Job [kWh]")
    for bars in (total, per_job):
        bars.invert_yaxis()  # the first run on top, as in the key
        bars.grid(axis="y", visible=False)
