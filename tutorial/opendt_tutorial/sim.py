"""Run OpenDT's simulator (the bundled OpenDC) on the SURF trace and read the results.

This mirrors what OpenDT's simulator service does for one window of operation
(`libs/common/odt_common/odc_runner/runner.py`): write the jobs received so far as
OpenDC input, simulate, and read OpenDC's parquet output. Because OpenDC is a
deterministic, causal simulator, one run from the start of the trace up to `until`
gives exactly the predictions the live twin stitches together window by window.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from odt_common.models import Topology
from odt_common.odc_runner import OpenDCRunner
from odt_common.odc_runner.java_home import detect_java_home

from .data import TRACE_END, TRACE_START, _utc, load_surf
from .paths import PATHS
from .topology import make_topology

log = logging.getLogger(__name__)

EXPORT_INTERVAL_S = 150  # OpenDC samples every 150 s, as in OpenDT's simulator
TIMEOUT_S = 300
DEFAULT_JAVA_OPTS = "-Xmx2g"
CACHE_VERSION = 1
_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")

# OpenDC needs non-nullable columns (same schema as OpenDCRunner._create_tasks/_fragments_parquet).
TASK_SCHEMA = pa.schema(
    [
        ("id", pa.int32(), False),
        ("submission_time", pa.int64(), False),
        ("duration", pa.int64(), False),
        ("cpu_count", pa.int32(), False),
        ("cpu_capacity", pa.float64(), False),
        ("mem_capacity", pa.int64(), False),
    ]
)
FRAGMENT_SCHEMA = pa.schema(
    [
        ("id", pa.int32(), False),
        ("duration", pa.int64(), False),
        ("cpu_count", pa.int32(), False),
        ("cpu_usage", pa.float64(), False),
    ]
)
POWER_COLUMNS = ["power_draw", "energy_usage", "carbon_intensity", "carbon_emission"]
SERVICE_COLUMNS = [
    "hosts_up",
    "hosts_down",
    "tasks_total",
    "tasks_pending",
    "tasks_active",
    "tasks_completed",
    "tasks_terminated",
]
HOST_COLUMNS = ["host_name", "cpu_utilization", "cpu_usage", "power_draw", "tasks_running"]


@dataclass(repr=False)
class SimResult:
    """One OpenDC run. Frames are indexed by UTC timestamp and end at `until`."""

    label: str
    params: dict
    until: pd.Timestamp
    power: pd.DataFrame  # power_draw [W], energy_usage [J per sample], carbon_intensity [g/kWh], carbon_emission [g per sample]
    service: pd.DataFrame  # hosts_up, tasks_pending, tasks_active, tasks_completed, ...
    tasks: pd.DataFrame | None  # one row per job: submission_time, schedule_time, finish_time (UTC), wait_s
    hosts: pd.DataFrame | None  # per-host samples (only if exported)
    forecast: pd.DataFrame  # power after `until` too: what the twin predicts if no new jobs arrive
    run_dir: Path
    wall_seconds: float
    cached: bool

    def summary(self, start=None, end=None) -> dict:
        """Key numbers between `start` (default: trace start) and `end` (default: `until`)."""
        start, end = _utc(start) or TRACE_START, _utc(end) or self.until
        p, s = self.power.loc[start:end], self.service.loc[start:end]
        out = {
            "avg_power_kw": float(p["power_draw"].mean() / 1000),
            "energy_kwh": _energy_kwh(p),
            "co2_kg": _co2_kg(p),
            "max_pending": int(s["tasks_pending"].max()) if len(s) else 0,
        }
        if self.tasks is not None:
            t = self.tasks[(self.tasks["submission_time"] >= start) & (self.tasks["submission_time"] <= end)]
            out["mean_wait_min"] = float(t["wait_s"].mean() / 60) if len(t) else 0.0
            out["jobs_waited"] = int((t["wait_s"] > 0).sum())
        return out

    def __repr__(self) -> str:
        return (
            f"SimResult({self.label!r}, until={self.until:%Y-%m-%d %H:%M}, "
            f"{len(self.power)} samples, cached={self.cached})"
        )


def _energy_kwh(power: pd.DataFrame) -> float:
    return float(power["energy_usage"].sum() / 3.6e6)  # J -> kWh


def _co2_kg(power: pd.DataFrame) -> float:
    return float(power["carbon_emission"].sum() / 1000)  # g -> kg


def _resolve_until(until) -> pd.Timestamp:
    t = _utc(until)
    if t <= TRACE_START:
        raise ValueError(f"until must be after the trace start ({TRACE_START:%Y-%m-%d %H:%M} UTC), got {t}.")
    if t > TRACE_END:
        log.warning("until=%s is past the end of the trace; using %s instead.", t, TRACE_END)
        t = TRACE_END
    return t


def write_inputs(until, out_dir: Path) -> int:
    """Write OpenDC's tasks.parquet and fragments.parquet for all jobs submitted before `until`.

    Jobs are ordered by submission time and fragments by job, as the live twin's runner does.
    Returns the number of jobs written.
    """
    until = _resolve_until(until)
    surf = load_surf()
    tasks = surf.tasks[surf.tasks["submission_time"] < until].sort_values("submission_time", kind="stable")
    position = pd.Series(np.arange(len(tasks)), index=tasks["id"].to_numpy())
    frags = surf.fragments[surf.fragments["id"].isin(position.index)]
    frags = frags.iloc[np.argsort(frags["id"].map(position).to_numpy(), kind="stable")]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pydict(
            {
                "id": tasks["id"].to_numpy("int32"),
                "submission_time": ((tasks["submission_time"] - _EPOCH) // pd.Timedelta("1ms")).to_numpy("int64"),
                "duration": tasks["duration"].to_numpy("int64"),
                "cpu_count": tasks["cpu_count"].to_numpy("int32"),
                "cpu_capacity": tasks["cpu_capacity"].to_numpy("float64"),
                "mem_capacity": tasks["mem_capacity"].to_numpy("int64"),
            },
            schema=TASK_SCHEMA,
        ),
        out_dir / "tasks.parquet",
    )
    pq.write_table(
        pa.Table.from_pydict(
            {
                "id": frags["id"].to_numpy("int32"),
                "duration": frags["duration"].to_numpy("int64"),
                "cpu_count": frags["cpu_count"].to_numpy("int32"),
                "cpu_usage": frags["cpu_usage"].to_numpy("float64"),
            },
            schema=FRAGMENT_SCHEMA,
        ),
        out_dir / "fragments.parquet",
    )
    return len(tasks)


def simulate(
    until="2022-10-07 22:00",
    *,
    hosts: int = 277,
    r: float = 4.0,
    idle_power: float = 25.0,
    max_power: float = 174.0,
    carbon: str | Path | None = None,
    export: tuple[str, ...] = ("powerSource", "service", "task"),
    label: str | None = None,
    force: bool = False,
) -> SimResult:
    """Simulate SURF from the start of the trace until `until` with the given datacenter.

    Results are cached in tutorial/output/: running the same simulation twice is instant.
    """
    until = _resolve_until(until)
    topology = make_topology(hosts=hosts, r=r, idle_power=idle_power, max_power=max_power, carbon=carbon)
    export = tuple(dict.fromkeys(("powerSource", "service", *export)))
    params = {"hosts": hosts, "r": r, "idle_power": idle_power, "max_power": max_power, "carbon": str(carbon) if carbon else None}
    label = label or f"hosts={hosts}, r={r:g}, carbon={carbon or 'OpenDT'}"
    run_dir = PATHS.output / _cache_key(until, topology, export)

    cached = not force and _is_complete(run_dir, export)
    if cached:
        wall = json.loads((run_dir / "params.json").read_text())["wall_seconds"]
    else:
        shutil.rmtree(run_dir, ignore_errors=True)
        input_dir = run_dir / "input"
        write_inputs(until, input_dir / "workload")
        _runner()._create_topology_json(topology, input_dir / "topology.json")
        _write_experiment(input_dir, run_dir / "output", export)
        wall = _run_opendc(input_dir / "experiment.json", run_dir / "opendc.log")
        if not _outputs_readable(run_dir, export):
            raise RuntimeError(f"OpenDC finished but its output is incomplete; see {run_dir / 'opendc.log'}.")
        (run_dir / "params.json").write_text(
            json.dumps({"params": params, "until": until.isoformat(), "export": export, "wall_seconds": wall}, indent=2)
        )
        (run_dir / "DONE").write_text("")
    return _load_result(run_dir, label, params, until, export, wall, cached)


@lru_cache(maxsize=1)
def _runner() -> OpenDCRunner:
    return OpenDCRunner(PATHS.opendc_bin)


def _cache_key(until: pd.Timestamp, topology: Topology, export: tuple[str, ...]) -> str:
    spec = {
        "v": CACHE_VERSION,
        "until": until.isoformat(),
        "topology": topology.model_dump(mode="json"),
        "export": sorted(export),
        "interval": EXPORT_INTERVAL_S,
    }
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def _write_experiment(input_dir: Path, output_dir: Path, export: tuple[str, ...]) -> None:
    # Same structure as OpenDCRunner._create_experiment_json, with a configurable export list.
    experiment = {
        "name": "run",
        "topologies": [{"pathToFile": str(input_dir / "topology.json")}],
        "workloads": [{"pathToFile": str(input_dir / "workload"), "type": "ComputeWorkload"}],
        "outputFolder": str(output_dir),
        "exportModels": [{"exportInterval": EXPORT_INTERVAL_S, "filesToExport": list(export)}],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "experiment.json").write_text(json.dumps(experiment, indent=2))


def _java_opts() -> str:
    return DEFAULT_JAVA_OPTS


def _run_opendc(experiment_file: Path, log_file: Path) -> float:
    """Run the OpenDC binary (same command as OpenDCRunner._execute_opendc); return wall-clock seconds.

    OpenDC runs in its own process group so that interrupting the notebook kernel also stops Java.
    """
    env = os.environ.copy()
    env["JAVA_HOME"] = detect_java_home()
    env["OPEN_DC_EXPERIMENT_RUNNER_OPTS"] = _java_opts()
    cmd = [str(PATHS.opendc_bin), "--experiment-path", str(experiment_file)]
    started = time.monotonic()
    with open(log_file, "w") as out:
        proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        try:
            code = proc.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired as e:
            _kill(proc)
            raise RuntimeError(f"OpenDC took longer than {TIMEOUT_S} s; see {log_file}.") from e
        except BaseException:  # e.g. KeyboardInterrupt from "interrupt kernel"
            _kill(proc)
            raise
    if code != 0:
        tail = "\n".join(log_file.read_text(errors="replace").splitlines()[-20:])
        raise RuntimeError(f"OpenDC failed (exit code {code}). Last lines of {log_file}:\n{tail}")
    return time.monotonic() - started


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _output_file(run_dir: Path, name: str) -> Path | None:
    return next((run_dir / "output").glob(f"**/{name}.parquet"), None)


def _outputs_readable(run_dir: Path, export: tuple[str, ...]) -> bool:
    for name in export:
        path = _output_file(run_dir, name)
        try:
            pq.read_metadata(path)
        except Exception:
            return False
    return True


def _is_complete(run_dir: Path, export: tuple[str, ...]) -> bool:
    return (run_dir / "DONE").exists() and (run_dir / "params.json").exists() and _outputs_readable(run_dir, export)


def _read(run_dir: Path, name: str, columns: list[str]) -> pd.DataFrame:
    """Read an OpenDC output file; index = absolute UTC time, `sim_ms` = OpenDC's relative time."""
    df = pq.read_table(_output_file(run_dir, name), columns=["timestamp", "timestamp_absolute", *columns]).to_pandas()
    df = df.rename(columns={"timestamp": "sim_ms"})
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("timestamp_absolute"), unit="ms", utc=True), name="timestamp")
    return df


def _load_result(run_dir, label, params, until, export, wall, cached) -> SimResult:
    forecast = _read(run_dir, "powerSource", POWER_COLUMNS).drop(columns="sim_ms")
    service = _read(run_dir, "service", SERVICE_COLUMNS).drop(columns="sim_ms")

    tasks = None
    if "task" in export:
        raw = _read(run_dir, "task", ["task_id", "submission_time", "schedule_time", "finish_time", "task_state"])
        offset_ms = int(((raw.index - _EPOCH) // pd.Timedelta("1ms"))[0] - raw["sim_ms"].iloc[0])
        last = raw.sort_values("sim_ms").groupby("task_id").last()
        for col in ("submission_time", "schedule_time", "finish_time"):
            last[col] = pd.to_datetime(last[col] + offset_ms, unit="ms", utc=True)
        last["wait_s"] = (last["schedule_time"] - last["submission_time"]).dt.total_seconds()
        tasks = last[["submission_time", "schedule_time", "finish_time", "task_state", "wait_s"]]

    hosts = None
    if "host" in export:
        hosts = _read(run_dir, "host", HOST_COLUMNS).drop(columns="sim_ms").loc[:until]

    return SimResult(
        label=label,
        params=params,
        until=until,
        power=forecast.loc[:until],
        service=service.loc[:until],
        tasks=tasks,
        hosts=hosts,
        forecast=forecast,
        run_dir=run_dir,
        wall_seconds=wall,
        cached=cached,
    )
