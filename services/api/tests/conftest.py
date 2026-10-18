"""A tiny run folder as the live twin writes it: two complete windows of operation and one unfinished."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # services/api, for `import api`

T0 = 1665093600000  # 2022-10-06 22:00 UTC, the first SURF job, in ms


def write_window(run_dir, n, minutes, hosts, active, zone_path="/app/workload/carbon.parquet"):
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
    pd.DataFrame({**base, "host_name": "H01-1", "cpu_utilization": 0.5}).to_parquet(
        out / "host.parquet"
    )
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
    end = pd.Timestamp(T0 + minutes * 60_000, unit="ms", tz="UTC")
    (window / "metadata.json").write_text(
        json.dumps({"run_number": n, "simulated_time": end.isoformat()})
    )
    return window


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / "run"
    write_window(run, 1, 5, hosts=277, active=[10, 11, 12])
    write_window(run, 2, 10, hosts=2770, active=[20, 21, 22, 23, 24])
    # an unfinished window: no metadata.json yet
    (run / "simulator" / "opendc" / "run_3" / "output").mkdir(parents=True)
    return run
