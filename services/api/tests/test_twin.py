"""What the live twin has computed: its complete windows, the cluster over time, and its current state."""

import numpy as np
import pandas as pd
import pytest
from api import twin
from conftest import write_window


def test_windows_are_complete_and_in_order(run_dir):
    assert [w.name for w in twin.windows(run_dir)] == ["run_1", "run_2"]


def test_cluster_stitches_each_windows_own_slice(run_dir):
    cluster = twin.cluster(run_dir)
    assert cluster["timestamp"].dt.strftime("%H:%M:%S").tolist() == [
        "22:02:30",
        "22:05:00",
        "22:07:30",
        "22:10:00",
    ]
    assert cluster["tasks_active"].tolist() == [10, 11, 22, 23]
    assert cluster["hosts_up"].tolist() == [277, 277, 2770, 2770]


def test_hosts_in_use_are_the_hosts_running_a_job(run_dir):
    assert twin.cluster(run_dir)["hosts_in_use"].tolist() == [1, 1, 1, 1]  # H01-2 only


def test_cluster_has_cpu_spread_and_demand(run_dir):
    cluster = twin.cluster(run_dir)
    last = cluster.iloc[-1]
    cpu = last[["cpu_utilization", "cpu_utilization_median", "cpu_utilization_p95"]].tolist()
    assert cpu == pytest.approx([0.4, 0.4, 0.58])
    # 3 + 12 of 2 x 16 cores
    assert last[["cpu_demand_cores", "cpu_capacity_cores"]].tolist() == [15, 32]


def test_energy_and_co2_add_up_per_period(run_dir):
    # per sample: 1 kWh, 100 g CO2, and 2 hosts x 500 g embodied CO2; samples at 22:02:30, 22:05, 22:07:30, 22:10
    [hour] = twin.totals(run_dir, "hour").to_dict("records")
    assert hour["timestamp"] == pd.Timestamp("2022-10-06 22:00", tz="UTC")
    assert (hour["energy_kwh"], hour["co2_kg"], hour["embodied_co2_kg"]) == pytest.approx(
        (4, 0.4, 4)
    )
    minutes = twin.totals(run_dir, "minute")
    assert minutes["timestamp"].dt.strftime("%H:%M").tolist()[::3] == ["22:02", "22:05", "22:08"]
    assert minutes["energy_kwh"].tolist() == [1, 0, 0, 1, 0, 1, 0, 0, 1]


def test_scheduling_forecasts_completion_and_queue_time_per_window(run_dir):
    scheduling = twin.scheduling(run_dir)
    assert scheduling["timestamp"].dt.strftime("%H:%M").tolist() == ["22:05", "22:10"]
    # the last job submitted so far ends at 23:00, then (with job 3) at 01:10
    assert scheduling["completion_h"].tolist() == pytest.approx([55 / 60, 3])
    # jobs started in each window's own slice: 1, 2, and 5 (0, 2, 1 min), then 3 (3 min)
    assert scheduling["queue_median_min"].tolist() == [1, 3]
    assert scheduling["queue_p95_min"].tolist() == pytest.approx([1.9, 3])


def test_jobs_left_at_twin_time_longest_first(run_dir):
    jobs = twin.jobs(run_dir)
    assert jobs["task_id"].tolist() == [3, 1, 4, 2]  # job 5 is done
    assert jobs["state"].tolist() == ["running", "running", "waiting", "running"]
    assert jobs["time_left_h"].tolist() == pytest.approx([3, 50 / 60, 40 / 60, 20 / 60])
    assert jobs["finish"].iloc[0] == pd.Timestamp("2022-10-07 01:10", tz="UTC")


def test_events_mark_topology_changes_where_they_apply(run_dir):
    write_window(run_dir, 3, 15, hosts=2770, active=[30], zone_path=twin.CARBON_TRACES["RO"])
    events = twin.events(run_dir)
    assert events["time"].dt.strftime("%H:%M").tolist() == ["22:05", "22:10"]
    assert events["text"].tolist() == ["Hosts 277 to 2,770", "Carbon zone Default to RO"]


def test_calibration_without_infinite_mape(run_dir):
    assert twin.calibration(run_dir).empty  # the calibrator is off
    (run_dir / "calibrator").mkdir()
    pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2022-10-06 22:05", "2022-10-06 22:10"], utc=True),
            "best_value": [3.0, 4.0],
            "best_mape": [5.2, np.inf],
        }
    ).to_parquet(run_dir / "calibrator" / "agg_results.parquet")
    calibration = twin.calibration(run_dir)
    assert calibration["r"].tolist() == [3, 4]
    assert calibration["mape"].isna().tolist() == [False, True]


def test_status_is_the_latest_complete_window(run_dir):
    status = twin.status(run_dir)
    assert status["twin_time"] == pd.Timestamp("2022-10-06 22:10", tz="UTC")
    assert (
        status["window"],
        status["hosts"],
        status["calibration_factor"],
        status["carbon_zone"],
    ) == (2, 2770, 4.0, "Default")


def test_carbon_zone_comes_from_the_trace_path(tmp_path):
    write_window(tmp_path, 1, 5, hosts=277, active=[1], zone_path=twin.CARBON_TRACES["RO"])
    assert twin.status(tmp_path)["carbon_zone"] == "RO"
