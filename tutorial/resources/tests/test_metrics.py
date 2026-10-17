"""Tests for comparing simulated with measured power, and the power plot."""

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from resources import TRACE_START, simulate
from resources.metrics import align, mape
from resources.plots import legend_above, plot_power

matplotlib.use("Agg")
T = pd.date_range(TRACE_START, periods=2, freq="60s")


def test_mape_known_value():
    measured = pd.Series([100.0, 200.0], index=T)
    simulated = pd.Series([110.0, 180.0], index=T)
    assert mape(simulated, measured) == pytest.approx(10.0)  # both samples are 10 % off


def test_align_mixed_sampling():
    """30-s measurements and 150-s simulation samples meet on a 60-s grid, interpolated in time."""
    measured = pd.Series(
        range(11), index=pd.date_range(TRACE_START, periods=11, freq="30s"), dtype=float
    )
    simulated = pd.Series([0.0, 150.0], index=[TRACE_START, TRACE_START + pd.Timedelta("150s")])
    both = align(simulated, measured)
    assert list(both.index) == list(pd.date_range(TRACE_START, periods=3, freq="60s"))
    at_2_min = both.loc[TRACE_START + pd.Timedelta("120s")]
    assert (at_2_min["simulated"], at_2_min["measured"]) == (120.0, 4.0)


@pytest.mark.opendc
def test_mape_of_the_first_day_is_below_the_paper_threshold():
    assert 1 < mape(simulate(until=TRACE_START + pd.Timedelta("24h"))) < 10  # NFR1: within 10 %


def test_legend_above_puts_the_key_in_one_row_above_the_axes():
    ax = plt.subplots()[1]
    for i in range(4):
        ax.plot([0, 1], [i, i], label=f"line {i}")
    legend_above(ax)
    ax.figure.canvas.draw()
    key = ax.get_legend()
    assert len({round(text.get_window_extent().y0) for text in key.get_texts()}) == 1
    assert key.get_window_extent().y0 >= ax.get_window_extent().y1


@pytest.mark.opendc
def test_plot_power_draws_measured_and_each_run_or_series():
    day = TRACE_START + pd.Timedelta("6h")
    run = simulate(until=day)
    ax = plot_power(run, run.power["power_draw"].rename("a power series [W]"))
    assert [line.get_label() for line in ax.lines] == [
        "Ground Truth",
        run.label,
        "a power series [W]",
    ]
    assert ax.get_ylabel() == "Power Draw [kW]" and ax.get_ylim()[0] == 0
