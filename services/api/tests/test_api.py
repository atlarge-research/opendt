"""The dashboard endpoints: the twin's status, the cluster over time, and the control panel."""

import json

import pytest
from api import main, twin
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
    main.app.state.speed_factor = main.app.state.parallel_simulations = None
    main.app.state.topology = None
    sent = []
    monkeypatch.setattr(
        main,
        "send_message",
        lambda producer, topic, message, key=None: sent.append((topic, message, key)),
    )
    return sent


def data(response):
    return json.loads(response.body)["data"]


def test_status_gives_the_control_panel_its_values(api):
    # flat, so the form fills its fields by name
    assert main.get_status() == {
        "twin_time": "2022-10-06T22:10:00+00:00",
        "window": 2,
        "hosts": 2770,
        "servers": "2,770 SURF-SARA",
        "kind_1": "H01",
        "count_1": 2770,
        "kind_2": None,
        "count_2": 0,
        "kind_3": None,
        "count_3": 0,
        "calibration_factor": 4.0,
        "carbon_zone": "NL",
        "scheduler": "Mem",
        "speed_factor": -1,
        "parallel_simulations": None,  # the test twin runs without a calibrator
    }


def test_cluster_can_be_cut_to_grafanas_time_range(api):
    rows = data(main.get_cluster(start="2022-10-06T22:05:00Z", end="2022-10-06T22:07:30Z"))
    assert [row["tasks_active"] for row in rows] == [11, 22]


def sent_topology(api):
    [(topic, message, _)] = api
    assert topic == "sim.topology"
    return Topology(**message).clusters[0]


def test_control_changes_hosts_and_zone_of_the_current_topology(api):
    main.control(main.Control(count_1=138, carbon_zone="RO"))
    cluster = sent_topology(api)
    assert cluster.hosts[0].count == 138
    assert cluster.powerSource.carbonTracePath == "/app/workload/carbon_zones/RO.parquet"
    # the rest stays as the twin had it
    assert cluster.hosts[0].cpuPowerModel.calibrationFactor == 4.0


def test_control_adds_a_second_kind_of_server_with_the_twins_r(api):
    main.control(main.Control(kind_2="EPYC", count_2=40))
    surf, epyc = sent_topology(api).hosts
    assert (surf.name, surf.count, epyc.name, epyc.count) == ("H01", 2770, "EPYC", 40)
    assert (epyc.cpu.coreCount, epyc.cpu.coreSpeed) == (64, 3200)  # 2 x 32 cores at 3.2 GHz
    assert epyc.cpuPowerModel.calibrationFactor == 4.0


def test_control_swaps_a_kind_and_removes_a_group_set_to_zero(api):
    main.control(main.Control(kind_1="Edge", count_2=0))
    [edge] = sent_topology(api).hosts
    assert (edge.name, edge.count, edge.cpu.coreCount) == ("Edge", 2770, 8)


def test_control_rejects_a_kind_without_hosts(api):
    with pytest.raises(HTTPException) as error:
        main.control(main.Control(kind_2="EPYC"))
    assert (error.value.status_code, error.value.detail) == (422, "Hosts 2 need a count")
    assert not api


def test_control_sends_the_speed_to_the_data_source(api):
    main.control(main.Control(speed_factor=300))
    [(topic, message, key)] = api
    event = DynamicConfigEvent(**message)
    assert (topic, key) == ("sys.config", "global.speed_factor")  # a compacted topic needs a key
    assert (event.setting_key, event.new_value) == ("global.speed_factor", 300)
    assert main.get_status()["speed_factor"] == 300


def test_control_sends_the_scheduler_to_the_simulator(api):
    main.control(main.Control(scheduler="ActiveServers"))
    [(topic, event, key)] = api
    assert (topic, key, event["new_value"]) == (
        "sys.config",
        "simulator.scheduler",
        "ActiveServers",
    )


def test_control_sends_the_parallel_simulations_to_the_calibrator(api):
    main.control(main.Control(parallel_simulations=2))
    [(topic, event, key)] = api
    assert (topic, key, event["new_value"]) == ("sys.config", "calibrator.max_parallel_workers", 2)
    assert main.get_status()["parallel_simulations"] == 2


def test_control_builds_on_the_topology_it_sent_last(api):
    # two changes within one window of operation: the second keeps the first
    main.control(main.Control(count_1=138))
    main.control(main.Control(carbon_zone="RO"))
    [_, (_, message, _)] = api
    cluster = Topology(**message).clusters[0]
    assert cluster.hosts[0].count == 138
    assert cluster.powerSource.carbonTracePath == twin.CARBON_TRACES["RO"]


def test_control_rejects_a_speed_the_twin_cannot_use():
    with pytest.raises(ValueError):
        main.Control(speed_factor=0)


@pytest.mark.parametrize(
    "endpoint",
    [
        main.get_cluster,
        main.get_scheduling,
        main.get_jobs,
        main.get_events,
        main.get_accuracy,
        main.get_arrivals,
        main.get_servers,
        main.get_totals,
    ],
    ids=lambda endpoint: endpoint.__name__,
)
def test_tables_are_empty_before_the_first_window(api, tmp_path, monkeypatch, endpoint):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "no_run_yet"))
    assert data(endpoint()) == []


def test_markers_have_grafanas_time_format(api):
    assert data(main.get_events()) == [
        {"time": "2022-10-06T22:05:00.000Z", "text": "Hosts 277 SURF-SARA to 2,770 SURF-SARA"}
    ]


def test_a_window_without_jobs_starting_has_no_queue_time(api, run_dir):
    write_window(run_dir, 3, 15, hosts=2770, active=[30])  # job 4 starts only at 22:20
    assert data(main.get_scheduling())[-1]["queue_median_min"] is None


def test_swagger_example_uses_the_surf_power_model():
    assert main.DEFAULT_TOPOLOGY.clusters[0].hosts[0].cpuPowerModel.calibrationFactor == 4.0


def test_control_keeps_at_least_one_server(api):
    with pytest.raises(HTTPException) as refused:
        main.control(main.Control(count_1=0))
    assert refused.value.status_code == 422 and not api


def test_control_merges_groups_of_the_same_kind(api):
    main.control(main.Control(kind_2="EPYC", count_2=20, kind_3="EPYC", count_3=5))
    groups = [(host.name, host.count) for host in sent_topology(api).hosts]
    assert groups == [("H01", 2770), ("EPYC", 25)]


def test_server_kinds_are_the_ones_the_control_panel_offers():
    assert [kind["id"] for kind in data(main.get_server_kinds())] == list(twin.SERVERS)


def test_markers_can_be_switched_off(api):
    assert data(main.get_events(markers="off")) == []
