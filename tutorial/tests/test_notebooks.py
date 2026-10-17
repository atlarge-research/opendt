"""Run each notebook top to bottom, then check the numbers its text talks about."""

import time

import pytest
from conftest import TUTORIAL_DIR

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

CHECKS = {
    "1.autoscaling.ipynb": """
SIX_H = TRACE_START + pd.Timedelta("6h")
assert 5 < mape(day1) < 7
assert 9 < mape(day1, end=SIX_H) < 12 and 3 < mape(day1, start=SIX_H, end=DAY) < 6
assert align(day1, end=DAY).eval("measured > simulated").mean() > 0.99

power = table["avg_power_kw"]
assert 3 < power[2770] / power[277] < 5 and abs(power[2770] - power[277] - 2493 * 0.025) < 1
assert 0.14 < 1 - power[138] / power[277] < 0.18
assert table.loc[138, "jobs_waited"] > 0 and table.loc[277, "jobs_waited"] == 0
assert table.loc[69, "mean_wait_min"] > 24 * 60 and table.loc[69, "waiting_at_end"] >= 100
assert 155 <= in_use.max() <= 165

assert 0.15 < saved_kwh / used_kwh < 0.18
for spare, share in [(0, 0.18), (50, 0.12)]:
    off = 277 - (in_use + spare).clip(upper=277)
    assert abs((off * IDLE_POWER * 150).sum() / 3.6e6 / used_kwh - share) < 0.01
assert 18.5 < low_idle.summary()["avg_power_kw"] < 19.5 and 15 < mape(low_idle) < 21
""",
}


@pytest.mark.notebooks
@pytest.mark.parametrize("name", sorted(CHECKS))
def test_notebook_runs_and_tells_the_truth(name):
    notebook = nbformat.read(TUTORIAL_DIR / name, as_version=4)
    notebook.cells.append(nbformat.v4.new_code_cell(CHECKS[name]))
    started = time.monotonic()
    nbclient.NotebookClient(
        notebook, timeout=900, resources={"metadata": {"path": str(TUTORIAL_DIR)}}
    ).execute()
    print(f"{name}: {time.monotonic() - started:.0f} s")
