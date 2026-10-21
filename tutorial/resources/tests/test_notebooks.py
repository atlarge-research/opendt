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

mape_per_r = errors.mean()
assert mape_per_r.idxmin() == 7 and [round(mape_per_r[7], 1), round(mape_per_r[4], 1)] == [4.5, 6.4]
assert [best_r_per_day.min(), best_r_per_day.max()] == [5, 9]

assert [round(no_calibration.mean(), 1), round((no_calibration < 10).mean() * 100)] == [6.4, 80]
assert [round(with_calibration.mean(), 1), round((with_calibration < 10).mean() * 100)] == [3.6, 91]
under = pd.DataFrame({r: align(run).eval("measured > simulated") for r, run in sweep.items()})
under = under.resample("1h").mean()
assert [round(under[4].mean() * 100), round(self_calibrate(under, best_r).mean() * 100)] == [93, 69]
assert [worse.sum(), len(worse)] == [5, 168]

assert [round(with_24h.mean(), 1), (with_24h > no_calibration).sum()] == [4.3, 20]
assert (best_r == 9).sum() == 75
assert [round(with_wide.mean(), 1), (best_r_wide == 12).sum()] == [3.3, 69]
edge = best_r_wide.index[best_r_wide == 12]
assert align(sweep_wide[12]).eval("measured > simulated").resample("1h").mean()[edge].mean() > 0.9
""",
    "3.co2_migration.ipynb": """
average = intensity.mean()
assert len(intensity) == 168 and list(average.sort_values().index) == ["RO", "NL", "DE", "PL"]
assert [round(average["RO"]), round(average["NL"])] == [343, 372]
assert (intensity["NL"] < intensity["RO"]).sum() == 57
assert [round(intensity["NL"].min()), round(intensity["NL"].max())] == [123, 528]

energy = table["energy_kwh"]
assert energy.max() - energy.min() < 0.01 and round(energy.mean()) == 3424
assert [round(co2[zone]) for zone in ["RO", "NL", "DE", "PL"]] == [1172, 1253, 1726, 2959]
assert best == "RO" and round(saving) == 81 and round(saving / co2["NL"] * 100) == 6

assert round(co2_per_hour.min(axis=1).sum()) == 1065 and switches == 11 and set(greenest) == {"NL", "RO"}
assert [round((1 - 1065 / co2[zone]) * 100) for zone in ["NL", "RO"]] == [15, 9]
half_co2 = half.summary()["co2_kg"]
assert [round(half_co2), round((1 - half_co2 / co2["NL"]) * 100)] == [971, 23]
assert [half.summary()["jobs_waited"], round(half.summary()["mean_wait_min"])] == [2631, 78]
""",
}


def test_live_twin_notebook_compiles():
    """Notebook 4 needs the Docker twin to run; here we only check that its code is valid Python."""
    notebook = nbformat.read(TUTORIAL_DIR / "4.live_twin.ipynb", as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            compile(cell.source, "4.live_twin.ipynb", "exec")


@pytest.mark.notebooks
@pytest.mark.parametrize("name", sorted(CHECKS))
def test_notebook_runs_and_tells_the_truth(name):
    notebook = nbformat.read(TUTORIAL_DIR / name, as_version=4)
    notebook.cells.insert(0, nbformat.v4.new_code_cell(NO_OPENDC))
    notebook.cells.append(nbformat.v4.new_code_cell(CHECKS[name]))
    nbclient.NotebookClient(
        notebook, timeout=900, resources={"metadata": {"path": str(TUTORIAL_DIR)}}
    ).execute()
