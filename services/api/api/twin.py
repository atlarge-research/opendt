"""What the live twin has computed so far, read from its windows of operation.

Every window (simulator/opendc/run_<N>/) re-simulates the trace from the start with the topology of that moment;
metadata.json is written last, so a window without it is still running.
"""

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

SERVICE = ("hosts_up", "tasks_pending", "tasks_active", "tasks_completed")
# Carbon intensity traces inside the containers: OpenDT's own (SURF) and the Electricity Maps zones.
CARBON_TRACES = {
    "SURF": "/app/workload/carbon.parquet",
    **{zone: f"/app/workload/carbon_zones/{zone}.parquet" for zone in ("NL", "DE", "RO", "PL")},
}


def windows(run_dir: Path) -> list[Path]:
    """The complete windows, in order."""
    done = (run_dir / "simulator" / "opendc").glob("run_*/metadata.json")
    return sorted((m.parent for m in done), key=lambda w: int(w.name.split("_")[1]))


@lru_cache(maxsize=4096)  # a complete window never changes
def end_time(window: Path) -> pd.Timestamp:
    return pd.Timestamp(json.loads((window / "metadata.json").read_text())["simulated_time"])


def topology(window: Path) -> dict:
    """The topology the window used, as OpenDC read it."""
    return json.loads((window / "input" / "topology.json").read_text())


def describe(topology: dict) -> dict:
    """Hosts, power-model exponent r, and carbon zone of a topology."""
    cluster = topology["clusters"][0]
    path = cluster["powerSource"]["carbonTracePath"]
    return {
        "hosts": sum(host["count"] for host in cluster["hosts"]),
        "calibration_factor": cluster["hosts"][0]["cpuPowerModel"]["calibrationFactor"],
        "carbon_zone": next(zone for zone, trace in CARBON_TRACES.items() if trace == path),
    }


def read(window: Path, name: str, columns: tuple[str, ...]) -> pd.DataFrame:
    """One OpenDC output file of the window, with UTC timestamps."""
    path = next(window.glob(f"output/*/raw-output/0/seed=0/{name}.parquet"))
    df = pd.read_parquet(path, columns=["timestamp_absolute", *columns])
    df.insert(0, "timestamp", pd.to_datetime(df.pop("timestamp_absolute"), unit="ms", utc=True))
    return df


@lru_cache(maxsize=4096)  # a complete window never changes
def cluster_slice(window: Path, start: pd.Timestamp | None, end: pd.Timestamp) -> pd.DataFrame:
    """Hosts and jobs (service output) and mean CPU utilization (host output) between start and end."""
    service = read(window, "service", SERVICE)
    hosts = read(window, "host", ("cpu_utilization",)).groupby("timestamp", as_index=False).mean()
    both = service.merge(hosts, on="timestamp")
    keep = (
        both["timestamp"] <= end
        if start is None
        else both["timestamp"].between(start, end, "right")
    )
    return both[keep]


def cluster(run_dir: Path) -> pd.DataFrame:
    """The cluster over time: each window contributes its own slice, from the previous window's end to its own."""
    slices, start = [], None
    for window in windows(run_dir):
        end = end_time(window)
        slices.append(cluster_slice(window, start, end))
        start = end
    return pd.concat(slices, ignore_index=True)


def status(run_dir: Path) -> dict:
    """The twin's current time and topology, from the latest complete window."""
    window = windows(run_dir)[-1]
    return {
        "twin_time": end_time(window),
        "window": int(window.name.split("_")[1]),
        **describe(topology(window)),
    }
