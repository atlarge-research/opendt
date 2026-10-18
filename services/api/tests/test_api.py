"""The dashboard endpoints: the twin's status, the cluster over time, and the control panel."""

import json

import pytest
from api import hosts, levers, main, twin
from conftest import write_window
from fastapi import HTTPException
from odt_common import AppConfig
from odt_common.config import DynamicConfigEvent
from odt_common.models import Topology


@pytest.fixture
def api(run_dir, monkeypatch):
    """The API on the test run folder, with its Kafka messages collected instead of sent."""
    monkeypatch.setenv("DATA_DIR", str(run_dir.parent))
    monkeypatch.setenv("RUN_ID", run_dir.name)
    main.app.state.config = AppConfig(
        **{
            "global": {"speed_factor": -1},
            "services": {
                "dc-mock": {"workload": "SURF"},
                "simulator": {"background_load_nodes": 0},
            },
            "kafka": {
                "topics": {
                    "sim_topology": {"name": "sim.topology"},
                    "system": {"name": "sys.config"},
                }
            },
        }
    )
    main.app.state.kafka_producer = object()
    main.app.state.settings = {}
    main.app.state.topology = None
    sent = []
    monkeypatch.setattr(
        main,
        "send_message",
        lambda producer, topic, message, key=None: sent.append((topic, message, key)),
    )
    return sent


def data(response):
    return response["data"] if isinstance(response, dict) else json.loads(response.body)["data"]


def test_status(api):
    # flat, so the form fills its fields by name
    assert main.get_status() == {
        "twin_time": "2022-10-06T22:10:00+00:00",
        "servers": "2,770 SURF-SARA",
        "hosts": 2770,
        "calibration_factor": 4.0,
        "carbon_zone": "NL",
        "scheduler": "Mem",
        "speed_factor": -1,
        "calibration": False,  # and no settings of a calibrator: the test twin runs without one
    }


def test_cluster_range(api):
    rows = data(main.get_cluster(start="2022-10-06T22:05:00Z", end="2022-10-06T22:07:30Z"))
    assert [row["tasks_active"] for row in rows] == [11, 22]


def test_cluster_points(api):
    # a week has thousands of samples, more than some plots can draw
    # counted from the latest, which stays: one point is the latest sample, for the tiles
    rows = data(main.get_cluster(points=2))
    assert [row["tasks_active"] for row in rows] == [11, 23]
    assert [row["tasks_active"] for row in data(main.get_cluster(points=1))] == [23]


def sent_topology(api):
    [(topic, message, _)] = api
    assert topic == "sim.topology"
    return Topology(**message).clusters[0]


def test_control_hosts_and_zone(api):
    main.control(levers.Control(hosts=138, carbon_zone="RO"))
    cluster = sent_topology(api)
    assert cluster.hosts[0].count == 138
    assert cluster.powerSource.carbonTracePath == "/app/workload/carbon_zones/RO.parquet"
    # the rest stays as the twin had it
    assert cluster.hosts[0].cpuPowerModel.calibrationFactor == 4.0


def test_row_saved(api):
    main.edit_hosts(hosts.Row(id=1, kind="SURF-SARA", count=138))
    [h01] = sent_topology(api).hosts
    assert (h01.name, h01.count) == ("H01", 138)
    assert data(main.get_hosts())[0]["count"] == 138  # before the twin's next window runs it


def test_row_added(api):
    main.edit_hosts(hosts.Row(kind="Edge", count=10, cpu="Xeon E-2288G", memory_gb=32))
    _, edge = sent_topology(api).hosts
    assert (edge.name, edge.count, edge.cpu.coreCount) == ("Edge", 10, 8)
    assert edge.cpuPowerModel.calibrationFactor == 4.0  # the twin's r


def test_no_last_row(api):
    with pytest.raises(HTTPException) as refused:
        main.edit_hosts(hosts.Row(id=1, count=0))
    assert refused.value.status_code == 422 and not api


def test_control_speed(api):
    main.control(levers.Control(speed_factor=300))
    [(topic, message, key)] = api
    event = DynamicConfigEvent(**message)
    assert (topic, key) == ("sys.config", "global.speed_factor")  # a compacted topic needs a key
    assert (event.setting_key, event.new_value) == ("global.speed_factor", 300)
    assert main.get_status()["speed_factor"] == 300


def test_control_scheduler(api):
    main.control(levers.Control(scheduler="ActiveServers"))
    [(topic, event, key)] = api
    assert (topic, key, event["new_value"]) == (
        "sys.config",
        "simulator.scheduler",
        "ActiveServers",
    )


def test_control_parallel_runs(api):
    main.control(levers.Control(parallel_simulations=2))
    [(topic, event, key)] = api
    assert (topic, key, event["new_value"]) == ("sys.config", "calibrator.max_parallel_workers", 2)
    assert main.get_status()["parallel_simulations"] == 2


@pytest.mark.parametrize(
    "field, value, key",
    [
        ("calibration", True, "calibrator.enabled"),
        ("calibration_min", 4.0, "calibrator.min_value"),
        ("calibration_max", 12.0, "calibrator.max_value"),
        ("calibration_points", 10, "calibrator.linspace_points"),
        ("mape_window", 1440, "calibrator.mape_window_minutes"),
    ],
)
def test_control_calibration(api, field, value, key):
    main.control(levers.Control(**{field: value}))
    [(topic, event, sent)] = api
    assert (topic, sent, event["new_value"]) == ("sys.config", key, value)
    assert main.get_status()[field] == value


def test_control_builds_on_last_sent(api):
    # two changes within one window of operation: the second keeps the first
    main.control(levers.Control(hosts=138))
    main.control(levers.Control(carbon_zone="RO"))
    [_, (_, message, _)] = api
    cluster = Topology(**message).clusters[0]
    assert cluster.hosts[0].count == 138
    assert cluster.powerSource.carbonTracePath == twin.CARBON_TRACES["RO"]


def test_control_keeps_one_host():
    with pytest.raises(ValueError):
        levers.Control(hosts=0)


def test_control_rejects_speed_0():
    with pytest.raises(ValueError):
        levers.Control(speed_factor=0)


@pytest.mark.parametrize(
    "endpoint",
    [
        main.get_cluster,
        main.get_scheduling,
        main.get_jobs,
        main.get_events,
        main.get_accuracy,
        main.get_arrivals,
        main.get_hosts,
        main.get_totals,
    ],
    ids=lambda endpoint: endpoint.__name__,
)
def test_tables_empty_at_start(api, tmp_path, monkeypatch, endpoint):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "no_run_yet"))
    assert data(endpoint()) == []


def test_markers_time_format(api):
    assert data(main.get_events()) == [
        {
            "time": "2022-10-06T22:05:00.000Z",
            "text": "Hosts 277 SURF-SARA to 2,770 SURF-SARA",
            "by": "Manual",
        }
    ]


def test_markers_off(api):
    assert data(main.get_events(markers="off")) == []


def test_components():
    names = [component["name"] for component in data(main.get_components())]
    assert names == [*hosts.CPUS, "None", *hosts.GPUS]
    # a host can also have no GPU
    assert [gpu["name"] for gpu in data(main.get_components(part="GPU"))] == ["None", *hosts.GPUS]


def test_no_queue_time_without_starts(api, run_dir):
    write_window(run_dir, 3, 15, hosts=2770, active=[30])  # job 4 starts only at 22:20
    assert data(main.get_scheduling())[-1]["queue_median_min"] is None


def test_swagger_example_r():
    assert main.DEFAULT_TOPOLOGY.clusters[0].hosts[0].cpuPowerModel.calibrationFactor == 4.0
