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
    "2.calibration.ipynb": """
def power(u, r):
    return P_IDLE + (P_MAX - P_IDLE) * (2 * u - u**r)
assert [round(power(0.5, 4)), round(power(0.5, 9)), round(power(0.8, 4))] == [165, 174, 202]

mape_per_r = errors.mean()
assert mape_per_r.idxmin() == 7 and 4.3 < mape_per_r[7] < 4.7 and 6.2 < mape_per_r[4] < 6.6
assert best_r_per_day.min() == 5 and best_r_per_day.max() == 9

assert 6.2 < no_calibration.mean() < 6.6 and 0.77 < (no_calibration < 10).mean() < 0.83
assert 3.4 < with_calibration.mean() < 3.9 and 0.88 < (with_calibration < 10).mean() < 0.94
under = pd.DataFrame({r: align(run).eval("measured > simulated") for r, run in sweep.items()})
under = under.resample("1h").mean()
assert 0.91 < under[4.0].mean() < 0.95 and 0.66 < self_calibrate(under, best_r).mean() < 0.72
assert worse.sum() == 5

assert 4.1 < with_24h.mean() < 4.5 and (with_24h > no_calibration).sum() == 20
assert (best_r == 9).sum() == 75
best_wide = hourly_wide.idxmin(axis=1)
assert 3.1 < with_wide.mean() < 3.5 and (best_wide == 12).sum() == 69
edge = best_wide.index[best_wide == 12]
under_12 = align(wider[12.0]).eval("measured > simulated").resample("1h").mean()
assert under_12[edge].mean() > 0.9
""",
    "3.co2_migration.ipynb": """
average = intensity.mean()
assert list(average.sort_values().index) == ["RO", "NL", "DE", "PL"]
assert [round(average["RO"]), round(average["NL"])] == [343, 373]
assert len(intensity) == 169 and (intensity["NL"] < intensity["RO"]).sum() == 57
assert [round(intensity["NL"].min()), round(intensity["NL"].max())] == [123, 528]

energy, co2 = table["energy_kwh"], table["co2_kg"]
assert energy.max() - energy.min() < 0.01 and round(energy.mean()) == 3424
assert [round(co2[zone]) for zone in ["RO", "NL", "DE", "PL"]] == [1172, 1253, 1726, 2959]
assert best == "RO" and round(saving) == 81 and round(saving / co2["NL"] * 100) == 6

assert round(co2_per_hour.min(axis=1).sum()) == 1065 and switches == 11
assert [round((1 - 1065 / co2[zone]) * 100) for zone in ["NL", "RO"]] == [15, 9]
half_summary = half.summary()
assert round(half_summary["co2_kg"]) == 971 and round((1 - half_summary["co2_kg"] / co2["NL"]) * 100) == 23
assert half_summary["jobs_waited"] == 2631 and round(half_summary["mean_wait_min"]) == 78
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
    notebook.cells.append(nbformat.v4.new_code_cell(CHECKS[name]))
    started = time.monotonic()
    nbclient.NotebookClient(
        notebook, timeout=900, resources={"metadata": {"path": str(TUTORIAL_DIR)}}
    ).execute()
    print(f"{name}: {time.monotonic() - started:.0f} s")
