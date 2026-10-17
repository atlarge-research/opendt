"""Run OpenDT's simulator (the bundled OpenDC) on the SURF trace.

This does what OpenDT's simulator service does for one window of operation
(libs/common/odt_common/odc_runner/runner.py): write the jobs submitted so far as OpenDC
input, run OpenDC, read its output. OpenDC is deterministic and causal, so one run from the
start of the trace up to `until` gives exactly the predictions the live twin stitches
together window by window.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
from odt_common.odc_runner.java_home import detect_java_home

from .data import TRACE_END, TRACE_START, load_surf, to_utc
from .paths import PATHS
from .topology import make_topology

log = logging.getLogger(__name__)

CACHE_VERSION = 1  # bump when the run directory layout changes

# OpenDC needs non-nullable columns; this is the schema OpenDT's OpenDCRunner writes.
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


@dataclass(repr=False)
class SimResult:
    """One OpenDC run up to `until`.

    power    per 150-s sample (UTC index): power_draw [W], energy_usage [J],
             carbon_intensity [gCO2/kWh], carbon_emission [g]
    service  per sample: hosts_up, tasks_pending, tasks_active, tasks_completed, ...
    tasks    per job id: submission_time, schedule_time, finish_time (UTC), wait_s
    """

    label: str
    until: pd.Timestamp
    power: pd.DataFrame
    service: pd.DataFrame
    tasks: pd.DataFrame
    run_dir: Path
    cached: bool

    def summary(self, start=TRACE_START, end=TRACE_END) -> dict:
        """Key numbers between `start` and `end` (at most `until`)."""
        start, end = to_utc(start), min(to_utc(end), self.until)
        power = self.power[start:end]
        jobs = self.tasks[self.tasks["submission_time"].between(start, end)]
        return {
            "avg_power_kw": float(power["power_draw"].mean() / 1000),
            "energy_kwh": float(power["energy_usage"].sum() / 3.6e6),
            "co2_kg": float(power["carbon_emission"].sum() / 1000),
            "jobs_waited": int((jobs["wait_s"] > 0).sum()),
            "mean_wait_min": float(jobs["wait_s"].mean() / 60),
            "waiting_at_end": int(
                (jobs["schedule_time"] > end).sum()
            ),  # submitted, not yet started
        }

    def __repr__(self) -> str:
        return f"SimResult({self.label!r}, until={self.until:%Y-%m-%d %H:%M}, cached={self.cached})"


def write_inputs(until, out_dir: Path) -> int:
    """Write OpenDC's tasks.parquet and fragments.parquet for the jobs submitted before `until`.

    Ordered like the live twin: jobs by submission time, fragments grouped per job.
    Returns the number of jobs.
    """
    until = _clip(until)
    surf = load_surf()
    tasks = surf.tasks[surf.tasks["submission_time"] < until]
    tasks = tasks.sort_values("submission_time", kind="stable")
    fragments = tasks[["id"]].merge(surf.fragments, on="id")  # keeps the job order
    epoch_ms = (tasks["submission_time"] - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1ms")
    tasks = tasks.assign(submission_time=epoch_ms)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks.to_parquet(out_dir / "tasks.parquet", schema=TASK_SCHEMA, index=False)
    fragments.to_parquet(out_dir / "fragments.parquet", schema=FRAGMENT_SCHEMA, index=False)
    return len(tasks)


def simulate(
    until="2022-10-07 22:00",
    *,
    hosts: int = 277,
    r: float = 4.0,
    idle_power: float = 25.0,
    max_power: float = 174.0,
    carbon: str | None = None,
    label: str | None = None,
) -> SimResult:
    """Simulate SURF from the start of the trace until `until` on the given datacenter.

    Results are cached in tutorial/output/, so running the same simulation again is instant.
    """
    until = _clip(until)
    topology = make_topology(
        hosts=hosts, r=r, idle_power=idle_power, max_power=max_power, carbon=carbon
    )
    key = f"{CACHE_VERSION} {until.isoformat()} {topology.model_dump_json()}"
    run_dir = PATHS.output / hashlib.sha256(key.encode()).hexdigest()[:12]

    cached = (run_dir / "DONE").exists()
    if not cached:
        shutil.rmtree(run_dir, ignore_errors=True)
        _run_opendc(run_dir, until, topology)
        (run_dir / "DONE").touch()  # written last: an interrupted run is simply re-run next time
    power, service, tasks = _read_output(run_dir, until)
    label = label or f"hosts={hosts}, r={r:g}, carbon={carbon or 'OpenDT'}"
    return SimResult(label, until, power, service, tasks, run_dir, cached)


def simulate_many(param: str, values, **common) -> dict:
    """Run `simulate` once per value of `param`, several at a time; returns {value: SimResult}."""
    load_surf()  # load the trace once here rather than in every thread
    values = list(values)
    with ThreadPoolExecutor(default_workers()) as pool:
        runs = pool.map(lambda v: simulate(**common, **{param: v}, label=f"{param}={v}"), values)
        return dict(zip(values, runs, strict=True))


def default_workers() -> int:
    """Simulations run at once: $OPENDT_TUTORIAL_WORKERS, else one per CPU core, at most 4."""
    return int(os.environ.get("OPENDT_TUTORIAL_WORKERS", min(4, os.cpu_count() or 1)))


def _clip(until) -> pd.Timestamp:
    until = to_utc(until)
    if until <= TRACE_START:
        raise ValueError(
            f"until must be after the trace start ({TRACE_START:%Y-%m-%d %H:%M} UTC), got {until}."
        )
    if until > TRACE_END:
        log.warning("until=%s is past the end of the trace; using %s.", until, TRACE_END)
        return TRACE_END
    return until


def _run_opendc(run_dir: Path, until: pd.Timestamp, topology) -> None:
    inputs = run_dir / "input"
    write_inputs(until, inputs / "workload")
    (inputs / "topology.json").write_text(topology.model_dump_json(indent=2))
    experiment = {  # the experiment file OpenDCRunner writes, minus host.parquet (unused here)
        "name": "run",
        "topologies": [{"pathToFile": str(inputs / "topology.json")}],
        "workloads": [{"pathToFile": str(inputs / "workload"), "type": "ComputeWorkload"}],
        "outputFolder": str(run_dir / "output"),
        "exportModels": [
            {"exportInterval": 150, "filesToExport": ["powerSource", "service", "task"]}
        ],
    }
    (inputs / "experiment.json").write_text(json.dumps(experiment, indent=2))

    env = {**os.environ, "JAVA_HOME": detect_java_home()}
    with open(run_dir / "opendc.log", "w") as log_file:
        result = subprocess.run(
            [str(PATHS.opendc_bin), "--experiment-path", str(inputs / "experiment.json")],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=600,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"OpenDC failed (exit code {result.returncode}); see {run_dir / 'opendc.log'}"
        )


def _read_output(run_dir: Path, until: pd.Timestamp):
    """OpenDC's power, service and per-job output, with OpenDC's clock turned into UTC times."""

    def read(name, columns=None):
        return pd.read_parquet(
            next((run_dir / "output").glob(f"**/{name}.parquet")), columns=columns
        )

    power = read("powerSource").drop(columns=["source_name", "cluster_name"])
    service = read("service")
    # task.parquet has a row per job per sample; the last one holds the job's final times.
    tasks = read("task", ["task_id", "submission_time", "schedule_time", "finish_time"])
    tasks = tasks.drop_duplicates("task_id", keep="last").set_index("task_id")

    # OpenDC counts milliseconds from its time zero, the submission of the first job.
    origin_ms = power["timestamp_absolute"].iloc[0] - power["timestamp"].iloc[0]

    def utc(ms):
        return pd.to_datetime(ms + origin_ms, unit="ms", utc=True)

    for frame in (power, service):
        frame.index = pd.DatetimeIndex(utc(frame.pop("timestamp")), name="timestamp")
        frame.pop("timestamp_absolute")
    for col in ("submission_time", "schedule_time", "finish_time"):
        tasks[col] = utc(tasks[col])
    tasks["wait_s"] = (tasks["schedule_time"] - tasks["submission_time"]).dt.total_seconds()
    return power[:until], service[:until], tasks
