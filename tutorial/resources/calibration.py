"""OpenDT's self-calibrator, replayed hour by hour on the simulations of the SURF week (notebook 2)."""

import pandas as pd

from .data import TRACE_END
from .metrics import error
from .sim import simulate_many


def hourly_mape(r_values) -> pd.DataFrame:
    """MAPE of each hour of the week [%], one column per r."""
    runs = simulate_many("r", r_values, until=TRACE_END)
    return pd.DataFrame({r: error(run) for r, run in runs.items()}).resample("1h").mean()


def self_calibrate(hourly: pd.DataFrame, grid, every: int = 1) -> pd.Series:
    """MAPE of each hour [%] when OpenDT simulates with the best r of `grid` in the last hour, recalibrating every
    `every` hours (r = 4 until the first calibration)."""
    best_r = hourly[grid].idxmin(axis=1)
    used_r = best_r.shift(1, fill_value=4).iloc[::every].reindex(best_r.index, method="ffill")
    return pd.Series([hourly.loc[h, r] for h, r in used_r.items()], index=hourly.index)


def compare_grids(grids: dict):
    """Simulations per window and MAPE over the week of the self-calibrating twin, for each grid of r."""
    hourly = hourly_mape(sorted({4, *(r for grid in grids.values() for r in grid)}))
    costs = {name: len(grid) for name, grid in grids.items()}
    mapes = {name: self_calibrate(hourly, grid).mean() for name, grid in grids.items()}
    return _table({"Simulations per window": costs, "MAPE [%]": mapes})


def compare_frequencies(grid, every):
    """Simulations per day and MAPE over the week of the self-calibrating twin, recalibrating every 1, 2, ... hours."""
    hourly = hourly_mape(sorted({4, *grid}))
    costs = {f"Every {hours} h": round(len(grid) * 24 / hours, 1) for hours in every}
    mapes = {f"Every {hours} h": self_calibrate(hourly, grid, hours).mean() for hours in every}
    return _table({"Simulations per day": costs, "MAPE [%]": mapes})


def _table(rows: dict):
    """One row per entry of `rows`, the costs with their own precision, the MAPEs with one decimal."""
    table = pd.DataFrame(rows).T
    cost = table.index[0]
    return table.style.format(precision=1).format("{:g}", subset=([cost], table.columns))
