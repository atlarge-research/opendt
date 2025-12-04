"""Tests for Topology models."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from odt_common.models.topology import (
    CPU,
    AsymptoticCPUPowerModel,
    Cluster,
    Host,
    Memory,
    MseCPUPowerModel,
    Topology,
    TopologySnapshot,
)


@pytest.fixture
def sample_topology_data() -> dict:
    """Sample topology data matching SURF workload structure."""
    return {
        "clusters": [
            {
                "name": "A01",
                "hosts": [
                    {
                        "name": "A01",
                        "count": 277,
                        "cpu": {"coreCount": 16, "coreSpeed": 2100},
                        "memory": {"memorySize": 128000000},
                        "cpuPowerModel": {
                            "modelType": "asymptotic",
                            "power": 400,
                            "idlePower": 32,
                            "maxPower": 180,
                            "asymUtil": 0.3,
                            "dvfs": False,
                        },
                    }
                ],
            }
        ]
    }


def test_cpu_model():
    """Test CPU model validation."""
    cpu = CPU(coreCount=16, coreSpeed=2100.0)
    assert cpu.coreCount == 16
    assert cpu.coreSpeed == 2100.0

    # Test validation
    with pytest.raises(Exception):
        CPU(coreCount=0, coreSpeed=2100.0)  # Invalid: coreCount must be > 0


def test_memory_model():
    """Test Memory model validation."""
    memory = Memory(memorySize=128000000)
    assert memory.memorySize == 128000000

    # Test validation
    with pytest.raises(Exception):
        Memory(memorySize=0)  # Invalid: memorySize must be > 0


def test_cpu_power_model():
    """Test CPUPowerModel validation."""
    power_model = AsymptoticCPUPowerModel(
        modelType="asymptotic",
        power=400.0,
        idlePower=32.0,
        maxPower=180.0,
        asymUtil=0.3,
        dvfs=False,
    )
    assert power_model.modelType == "asymptotic"
    assert power_model.power == 400.0
    assert power_model.idlePower == 32.0
    assert power_model.maxPower == 180.0
    assert power_model.asymUtil == 0.3
    assert power_model.dvfs is False


def test_host_model():
    """Test Host model."""
    host = Host(
        name="A01",
        count=277,
        cpu=CPU(coreCount=16, coreSpeed=2100.0),
        memory=Memory(memorySize=128000000),
        cpuPowerModel=AsymptoticCPUPowerModel(
            modelType="asymptotic",
            power=400.0,
            idlePower=32.0,
            maxPower=180.0,
            asymUtil=0.3,
            dvfs=False,
        ),
    )
    assert host.name == "A01"
    assert host.count == 277
    assert host.cpu.coreCount == 16
    assert host.memory.memorySize == 128000000


def test_cluster_model():
    """Test Cluster model."""
    cluster = Cluster(
        name="A01",
        hosts=[
            Host(
                name="A01",
                count=277,
                cpu=CPU(coreCount=16, coreSpeed=2100.0),
                memory=Memory(memorySize=128000000),
                cpuPowerModel=AsymptoticCPUPowerModel(
                    modelType="asymptotic",
                    power=400.0,
                    idlePower=32.0,
                    maxPower=180.0,
                    asymUtil=0.3,
                    dvfs=False,
                ),
            )
        ],
    )
    assert cluster.name == "A01"
    assert len(cluster.hosts) == 1
    assert cluster.hosts[0].name == "A01"


def test_topology_model(sample_topology_data):
    """Test Topology model."""
    topology = Topology(**sample_topology_data)
    assert len(topology.clusters) == 1
    assert topology.clusters[0].name == "A01"


def test_topology_from_json(sample_topology_data):
    """Test creating Topology from JSON data."""
    topology = Topology(**sample_topology_data)

    # Verify structure
    assert len(topology.clusters) == 1
    cluster = topology.clusters[0]
    assert cluster.name == "A01"
    assert len(cluster.hosts) == 1

    host = cluster.hosts[0]
    assert host.name == "A01"
    assert host.count == 277
    assert host.cpu.coreCount == 16
    assert host.cpu.coreSpeed == 2100
    assert host.memory.memorySize == 128000000


def test_topology_calculations(sample_topology_data):
    """Test Topology utility methods."""
    topology = Topology(**sample_topology_data)

    # Test calculations
    assert topology.total_host_count() == 277
    assert topology.total_core_count() == 277 * 16  # 4432
    assert topology.total_memory_bytes() == 277 * 128000000


def test_topology_model_dump(sample_topology_data):
    """Test Topology serialization."""
    topology = Topology(**sample_topology_data)

    # Serialize back to dict
    dumped = topology.model_dump(mode="json")

    # Should be able to reconstruct
    topology2 = Topology(**dumped)
    assert topology2.total_host_count() == topology.total_host_count()
    assert topology2.total_core_count() == topology.total_core_count()


def test_topology_from_surf_file():
    """Test loading actual SURF topology file if it exists."""
    surf_topology_path = Path(__file__).parent.parent.parent.parent / "workload/SURF/topology.json"

    if not surf_topology_path.exists():
        pytest.skip("SURF topology file not found")

    with open(surf_topology_path) as f:
        data = json.load(f)

    topology = Topology(**data)
    assert len(topology.clusters) > 0
    assert topology.total_host_count() > 0
    assert topology.total_core_count() > 0


def test_topology_snapshot(sample_topology_data):
    """Test TopologySnapshot with timestamp."""
    topology = Topology(**sample_topology_data)
    timestamp = datetime(2022, 10, 7, 9, 14, 30)

    snapshot = TopologySnapshot(timestamp=timestamp, topology=topology)

    assert snapshot.timestamp == timestamp
    assert snapshot.topology == topology
    assert len(snapshot.topology.clusters) == 1


def test_topology_snapshot_serialization(sample_topology_data):
    """Test TopologySnapshot JSON serialization with proper timestamp format."""
    topology = Topology(**sample_topology_data)
    timestamp = datetime(2022, 10, 7, 9, 14, 30)

    snapshot = TopologySnapshot(timestamp=timestamp, topology=topology)

    # Serialize to dict
    snapshot_dict = snapshot.model_dump(mode="json")

    assert "timestamp" in snapshot_dict
    assert "topology" in snapshot_dict

    # Verify timestamp format (should be ISO 8601)
    assert isinstance(snapshot_dict["timestamp"], str)
    # Check it matches the expected format
    assert snapshot_dict["timestamp"] == "2022-10-07T09:14:30"

    # Verify we can reconstruct from the dict
    snapshot2 = TopologySnapshot(**snapshot_dict)
    assert snapshot2.topology.total_host_count() == topology.total_host_count()


def test_topology_snapshot_with_microseconds():
    """Test TopologySnapshot handles timestamps with microseconds."""
    topology = Topology(
        clusters=[
            Cluster(
                name="Test",
                hosts=[
                    Host(
                        name="H1",
                        count=1,
                        cpu=CPU(coreCount=8, coreSpeed=2000),
                        memory=Memory(memorySize=64000000),
                        cpuPowerModel=MseCPUPowerModel(
                            modelType="mse",
                            power=200,
                            idlePower=20,
                            maxPower=100,
                            calibrationFactor=0.5,
                        ),
                    )
                ],
            )
        ]
    )

    timestamp_with_micros = datetime(2022, 10, 7, 9, 14, 30, 123456)
    snapshot = TopologySnapshot(timestamp=timestamp_with_micros, topology=topology)

    snapshot_dict = snapshot.model_dump(mode="json")
    # With microseconds, should use full ISO format
    assert "T" in snapshot_dict["timestamp"]
