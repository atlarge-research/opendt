"""What the live twin has computed so far, read from its windows of operation.

Every window (simulator/opendc/run_<N>/) re-simulates the trace from the start with the topology of that moment;
metadata.json is written last, so a window without it is still running.
"""

import json
import threading
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

import pandas as pd

SERVICE = ("hosts_up", "tasks_pending", "tasks_active", "tasks_completed")
HOST = (
    "core_count",
    "cpu_capacity",
    "cpu_demand",
    "cpu_utilization",
    "tasks_running",
    "embodied_carbon",
)
# Carbon intensity traces inside the containers: OpenDT's own (the default) and the Electricity Maps zones.
CARBON_TRACES = {
    "Default": "/app/workload/carbon.parquet",
    **{zone: f"/app/workload/carbon_zones/{zone}.parquet" for zone in ("NL", "DE", "RO", "PL")},
}
SETTINGS = {
    "servers": "Servers",
    "calibration_factor": "r",
    "carbon_zone": "Carbon zone",
    "scheduler": "Scheduler",
}
PERIODS = {"minute": "min", "hour": "h", "day": "D", "week": "W-MON", "month": "MS", "year": "YS"}
LOCK = threading.Lock()  # the panels of a dashboard ask at once; a new window is computed once
GROUPS = 3  # kinds of servers the control panel can mix


def server(
    cores: int, mhz: float, memory: int, idle: float, top: float, power: float | None = None
):
    power_model = {"modelType": "mse", "power": power or top, "idlePower": idle, "maxPower": top}
    return {
        "cpu": {"coreCount": cores, "coreSpeed": mhz},
        "memory": {"memorySize": memory},
        "cpuPowerModel": power_model,
    }


# SURF's node (H01) and four host templates of OpenDC web (Daniel Halasz, branch feat/refactor-web) in OpenDT's
# format: all cores of a server, MHz, memory in SURF's unit (128 GB is 128,000,000), and OpenDT's mse power model
# with the template's idle and maximum power. The twin's r applies to every kind; an assumption.
SERVERS = {
    "H01": server(16, 2100, 128_000_000, idle=25, top=174, power=300),
    "EPYC": server(64, 3200, 256_000_000, idle=120, top=400),  # 2x AMD EPYC 7502
    "Xeon": server(40, 2500, 192_000_000, idle=90, top=300),  # 2x Intel Xeon Gold 6248
    "Memory": server(48, 2900, 1_024_000_000, idle=140, top=350),  # 2x Intel Xeon Gold 6248R, 1 TiB
    "Edge": server(8, 3700, 32_000_000, idle=25, top=95),  # Intel Xeon E-2288G
}


def windows(run_dir: Path) -> list[Path]:
    """The complete windows, in order."""
    done = (run_dir / "simulator" / "opendc").glob("run_*/metadata.json")
    return sorted((m.parent for m in done), key=lambda w: int(w.name.split("_")[1]))


@lru_cache(maxsize=4096)  # a complete window never changes
def end_time(window: Path) -> pd.Timestamp:
    return pd.Timestamp(json.loads((window / "metadata.json").read_text())["simulated_time"])


def slices(run_dir: Path):
    """Each complete window with its own slice of time, (start, end]: from the previous window's end to its own."""
    start = None
    for window in windows(run_dir):
        end = end_time(window)
        yield window, start, end
        start = end


def topology(window: Path) -> dict:
    """The topology the window used, as OpenDC read it."""
    return json.loads((window / "input" / "topology.json").read_text())


@lru_cache(maxsize=4096)
def settings(window: Path) -> dict:
    """Servers, power-model exponent r, carbon zone, and scheduler the window ran with."""
    cluster = topology(window)["clusters"][0]
    hosts = cluster["hosts"]
    path = cluster["powerSource"]["carbonTracePath"]
    experiment = json.loads((window / "input" / "experiment.json").read_text())
    policies = experiment.get("allocationPolicies", [])  # none: OpenDC's default, Mem
    return {
        "hosts": sum(host["count"] for host in hosts),
        "servers": " + ".join(
            f"{h['count']:,} {'SURF' if h['name'] == 'H01' else h['name']}" for h in hosts
        ),
        # the groups as the control panel's fields kind_1, count_1, ..., kind_3, count_3
        **{
            f"{field}_{i}": value
            for i, host in enumerate((hosts + [{"name": None, "count": 0}] * GROUPS)[:GROUPS], 1)
            for field, value in (("kind", host["name"]), ("count", host["count"]))
        },
        "calibration_factor": hosts[0]["cpuPowerModel"]["calibrationFactor"],
        "carbon_zone": next(zone for zone, trace in CARBON_TRACES.items() if trace == path),
        "scheduler": policies[0]["policyName"] if policies else "Mem",
    }


def output(window: Path, name: str) -> Path:
    return next(window.glob(f"output/*/raw-output/0/seed=0/{name}.parquet"))


def ms(time: pd.Timestamp) -> int:
    return round(time.timestamp() * 1000)


def read(window: Path, name: str, columns: tuple, start: pd.Timestamp | None, end: pd.Timestamp):
    """The rows of one OpenDC output file of the window in (start, end], with UTC timestamps."""
    rows = [("timestamp_absolute", "<=", ms(end))]
    if start is not None:
        rows.append(("timestamp_absolute", ">", ms(start)))
    df = pd.read_parquet(
        output(window, name), columns=["timestamp_absolute", *columns], filters=rows
    )
    df.insert(0, "timestamp", pd.to_datetime(df.pop("timestamp_absolute"), unit="ms", utc=True))
    return df


@lru_cache(maxsize=4096)
def cluster_slice(window: Path, start: pd.Timestamp | None, end: pd.Timestamp) -> pd.DataFrame:
    """Hosts and jobs (service output), CPU, jobs, and embodied carbon of the hosts (host output), and energy and
    CO2 (power source output), between start and end."""
    hosts = read(window, "host", HOST, start, end)
    hosts["cpu_demand_cores"] = hosts["cpu_demand"] / hosts["cpu_capacity"] * hosts["core_count"]
    hosts["in_use"] = hosts["tasks_running"] > 0
    by_time = hosts.groupby("timestamp")
    cpu = by_time["cpu_utilization"]
    hosts = pd.DataFrame(
        {
            "hosts_in_use": by_time["in_use"].sum(),
            "cpu_utilization": cpu.mean(),
            "cpu_utilization_median": cpu.median(),
            "cpu_demand_cores": by_time["cpu_demand_cores"].sum(),
            "cpu_capacity_cores": by_time["core_count"].sum(),
            "embodied_carbon": by_time["embodied_carbon"].sum(),
        }
    ).reset_index()
    power = read(window, "powerSource", ("energy_usage", "carbon_emission"), start, end)
    service = read(window, "service", SERVICE, start, end)
    return service.merge(hosts, on="timestamp").merge(power, on="timestamp")


def cluster(run_dir: Path) -> pd.DataFrame:
    """The cluster over time, each window contributing its own slice."""
    with LOCK:
        return stitch(tuple(slices(run_dir)))


@lru_cache(maxsize=1)  # the panels of one dashboard refresh ask for the same windows
def stitch(slices: tuple) -> pd.DataFrame:
    cluster = pd.concat([cluster_slice(*s) for s in slices], ignore_index=True)
    # per sample, in J and g
    cluster["energy_kwh"] = cluster.pop("energy_usage") / 3.6e6
    cluster["co2_kg"] = cluster.pop("carbon_emission") / 1000
    cluster["embodied_co2_kg"] = cluster.pop("embodied_carbon") / 1000
    return cluster


def totals(run_dir: Path, period: str) -> pd.DataFrame:
    """Energy, CO2, and embodied CO2 per calendar period, the last one up to the twin's time."""
    by_period = cluster(run_dir).resample(
        PERIODS[period], on="timestamp", closed="left", label="left"
    )
    return by_period[["energy_kwh", "co2_kg", "embodied_co2_kg"]].sum().reset_index()


def job_times(window: Path) -> pd.DataFrame:
    """Each job of the window with its submit, start, and finish time (UTC)."""
    columns = {"submission_time": "submit", "schedule_time": "start", "finish_time": "finish"}
    tasks = pd.read_parquet(
        output(window, "task"), columns=["timestamp", "timestamp_absolute", "task_id", *columns]
    )
    # a row per job and sample; the last has its times, which count from the trace start
    tasks = tasks.drop_duplicates("task_id", keep="last")
    t0 = tasks["timestamp_absolute"].iloc[0] - tasks["timestamp"].iloc[0]
    times = {
        new: pd.to_datetime(t0 + tasks[old], unit="ms", utc=True) for old, new in columns.items()
    }
    return pd.DataFrame({"task_id": tasks["task_id"], **times})


@lru_cache(maxsize=4096)
def window_scheduling(window: Path, start: pd.Timestamp | None, end: pd.Timestamp) -> dict:
    jobs = job_times(window)
    started = jobs["start"] <= end if start is None else jobs["start"].between(start, end, "right")
    queue = (jobs["start"] - jobs["submit"])[started].dt.total_seconds() / 60
    return {
        "timestamp": end,
        "completion_h": (jobs["finish"].max() - end).total_seconds() / 3600,
        "queue_median_min": queue.median(),
    }


def scheduling(run_dir: Path) -> pd.DataFrame:
    """Per window: the time until all jobs submitted so far are done, and the time in queue of the jobs that
    started in the window's own slice."""
    with LOCK:
        return pd.DataFrame([window_scheduling(*s) for s in slices(run_dir)])


def jobs(run_dir: Path) -> pd.DataFrame:
    """The jobs not done at the twin's time, as the latest window predicts them, the longest time left first."""
    window = windows(run_dir)[-1]
    now = end_time(window)
    jobs = job_times(window)
    left = jobs[jobs["finish"] > now]
    left["state"] = (left["start"] <= now).map({True: "running", False: "waiting"})
    left["time_left_h"] = (left["finish"] - now).dt.total_seconds() / 3600
    return left.sort_values("time_left_h", ascending=False)


def shown(value) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def events(run_dir: Path) -> pd.DataFrame:
    """Topology changes, at the end of the last window before them: from there on, the twin runs the new one."""
    rows = []
    for before, after in pairwise(windows(run_dir)):
        old, new = settings(before), settings(after)
        changes = [
            f"{name} {shown(old[key])} to {shown(new[key])}"
            for key, name in SETTINGS.items()
            if old[key] != new[key]
        ]
        if changes:
            rows.append({"time": end_time(before), "text": "; ".join(changes)})
    return pd.DataFrame(rows, columns=["time", "text"])


def accuracy(run_dir: Path, power: pd.DataFrame) -> pd.DataFrame:
    """Per hour: the MAPE [%] of OpenDT's power vs. the measured power, and the r the twin ran with by then."""
    error = (power["simulated_power"] - power["actual_power"]).abs() / power["actual_power"] * 100
    hourly = error.groupby(power["timestamp"].dt.floor("h")).mean().rename("mape").to_frame()
    r = pd.Series({end_time(w): settings(w)["calibration_factor"] for w in windows(run_dir)})
    hourly["r"] = r.resample("h").last().reindex(hourly.index).ffill()
    return hourly.reset_index(names="timestamp")


def status(run_dir: Path) -> dict:
    """The twin's current time and topology, from the latest complete window."""
    window = windows(run_dir)[-1]
    return {
        "twin_time": end_time(window),
        "window": int(window.name.split("_")[1]),
        **settings(window),
    }
