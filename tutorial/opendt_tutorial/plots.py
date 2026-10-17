"""The plot every notebook uses: measured power next to the twin's predictions."""

from __future__ import annotations

import matplotlib.pyplot as plt

from .data import TRACE_START, measured_power, to_utc


def plot_power(*results, start=TRACE_START, end=None, ax=None):
    """Measured SURF power (grey) and the predicted power of each SimResult, in kW."""
    end = to_utc(end) if end is not None else max(r.until for r in results)
    ax = ax or plt.subplots(figsize=(10, 4))[1]
    ax.plot(measured_power(start, end) / 1000, color="#999999", label="measured at SURF")
    for result in results:
        ax.plot(result.power["power_draw"][to_utc(start) : end] / 1000, label=result.label)
    ax.set_ylabel("Power [kW]")
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend()
    return ax
