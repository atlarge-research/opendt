"""What the live twin has computed: its complete windows, the cluster over time, and its current state."""

import pandas as pd
import pytest
from api import twin
from conftest import JOBS, write_window


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
    # the mean of all hosts, the median of the hosts running a job (most hosts are idle; over all, it is 0)
    assert last[["cpu_utilization", "cpu_utilization_busy_median"]].tolist() == pytest.approx(
        [0.4, 0.6]
    )
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


def test_share_of_jobs_starting_within_10_minutes(run_dir):
    write_window(run_dir, 3, 25, hosts=2770, active=[30])
    # by 22:25, jobs 1, 2, 5, 3 start within 3 minutes, job 4 after 12
    assert twin.scheduling(run_dir)["started_in_10_min_pct"].tolist() == [100, 100, 80]


def test_jobs_arriving_per_hour(run_dir):
    write_window(run_dir, 3, 70, hosts=2770, active=[30], jobs=[*JOBS, (6, 65, 65, 90)])
    assert twin.arrivals(run_dir)["jobs"].tolist() == [5, 1]  # submitted 22:00-22:08, then 23:05


def test_hosts_per_cpu_utilization_bucket(run_dir):
    last = twin.cluster(run_dir).iloc[-1]
    buckets = [f"cpu_{low}_{low + 20}" for low in range(0, 100, 20)]
    assert last[buckets].tolist() == [0, 1, 0, 1, 0]  # one host at 20%, one at 60%


def test_server_groups_with_their_specs(run_dir):
    [surf] = twin.server_groups(run_dir).to_dict("records")
    assert surf == {
        "kind": "SURF-SARA",
        "count": 2770,
        "cores": 16,
        "ghz": 2.1,
        "memory_gb": 128,
        "idle_w": 25,
        "max_w": 174,
    }


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
    assert events["text"].tolist() == [
        "Hosts 277 SURF-SARA to 2,770 SURF-SARA",
        "CO₂ zone NL to RO",
    ]


def test_the_scheduler_comes_from_the_experiment_of_the_window(run_dir):
    write_window(run_dir, 3, 15, hosts=2770, active=[30], scheduler="ActiveServers")
    assert twin.status(run_dir)["scheduler"] == "ActiveServers"
    # without a scheduler, OpenDC runs Mem
    assert twin.events(run_dir)["text"].tolist()[-1] == "Scheduler Mem to ActiveServers"


def test_accuracy_is_the_hourly_mape_of_the_power_with_the_twins_r(run_dir):
    times = pd.to_datetime(["2022-10-06 22:00", "2022-10-06 22:30", "2022-10-06 23:00"], utc=True)
    power = pd.DataFrame(
        {"timestamp": times, "actual_power": 100.0, "simulated_power": [90.0, 110.0, 120.0]}
    )
    accuracy = twin.accuracy(run_dir, power)
    assert accuracy["timestamp"].dt.strftime("%H:%M").tolist() == ["22:00", "23:00"]
    assert accuracy["mape"].tolist() == pytest.approx([10, 20])
    assert accuracy["error_kw"].tolist() == pytest.approx(
        [0, 0.02]
    )  # OpenDT minus measured, signed
    assert accuracy["r"].tolist() == [4, 4]  # the r of the last window so far
    assert twin.accuracy(run_dir, power, minutes=30)["mape"].tolist() == pytest.approx([10, 10, 20])


def test_status_is_the_latest_complete_window(run_dir):
    status = twin.status(run_dir)
    assert status["twin_time"] == pd.Timestamp("2022-10-06 22:10", tz="UTC")
    assert (
        status["window"],
        status["hosts"],
        status["calibration_factor"],
        status["carbon_zone"],
    ) == (2, 2770, 4.0, "NL")


def test_carbon_zone_comes_from_the_trace_path(tmp_path):
    write_window(tmp_path, 1, 5, hosts=277, active=[1], zone_path=twin.CARBON_TRACES["RO"])
    assert twin.status(tmp_path)["carbon_zone"] == "RO"
