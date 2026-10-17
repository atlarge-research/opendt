"""MAPE between OpenDT's predicted power draw and the ground truth measured at SURF."""

from __future__ import annotations

import pandas as pd

from .data import TRACE_END, TRACE_START, measured_power, to_utc
from .sim import SimResult


def align(simulated, measured=None, start=TRACE_START, end=TRACE_END) -> pd.DataFrame:
    """Simulated and measured power [W] on a common 60-s grid, interpolated in time.

    Same alignment as OpenDT's calibrator (services/calibrator/calibrator/mape_comparator.py).
    `simulated` is a SimResult or a power series; `measured` defaults to SURF's measurements.
    """
    if isinstance(simulated, SimResult):
        simulated = simulated.power["power_draw"]
    if measured is None:
        measured = measured_power()
    start = max(to_utc(start), simulated.index[0], measured.index[0])
    end = min(to_utc(end), simulated.index[-1], measured.index[-1])
    grid = pd.date_range(start, end, freq="60s")
    both = pd.DataFrame({"simulated": simulated, "measured": measured})
    return both.reindex(both.index.union(grid)).interpolate("time").reindex(grid)


def mape(simulated, measured=None, start=TRACE_START, end=TRACE_END) -> float:
    """Mean absolute percentage error [%]: the average of |measured - simulated| / measured."""
    both = align(simulated, measured, start, end)
    return float(((both["measured"] - both["simulated"]).abs() / both["measured"]).mean() * 100)
