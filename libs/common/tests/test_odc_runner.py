"""What the runner writes for OpenDC: the experiment, with the twin's scheduler when one is chosen,
and the topology."""

import json

from odt_common.models import Topology
from odt_common.odc_runner import OpenDCRunner, environment, experiment


def runner(tmp_path):
    runner_bin = tmp_path / "OpenDCExperimentRunner"
    runner_bin.touch(mode=0o755)
    return OpenDCRunner(runner_bin)


def test_scheduler(tmp_path):
    run = experiment("run_1", tmp_path, tmp_path / "output", ["task"], "ActiveServers")
    assert run["allocationPolicies"] == [{"type": "prefab", "policyName": "ActiveServers"}]


def test_default_scheduler(tmp_path):
    assert "allocationPolicies" not in experiment("run_1", tmp_path, tmp_path / "output", ["task"])


def test_jvm_within_1_gb():
    assert "-Xmx1g" in environment()["OPEN_DC_EXPERIMENT_RUNNER_OPTS"]


def test_topology(tmp_path):
    # GPUs kept, and no nulls: OpenDC rejects them, e.g. for a host without GPUs
    host = {
        "name": "H01",
        "count": 1,
        "cpu": {"coreCount": 16, "coreSpeed": 2100},
        "memory": {"memorySize": 128_000_000},
        "cpuPowerModel": {"modelType": "mse", "power": 300, "idlePower": 25, "maxPower": 174},
    }
    gpu = {
        "gpu": {"count": 4, "coreCount": 6912, "coreSpeed": 1400, "memorySize": 40_000_000},
        "gpuPowerModel": {"modelType": "cubic", "power": 400, "idlePower": 100, "maxPower": 400},
    }
    topology = Topology(clusters=[{"name": "C01", "hosts": [host, {**host, **gpu, "name": "GPU"}]}])
    path = tmp_path / "topology.json"
    runner(tmp_path)._create_topology_json(topology, path)
    _, written = json.loads(path.read_text())["clusters"][0]["hosts"]
    assert "null" not in path.read_text() and written["gpu"]["count"] == 4
