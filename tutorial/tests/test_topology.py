"""Tests for building simulated datacenter topologies."""

import json

import pytest
from conftest import REPO
from odt_common.models import Topology
from opendt_tutorial.data import carbon_trace_path
from opendt_tutorial.topology import make_topology


def test_default_topology_matches_surf():
    """Default = OpenDT's own SURF topology, incl. its own carbon trace (as a host path)."""
    ref = json.loads((REPO / "workload/SURF/topology.json").read_text())
    ref["clusters"][0]["powerSource"]["carbonTracePath"] = str(
        REPO / "workload/SURF/carbon.parquet"
    )
    assert make_topology().model_dump(mode="json") == Topology(**ref).model_dump(mode="json")


def test_parameters_reach_the_host_and_power_source():
    host = make_topology(hosts=138, r=7.5, idle_power=10, max_power=150, carbon="RO").clusters[0]
    assert host.hosts[0].count == 138
    model = host.hosts[0].cpuPowerModel
    assert (model.calibrationFactor, model.idlePower, model.maxPower) == (7.5, 10, 150)
    assert host.powerSource.carbonTracePath == str(carbon_trace_path("RO"))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"hosts": 0},
        {"hosts": -5},
        {"r": 60},
        {"r": -1},
        {"idle_power": 200},
        {"idle_power": -1},
        {"carbon": "XX"},
    ],
)
def test_make_topology_rejects_nonsense(kwargs):
    with pytest.raises(ValueError):
        make_topology(**kwargs)
