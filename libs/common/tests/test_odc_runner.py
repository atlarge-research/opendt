"""The OpenDC experiment file names the scheduler of the twin, when one is chosen."""

import json

from odt_common.odc_runner import OpenDCRunner


def experiment(tmp_path, **scheduler):
    runner_bin = tmp_path / "OpenDCExperimentRunner"
    runner_bin.touch(mode=0o755)
    path = tmp_path / "experiment.json"
    OpenDCRunner(runner_bin)._create_experiment_json(
        "run_1", tmp_path, tmp_path / "topology.json", path, str(tmp_path / "output"), **scheduler
    )
    return json.loads(path.read_text())


def test_scheduler(tmp_path):
    policies = experiment(tmp_path, scheduler="ActiveServers")["allocationPolicies"]
    assert policies == [{"type": "prefab", "policyName": "ActiveServers"}]


def test_default_scheduler(tmp_path):
    assert "allocationPolicies" not in experiment(tmp_path)
