"""Write the trace's first day, from the notebooks' precomputed simulations, for the plots of fixed data on the live
twin's Tutorial screen; the dashboards embed it (services/grafana/dashboards/build.py).

From the repository root: python tutorial/resources/make_first_day.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the tutorial folder, for `resources`
from resources import TRACE_END, TRACE_START, align, simulate, simulate_many  # noqa: E402
from resources.metrics import error  # noqa: E402

DAY = TRACE_START + pd.Timedelta("24h")


def write(table, name):
    """The table as CSV, in this folder, each row at its hours since the trace start."""
    table.insert(0, "hours", (table.index - TRACE_START) / pd.Timedelta("1h"))
    table.round(3).to_csv(Path(__file__).with_name(name), index=False)


if __name__ == "__main__":
    # step 1: notebook 1's first day, OpenDT vs. the ground truth [kW], and the MAPE of each hour [%]
    day1 = simulate(until=DAY, label="OpenDT")
    both = align(day1)
    power = pd.DataFrame({"truth": both["measured"] / 1000, "opendt": both["simulated"] / 1000})
    power["mape"] = error(day1).resample("1h").transform("mean")
    write(power, "first_day_power.csv")

    # step 7: notebook 2's self-calibration, each hour with the r of the lowest MAPE in the hour before, vs. no
    # calibration (r = 4): the MAPE of each hour [%], and the r used
    sweep = simulate_many("r", [3, 4, 5, 6, 7, 8, 9], until=TRACE_END)
    hourly = pd.DataFrame({r: error(run) for r, run in sweep.items()}).resample("1h").mean()
    used_r = hourly.idxmin(axis=1).shift(1, fill_value=4)
    calibrated = pd.Series([hourly.loc[h, r] for h, r in used_r.items()], index=hourly.index)
    calibration = pd.DataFrame({"r4": hourly[4], "calibrated": calibrated, "r": used_r})
    calibration = calibration.loc[: DAY - pd.Timedelta("1h")]
    calibration.loc[DAY] = calibration.iloc[-1]  # the last hour drawn to its end
    write(calibration, "first_day_calibration.csv")
