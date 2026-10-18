"""What the live twin has computed so far, read from its windows of operation.

Every window (simulator/opendc/run_<N>/) re-simulates the trace from the start with the topology of that moment;
metadata.json is written last, so a window without it is still running.
"""

import json
import threading
from functools import cache, lru_cache
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

SERVICE = ("hosts_up", "tasks_pending", "tasks_active", "tasks_completed")
HOST = (
    "core_count",
    "cpu_capacity",
    "cpu_demand",
    "cpu_utilization",
    "tasks_running",
    "power_draw",
    "embodied_carbon",
)
# The CO2 zones: Electricity Maps carbon intensity traces inside the containers; SURF's twin starts on NL
CARBON_TRACES = {
    zone: f"/app/workload/carbon_zones/{zone}.parquet" for zone in ("NL", "PL", "DE", "RO")
}
SETTINGS = {
    "servers": "Hosts",
    "calibration_factor": "r",
    "carbon_zone": "CO₂ zone",
    "scheduler": "Scheduler",
}
PERIODS = {"minute": "min", "hour": "h", "day": "D", "week": "W-MON", "month": "MS", "year": "YS"}
LOCK = threading.Lock()  # the panels of a dashboard ask at once; a new window is computed once
GROUPS = 3  # kinds of servers the control panel can mix
# hosts per CPU utilization bucket [%]
LOWS = range(0, 100, 20)
BUCKETS = [f"cpu_{low}_{low + 20}" for low in LOWS]


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


@cache  # a complete window never changes
def end_time(window: Path) -> pd.Timestamp:
    return pd.Timestamp(json.loads((window / "metadata.json").read_text())["simulated_time"])


def slices(run_dir: Path):
    """Each complete window with its own slice of time, (start, end]: from the previous window's end to its own."""
    start = pd.Timestamp(0, tz="UTC")
    for window in windows(run_dir):
        end = end_time(window)
        yield window, start, end
        start = end


def topology(window: Path) -> dict:
    """The topology the window used, as OpenDC read it."""
    return json.loads((window / "input" / "topology.json").read_text())


def groups(hosts: list[dict]) -> list[dict]:
    """The host groups, as many as the control panel has, the missing ones empty."""
    return (hosts + [{"name": None, "count": 0}] * GROUPS)[:GROUPS]


@cache
def settings(window: Path) -> dict:
    """Servers, power-model exponent r, carbon zone, and scheduler the window ran with."""
    cluster = topology(window)["clusters"][0]
    hosts = cluster["hosts"]
    path = cluster["powerSource"]["carbonTracePath"]
    experiment = json.loads((window / "input" / "experiment.json").read_text())
    policies = experiment.get("allocationPolicies", [])  # none: OpenDC's default, Mem
    return {
        "servers": " + ".join(f"{host['count']:,} {label(host)}" for host in hosts),
        # the groups as the control panel's fields kind_1, count_1, ..., kind_3, count_3
        **{f"kind_{i}": host["name"] for i, host in enumerate(groups(hosts), 1)},
        **{f"count_{i}": host["count"] for i, host in enumerate(groups(hosts), 1)},
        "calibration_factor": hosts[0]["cpuPowerModel"]["calibrationFactor"],
        # another trace (e.g., of an older run) by its file name
        "carbon_zone": next(
            (zone for zone, trace in CARBON_TRACES.items() if trace == path), Path(path).stem
        ),
        "scheduler": policies[0]["policyName"] if policies else "Mem",
    }


def label(host: dict) -> str:
    # SURF is the datacenter, SURF-SARA its cluster
    return "SURF-SARA" if host["name"] == "H01" else host["name"]


def specs(host: dict) -> dict:
    """A kind of server as people read it: cores, GHz, GB, and idle and maximum power [W]."""
    return {
        "kind": label(host),
        "cores": host["cpu"]["coreCount"],
        "ghz": host["cpu"]["coreSpeed"] / 1000,
        "memory_gb": host["memory"]["memorySize"] / 1e6,  # SURF's unit: 128 GB is 128,000,000
        "idle_w": host["cpuPowerModel"]["idlePower"],
        "max_w": host["cpuPowerModel"]["maxPower"],
    }


def server_groups(run_dir: Path) -> pd.DataFrame:
    """The server groups the twin runs now, with their specs."""
    hosts = topology(windows(run_dir)[-1])["clusters"][0]["hosts"]
    return pd.DataFrame({**specs(host), "count": host["count"]} for host in hosts)


def output(window: Path, name: str) -> Path:
    return next(window.glob(f"output/*/raw-output/0/seed=0/{name}.parquet"))


def ms(time: pd.Timestamp) -> int:
    return round(time.timestamp() * 1000)


def read(window: Path, name: str, columns: tuple, start: pd.Timestamp, end: pd.Timestamp):
    """The rows of one OpenDC output file of the window in (start, end], with UTC timestamps."""
    rows = [("timestamp_absolute", ">", ms(start)), ("timestamp_absolute", "<=", ms(end))]
    df = pd.read_parquet(
        output(window, name), columns=["timestamp_absolute", *columns], filters=rows
    )
    df.insert(0, "timestamp", pd.to_datetime(df.pop("timestamp_absolute"), unit="ms", utc=True))
    return df


@cache
def cluster_slice(window: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Hosts and jobs (service output), CPU, jobs, idle power, and embodied carbon of the hosts (host output), and
    energy and CO2 (power source output), between start and end."""
    hosts = read(window, "host", HOST, start, end)
    hosts["cpu_demand_cores"] = hosts["cpu_demand"] / hosts["cpu_capacity"] * hosts["core_count"]
    hosts["in_use"] = hosts["tasks_running"] > 0
    hosts["idle_power_kw"] = hosts["power_draw"].where(~hosts["in_use"], 0) / 1000
    edges = [low / 100 for low in LOWS] + [np.inf]
    hosts["bucket"] = pd.cut(hosts["cpu_utilization"], edges, right=False, labels=BUCKETS)
    by_time = hosts.groupby("timestamp")
    cpu = by_time["cpu_utilization"]
    busy = hosts[hosts["in_use"]].groupby("timestamp")["cpu_utilization"]
    per_time = pd.DataFrame(
        {
            "hosts_in_use": by_time["in_use"].sum(),
            "idle_power_kw": by_time["idle_power_kw"].sum(),  # of the hosts running no job
            "cpu_utilization": cpu.mean(),
            # most hosts are idle: over all of them, the median is 0
            "cpu_utilization_busy_median": busy.median(),
            "cpu_demand_cores": by_time["cpu_demand_cores"].sum(),
            "cpu_capacity_cores": by_time["core_count"].sum(),
            "embodied_carbon": by_time["embodied_carbon"].sum(),
        }
    ).join(hosts.groupby(["timestamp", "bucket"], observed=False).size().unstack())
    power = read(window, "powerSource", ("energy_usage", "carbon_emission"), start, end)
    service = read(window, "service", SERVICE, start, end)
    return service.merge(per_time.reset_index(), on="timestamp").merge(power, on="timestamp")


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


@lru_cache(maxsize=2)  # the latest window, asked for by several panels
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


@cache
def window_scheduling(window: Path, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    jobs = job_times(window)
    started = jobs["start"].between(start, end, "right")
    waited = (jobs["start"] - jobs["submit"]).dt.total_seconds() / 60
    return {
        "timestamp": end,
        "completion_h": (jobs["finish"].max() - end).total_seconds() / 3600,
        "queue_median_min": waited[started].median(),
        # of all the jobs started by the end of the window
        "started_in_10_min_pct": (waited[jobs["start"] <= end] <= 10).mean() * 100,
    }


def scheduling(run_dir: Path) -> pd.DataFrame:
    """Per window: the time until all jobs submitted so far are done, and the time in queue of the jobs that
    started in the window's own slice."""
    with LOCK:
        return pd.DataFrame([window_scheduling(*s) for s in slices(run_dir)])


def arrivals(run_dir: Path) -> pd.DataFrame:
    """Jobs submitted per hour so far, from the trace."""
    submitted = job_times(windows(run_dir)[-1]).resample("h", on="submit").size()
    return submitted.rename_axis("timestamp").rename("jobs").reset_index()


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
    """Topology changes, at the end of the last window before them (from there on, the twin runs the new one), and
    who made them: r is the calibrator's (automatic), the rest the operator's, from the control panel (manual)."""
    rows = []
    for before, after in pairwise(windows(run_dir)):
        old, new = settings(before), settings(after)
        for key, name in SETTINGS.items():
            if old[key] != new[key]:
                by = "Automatic" if key == "calibration_factor" else "Manual"
                rows.append(
                    {
                        "time": end_time(before),
                        "text": f"{name} {shown(old[key])} to {shown(new[key])}",
                        "by": by,
                    }
                )
    return pd.DataFrame(rows, columns=["time", "text", "by"])


def accuracy(run_dir: Path, power: pd.DataFrame, minutes: int = 60) -> pd.DataFrame:
    """Per period of `minutes`: the MAPE [%] of OpenDT's power vs. the measured power, the mean error [kW] (above 0,
    OpenDT predicts more), the error [%] of the energy so far, and the r the twin ran with by then."""
    period = f"{minutes}min"
    by_period = power["timestamp"].dt.floor(period)
    error = power["simulated_power"] - power["actual_power"]
    per_period = (
        pd.DataFrame({"mape": error.abs() / power["actual_power"] * 100, "error_kw": error / 1000})
        .groupby(by_period)
        .mean()
    )
    # the samples are evenly spaced, so their sums stand for the energy
    so_far = power.groupby(by_period)[["simulated_power", "actual_power"]].sum().cumsum()
    per_period["energy_error_pct"] = (so_far["simulated_power"] / so_far["actual_power"] - 1) * 100
    r = pd.Series({end_time(w): settings(w)["calibration_factor"] for w in windows(run_dir)})
    per_period["r"] = r.resample(period).last().reindex(per_period.index).ffill()
    return per_period.reset_index(names="timestamp")


def status(run_dir: Path) -> dict:
    """The twin's current time and topology, from the latest complete window."""
    window = windows(run_dir)[-1]
    return {"twin_time": end_time(window), **settings(window)}
