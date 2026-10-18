"""A tiny run folder as the live twin writes it: two complete windows of operation and one unfinished."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # services/api, for `import api`

T0 = 1665093600000  # 2022-10-06 22:00 UTC, the first SURF job, in ms
MIN = 60_000

# Jobs as (id, submitted, started, finished), in minutes after T0; window 1 sees the first three, window 2 all.
JOBS = [
    (1, 0, 0, 60),
    (2, 1, 3, 30),  # waits 2 minutes
    (5, 1, 2, 4),  # waits 1 minute, done by 22:05
    (3, 6, 9, 190),  # waits 3 minutes
    (4, 8, 20, 50),  # still waiting at 22:10
]


def write_window(
    run_dir,
    n,
    minutes,
    hosts,
    active,
    zone_path="/app/workload/carbon.parquet",
    jobs=JOBS,
    scheduler=None,
):
    """Window n ends `minutes` after T0; OpenDC output every 150 s, up to one sample past the end."""
    window = run_dir / "simulator" / "opendc" / f"run_{n}"
    out = window / "output" / f"run_{n}" / "raw-output" / "0" / "seed=0"
    out.mkdir(parents=True)
    times = [T0 + 150_000 * (i + 1) for i in range(len(active))]
    base = {"timestamp": [t - T0 for t in times], "timestamp_absolute": times}
    pd.DataFrame(
        {
            **base,
            "hosts_up": hosts,
            "tasks_pending": 0,
            "tasks_active": active,
            "tasks_completed": 0,
        }
    ).to_parquet(out / "service.parquet")
    # two hosts, at 20% and 60% CPU; 16 cores at 2,100 MHz each, the busier one demanding 12 of them
    # and running two jobs
    pd.concat(
        pd.DataFrame(
            {
                **base,
                "host_name": name,
                "core_count": 16,
                "cpu_capacity": 33600.0,
                "cpu_demand": demand,
                "cpu_utilization": utilization,
                "tasks_running": running,
                "embodied_carbon": 500.0,
            }
        )
        for name, utilization, demand, running in [
            ("H01-1", 0.2, 6300.0, 0),
            ("H01-2", 0.6, 25200.0, 2),
        ]
    ).to_parquet(out / "host.parquet")
    # 1 kWh and 100 g CO2 per sample
    pd.DataFrame({**base, "energy_usage": 3.6e6, "carbon_emission": 100.0}).to_parquet(
        out / "powerSource.parquet"
    )
    # OpenDC writes a job's row at every sample; the last row has its final times
    times = ["submission_time", "schedule_time", "finish_time"]
    rows = [(i, s, None, None) for i, s, *_ in jobs] + jobs
    tasks = pd.DataFrame(rows, columns=["task_id", *times])
    tasks[times] = tasks[times].astype(float) * MIN
    tasks.assign(timestamp=0, timestamp_absolute=T0).to_parquet(out / "task.parquet")
    topology = {
        "clusters": [
            {
                "name": "C01",
                "hosts": [
                    {
                        "name": "H01",
                        "count": hosts,
                        "cpu": {"coreCount": 16, "coreSpeed": 2100},
                        "memory": {"memorySize": 128000000},
                        "cpuPowerModel": {
                            "modelType": "mse",
                            "power": 300.0,
                            "idlePower": 25.0,
                            "maxPower": 174.0,
                            "calibrationFactor": 4.0,
                        },
                    }
                ],
                "powerSource": {"carbonTracePath": zone_path},
            }
        ]
    }
    (window / "input").mkdir()
    (window / "input" / "topology.json").write_text(json.dumps(topology))
    policies = [{"type": "prefab", "policyName": scheduler}] if scheduler else []
    (window / "input" / "experiment.json").write_text(json.dumps({"allocationPolicies": policies}))
    end = pd.Timestamp(T0 + minutes * MIN, unit="ms", tz="UTC")
    (window / "metadata.json").write_text(
        json.dumps({"run_number": n, "simulated_time": end.isoformat()})
    )
    return window


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / "run"
    write_window(run, 1, 5, hosts=277, active=[10, 11, 12], jobs=JOBS[:3])
    write_window(run, 2, 10, hosts=2770, active=[20, 21, 22, 23, 24])
    # an unfinished window: no metadata.json yet
    (run / "simulator" / "opendc" / "run_3" / "output").mkdir(parents=True)
    return run
