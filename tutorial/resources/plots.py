"""Power draw plot: the ground truth measured at SURF and OpenDT's predictions, and their MAPE per hour."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .data import measured_power
from .metrics import error
from .sim import SimResult

# The colours of the OpenDT paper figures (reproducibility-capsule/plots/config.py), colour-blind friendly;
# a line style per colour keeps the plots readable in grayscale.
plt.rcParams.update(
    {
        "axes.prop_cycle": plt.cycler(
            color=["#009E73", "#E69F00", "#338ec1", "#D55E00", "#9557a5", "#56B4E9", "#CC79A7"],
            linestyle=["-", "--", (0, (5, 1)), "-.", ":", (0, (3, 1, 1, 1, 1, 1)), (0, (1, 1))],
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

# One colour per run across notebook 1; OpenDT's own run has SURF's 277 hosts.
RUNS = {
    "OpenDT": ("#009E73", "-"),
    "hosts = 277": ("#009E73", "-"),
    "hosts = 69": ("#E69F00", "--"),
    "hosts = 138": ("#9557a5", ":"),
    "hosts = 2,770": ("#D55E00", "-."),
    "OpenDT, 2,770 hosts from 08:00": ("#338ec1", "-"),
}


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
        color, linestyle = RUNS.get(line.name, (None, None))
        (line / 1000).plot(ax=ax, label=line.name, color=color, linestyle=linestyle)
    ax.set(xlabel="Time [UTC]", ylabel="Power Draw [kW]", ylim=(0, None))
    legend_above(ax)
    if hourly_mape:
        xlim = ax.get_xlim()  # pandas fits the shared time axis to each plot's data
        for line in lines:
            color, linestyle = RUNS.get(line.name, (None, None))
            error(line).resample("1h").transform("mean").plot(
                ax=below, label=line.name, color=color, linestyle=linestyle
            )
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


MIX = Path(__file__).with_name(
    "electricity_mix_2022.csv"
)  # IEA, electricity generation by source in 2022 [GWh]
SOURCES = {
    "Coal": "Coal",
    "Natural gas": "Natural Gas",
    "Nuclear": "Nuclear",
    "Hydropower": "Hydropower",
    "Wind": "Wind",
    "Solar PV": "Solar PV",
}  # the rest (oil, biofuels, waste, ...) shows as Other


def plot_electricity_mix():
    """Share of each source in the electricity generation of NL, DE, RO, and PL in 2022 [%], from the IEA."""
    gwh = pd.read_csv(MIX, index_col="source")
    mix = gwh.loc[list(SOURCES)].rename(index=SOURCES)
    mix.loc["Other"] = gwh.drop(SOURCES).sum()
    share = (mix / mix.sum() * 100).T  # one row per country
    # none of the colours the countries have in the carbon intensity plot
    colors = ["#000000", "#CC79A7", "#9557a5", "#56B4E9", "#777777", "#F0E442", "#BBBBBB"]
    ax = share.plot.barh(
        stacked=True, color=colors, width=0.6, edgecolor="white", figsize=(10, 2.5)
    )
    for bars, hatch in zip(
        ax.containers, ["", "//", "..", "xx", "\\\\", "--", ""], strict=True
    ):  # readable in grayscale
        for bar in bars:
            bar.set_hatch(hatch)
    ax.set(xlabel="Share of Electricity Generation in 2022 [%]", xlim=(0, 100))
    ax.invert_yaxis()  # NL on top, as in the other plots
    ax.grid(axis="y", visible=False)
    legend_above(ax)
    return ax
