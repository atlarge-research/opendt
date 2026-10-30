"""The MAPE of the simulated power against the measured power, as the calibrator compares them."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def mape(
    simulated: pd.DataFrame, measured: pd.DataFrame, end: datetime, window: timedelta
) -> tuple[float, datetime | None]:
    """MAPE [%] of `simulated` vs. `measured` (columns timestamp, power_draw) over the `window` before
    `end`, from where both have data on: each interpolated in time onto a 60-s grid, without the minutes
    measured at 0 W; inf if there is nothing to compare. With the window's start."""
    if simulated.empty or measured.empty:
        return float("inf"), None
    sim = simulated.set_index(pd.to_datetime(simulated["timestamp"]))["power_draw"]
    real = measured.set_index(pd.to_datetime(measured["timestamp"]))["power_draw"]
    start = max(end - window, sim.index.min(), real.index.min())
    sim = sim[(sim.index >= start) & (sim.index <= end)]
    real = real[(real.index >= start) & (real.index <= end)]
    if sim.empty or real.empty:
        return float("inf"), start
    first, last = max(sim.index.min(), real.index.min()), min(sim.index.max(), real.index.max())
    if first >= last:
        return float("inf"), start
    grid = pd.date_range(first, last, freq="60s")
    sim, real = (
        s.reindex(s.index.union(grid)).interpolate(method="time").reindex(grid) for s in (sim, real)
    )
    both = pd.DataFrame({"sim": sim.to_numpy(), "real": real.to_numpy()}).dropna()
    both = both[both["real"] != 0]
    if both.empty:
        return float("inf"), start
    real, sim = both["real"].to_numpy(), both["sim"].to_numpy()
    return float(np.mean(np.abs((real - sim) / real) * 100)), start
