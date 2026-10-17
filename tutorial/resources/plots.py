"""Power draw plot: the ground truth measured at SURF and OpenDT's predictions."""

from __future__ import annotations

import matplotlib.pyplot as plt

from .data import measured_power
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


def plot_power(*results):
    """Ground truth (grey) and the predicted power draw of each SimResult or power series [W], in kW."""
    lines = [
        r.power["power_draw"].rename(r.label) if isinstance(r, SimResult) else r for r in results
    ]
    ax = plt.subplots()[1]
    end = max(line.index[-1] for line in lines)
    (measured_power(end=end) / 1000).plot(
        ax=ax, color="#999999", linestyle="-", label="Ground Truth"
    )
    for line in lines:
        (line / 1000).plot(ax=ax, label=line.name)
    ax.set(xlabel="Time [UTC]", ylabel="Power Draw [kW]", ylim=(0, None))
    legend_above(ax)
    return ax
