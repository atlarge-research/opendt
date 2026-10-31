"""The power the Dashboard plots and the MAPE compares, simulated and measured on one grid, and the CO2."""

from datetime import UTC, datetime

import pandas as pd
from api import carbon_query, power_query
from odt_common import WorkloadContext

T0 = datetime(2022, 10, 6, 22, tzinfo=UTC)


def run(tmp_path):
    """A workload measured at 0, 150, and 300 s after its first task, and a run that simulates 12 kW every
    minute at 500 gCO2/kWh."""
    workload = tmp_path / "workload"
    workload.mkdir()
    pd.DataFrame({"submission_time": [T0.replace(tzinfo=None)]}).to_parquet(
        workload / "tasks.parquet"
    )
    measured = {"timestamp": [0, 150_000, 300_000], "power_draw": [10000.0, 20000.0, 20000.0]}
    pd.DataFrame(measured).to_parquet(workload / "consumption.parquet")
    folder = tmp_path / "run"
    (folder / "simulator").mkdir(parents=True)
    times = pd.date_range(T0, periods=6, freq="60s")
    simulated = {"timestamp": times, "power_draw": 12000.0, "carbon_intensity": 500.0}
    pd.DataFrame(simulated).to_parquet(folder / "simulator/agg_results.parquet")
    return folder, WorkloadContext(workload_dir=workload)


def test_power(tmp_path):
    folder, workload = run(tmp_path)
    power = power_query.query(folder, workload, 60, None).data
    assert [p.actual_power for p in power] == [10000, 14000, 18000, 20000, 20000, 20000]
    assert {p.simulated_power for p in power} == {12000}


def test_co2(tmp_path):
    folder, _ = run(tmp_path)
    co2 = carbon_query.query(folder, 60, None).data
    assert [p.carbon_emission for p in co2] == [6000] * 6  # 12 kW x 500 gCO2/kWh = 6 kgCO2/h
