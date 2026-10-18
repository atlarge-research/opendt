"""What the live twin has computed: its complete windows, the cluster over time, and its current state."""

import pandas as pd
from api import twin


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
    assert cluster["cpu_utilization"].tolist() == [0.5] * 4


def test_status_is_the_latest_complete_window(run_dir):
    status = twin.status(run_dir)
    assert status["twin_time"] == pd.Timestamp("2022-10-06 22:10", tz="UTC")
    assert (
        status["window"],
        status["hosts"],
        status["calibration_factor"],
        status["carbon_zone"],
    ) == (2, 2770, 4.0, "SURF")


def test_carbon_zone_comes_from_the_trace_path(tmp_path):
    from conftest import write_window

    write_window(
        tmp_path, 1, 5, hosts=277, active=[1], zone_path="/app/workload/carbon_zones/RO.parquet"
    )
    assert twin.status(tmp_path)["carbon_zone"] == "RO"
