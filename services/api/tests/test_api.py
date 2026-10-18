"""The dashboard endpoints: the twin's status, the cluster over time, and the control panel."""

import asyncio

import pytest
from api import main
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
    main.app.state.speed_factor = None
    sent = []
    monkeypatch.setattr(
        main,
        "send_message",
        lambda producer, topic, message, key=None: sent.append((topic, message, key)),
    )
    return sent


def test_status_gives_the_control_panel_its_values(api):
    status = asyncio.run(main.get_status())  # flat, so the form fills its fields by name
    assert status == {
        "twin_time": "2022-10-06T22:10:00+00:00",
        "window": 2,
        "hosts": 2770,
        "calibration_factor": 4.0,
        "carbon_zone": "SURF",
        "speed_factor": -1,
    }


def test_cluster_can_be_cut_to_grafanas_time_range(api):
    rows = asyncio.run(main.get_cluster(start="2022-10-06T22:05:00Z", end="2022-10-06T22:07:30Z"))[
        "data"
    ]
    assert [row["tasks_active"] for row in rows] == [11, 22]


def test_control_changes_hosts_and_zone_of_the_current_topology(api):
    asyncio.run(main.control(main.Control(hosts=138, carbon_zone="RO")))
    [(topic, message, _)] = api
    cluster = Topology(**message).clusters[0]
    assert topic == "sim.topology" and cluster.hosts[0].count == 138
    assert cluster.powerSource.carbonTracePath == "/app/workload/carbon_zones/RO.parquet"
    assert (
        cluster.hosts[0].cpuPowerModel.calibrationFactor == 4.0
    )  # the rest stays as the twin had it


def test_control_sends_the_speed_to_the_data_source(api):
    asyncio.run(main.control(main.Control(speed_factor=300)))
    [(topic, message, key)] = api
    event = DynamicConfigEvent(**message)
    assert (topic, key) == ("sys.config", "global.speed_factor")  # a compacted topic needs a key
    assert (event.setting_key, event.new_value) == ("global.speed_factor", 300)
    assert asyncio.run(main.get_status())["speed_factor"] == 300


def test_control_rejects_a_speed_the_twin_cannot_use():
    with pytest.raises(ValueError):
        main.Control(speed_factor=0)


def test_cluster_is_empty_before_the_first_window(api, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "no_run_yet"))
    assert asyncio.run(main.get_cluster()) == {"data": []}


def test_swagger_example_uses_the_surf_power_model():
    assert main.DEFAULT_TOPOLOGY.clusters[0].hosts[0].cpuPowerModel.calibrationFactor == 4.0
