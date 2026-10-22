"""Run each notebook top to bottom, then check the numbers its answers give."""

import pytest
from conftest import TUTORIAL_DIR

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

# every simulation of a notebook ships precomputed in resources/results/ (resources/precompute.py)
NO_OPENDC = """
import resources.sim


def no_opendc(*_args):
    raise RuntimeError("not precomputed: run python tutorial/resources/precompute.py")


resources.sim._run_opendc = no_opendc
"""
CHECKS = {
    "1.autoscaling.ipynb": """
SIX_H = TRACE_START + pd.Timedelta("6h")
assert [round(mape(day1)), round(mape(day1, end=SIX_H), 1), round(mape(day1, start=SIX_H), 1)] == [6, 10.4, 4.6]
assert align(day1).eval("measured > simulated").mean() > 0.99

power = table["avg_power_kw"]
assert [round(power[277]), round(power[2770]), round(power[2770] - power[277])] == [22, 84, 62]
assert round((1 - power[138] / power[277]) * 100) == 16
assert table.loc[138, "jobs_waited"] > 0 and table.loc[277, "jobs_waited"] == 0
assert table.loc[69, "mean_wait_min"] > 24 * 60 and table.loc[69, "waiting_at_end"] >= 100
assert in_use.max() == 160

assert round(saved_kwh / used_kwh * 100) == 16
for spare, share in [(0, 18), (50, 12)]:
    off = HOSTS - (in_use + spare).clip(upper=HOSTS)
    assert round((off * IDLE_POWER).mean() / 1000 * 24 / used_kwh * 100) == share
""",
    "2.calibration.ipynb": """
assert [round(curves["r = 4"][50]), round(curves["r = 9"][50]), round(curves["r = 4"][80])] == [165, 174, 202]
assert [round(curves[f"r = {r}"][u]) for u in [20, 80] for r in [2, 9]] == [79, 85, 168, 243]

mape_per_r = errors.mean()
assert mape_per_r.idxmin() == 7 and [round(mape_per_r[7], 1), round(mape_per_r[4], 1)] == [4.5, 6.4]
assert [best_r_per_day.min(), best_r_per_day.max()] == [5, 9]

noon = "2022-10-07 12:00"
assert [best_r[noon], used_r[noon]] == [7, 6]
assert [round(hourly.loc[noon, r], 1) for r in [6, 7, 4]] == [1.5, 0.8, 4.8]
assert [round(with_calibration.mean(), 1), round((with_calibration < 10).mean() * 100)] == [3.6, 91]
assert [round(hourly[4].mean(), 1), round((hourly[4] < 10).mean() * 100)] == [6.4, 80]

from resources.calibration import hourly_mape, self_calibrate
wide = hourly_mape([*range(1, 21), 30, 40])
assert [round(self_calibrate(wide, grid).mean(), 1) for grid in [*GRIDS.values(), list(range(1, 21))]] == [3.7, 4.2, 3.0]
assert wide.idxmin(axis=1).between(5, 9).sum() == 81
assert [round(self_calibrate(wide, R_VALUES, every=hours).mean(), 1) for hours in [1, 6, 24, 48]] == [3.6, 4.0, 4.8, 5.7]
""",
}


@pytest.mark.notebooks
@pytest.mark.parametrize("name", sorted(CHECKS))
def test_notebook_runs_and_tells_the_truth(name):
    notebook = nbformat.read(TUTORIAL_DIR / name, as_version=4)
    notebook.cells.insert(0, nbformat.v4.new_code_cell(NO_OPENDC))
    notebook.cells.append(nbformat.v4.new_code_cell(CHECKS[name]))
    nbclient.NotebookClient(
        notebook, timeout=900, resources={"metadata": {"path": str(TUTORIAL_DIR)}}
    ).execute()
