"""What the runner writes for OpenDC: the experiment, with the twin's scheduler when one is chosen,
the topology, and the tasks cut after the run's time; and that OpenDC's output stays the same."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from odt_common.models import Fragment, Task, Topology
from odt_common.odc_runner import HORIZON, OpenDCRunner, environment, experiment
from odt_common.odc_runner.runner import cut

REPO = Path(__file__).resolve().parents[3]
T0 = datetime(2022, 10, 6, 22, tzinfo=UTC)  # the first SURF job


def runner(tmp_path):
    runner_bin = tmp_path / "OpenDCExperimentRunner"
    runner_bin.touch(mode=0o755)
    return OpenDCRunner(runner_bin)


def task(id, submitted, minutes, cores):
    """Submitted `submitted` minutes after T0, `minutes` long on `cores` cores; 30-s fragments."""
    fragment = Fragment(id=id, duration=30_000, cpu_count=cores, cpu_usage=2100.0)
    return Task(
        id=id,
        submission_time=T0 + timedelta(minutes=submitted),
        duration=minutes * 60_000,
        cpu_count=cores,
        cpu_capacity=cores * 2100.0,
        mem_capacity=1000,
        fragments=[fragment] * (2 * minutes),
    )


def test_cut():
    # submitted a minute after T0: by T0 + 105 s, it has run 45 s at most
    assert [f.duration for f in cut(task(1, 1, 2, 16), T0 + timedelta(seconds=105))] == [
        30_000,
        15_000,
    ]
    assert cut(task(1, 1, 2, 16), T0 + timedelta(hours=1)) == task(1, 1, 2, 16).fragments


def test_cut_tasks_give_the_same_output(tmp_path):
    """Up to HORIZON past the run's time, OpenDC's output for the cut tasks is the whole tasks'; the
    future run has the whole tasks' times."""
    # one host: the second task waits for the first, which runs past the HORIZON
    tasks = [task(1, 0, 120, 16), task(2, 1, 60, 16), task(3, 20, 10, 8)]
    host = {
        "name": "H01",
        "count": 1,
        "cpu": {"coreCount": 16, "coreSpeed": 2100},
        "memory": {"memorySize": 128_000_000},
        "cpuPowerModel": {"modelType": "mse", "power": 300, "idlePower": 25, "maxPower": 174},
    }
    trace = str(REPO / "workload/SURF/carbon_zones/NL.parquet")
    topology = Topology(
        clusters=[{"name": "C01", "hosts": [host], "powerSource": {"carbonTracePath": trace}}]
    )
    opendc = OpenDCRunner(REPO / "opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner")
    now, exports = T0 + timedelta(minutes=30), ("powerSource", "host", "service")
    assert opendc.run_simulation(
        tasks, topology, tmp_path / "cut", 1, now, exports=exports, future=True
    )[0]
    # a day later, nothing is cut
    whole = T0 + timedelta(days=1)
    assert opendc.run_simulation(
        tasks, topology, tmp_path / "whole", 1, whole, exports=(*exports, "task")
    )[0]

    def read(run, name):
        return pd.read_parquet(
            next((tmp_path / run).glob(f"output/*/raw-output/0/seed=0/{name}.parquet"))
        )

    for name in exports:
        outputs = read("cut", name), read("whole", name)
        assert len(outputs[0]) < len(outputs[1])  # OpenDC stopped sooner
        before = (o[o["timestamp_absolute"] < (now + HORIZON).timestamp() * 1000] for o in outputs)
        pd.testing.assert_frame_equal(*before)
    times = (read(run, "task").drop_duplicates("task_id", keep="last") for run in ("cut", "whole"))
    pd.testing.assert_frame_equal(*times)


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
