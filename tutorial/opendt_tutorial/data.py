"""The SURF trace (jobs, their CPU use, measured power) and carbon-intensity traces."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd
from odt_common.config import WorkloadMetadata

from .paths import PATHS

# The SURF trace covers exactly one week, starting with the first job's submission.
TRACE_START = pd.Timestamp("2022-10-06 22:00", tz="UTC")
TRACE_END = TRACE_START + pd.Timedelta(days=7)

# Electricity Maps zones shipped in tutorial/carbon_traces/ (October 2022).
CARBON_ZONES = ("NL", "DE", "RO", "PL")


@dataclass(frozen=True)
class Surf:
    tasks: pd.DataFrame  # one row per job: id, submission_time (UTC), duration [ms], cpu_count, ...
    fragments: pd.DataFrame  # 30-s CPU use per job: id, duration, cpu_count, cpu_usage [MHz]
    measured: pd.Series  # measured power of the real cluster [W], 30-s samples, UTC index


@cache
def load_surf() -> Surf:
    """Load the SURF workload and the measured power of the real cluster."""
    tasks = pd.read_parquet(PATHS.workload / "tasks.parquet")
    tasks["id"] = tasks["id"].astype("int64")
    tasks["submission_time"] = tasks["submission_time"].dt.tz_localize("UTC")
    assert tasks["submission_time"].min() == TRACE_START

    fragments = pd.read_parquet(PATHS.workload / "fragments.parquet")
    fragments["id"] = fragments["id"].astype("int64")

    # Measured power is stamped in ms since the first job, plus the workload's offset (as in OpenDT's API).
    offset_ms = WorkloadMetadata.load(PATHS.workload / "workload.yaml").consumption_offset_ms
    power = pd.read_parquet(
        PATHS.workload / "consumption.parquet", columns=["timestamp", "power_draw"]
    )
    power["timestamp"] = TRACE_START + pd.to_timedelta(power["timestamp"] + offset_ms, unit="ms")
    return Surf(tasks, fragments, power.set_index("timestamp")["power_draw"])


def measured_power(start=TRACE_START, end=TRACE_END) -> pd.Series:
    """Measured power of the real SURF cluster [W] between `start` and `end`."""
    return load_surf().measured[to_utc(start) : to_utc(end)]


def carbon_trace_path(zone: str | None = None) -> Path:
    """Carbon-intensity trace: OpenDT's own (zone=None) or an Electricity Maps zone from CARBON_ZONES."""
    if zone is None:
        return PATHS.workload / "carbon.parquet"
    if zone not in CARBON_ZONES:
        raise ValueError(f"Unknown zone {zone!r}. Available zones: {', '.join(CARBON_ZONES)}")
    return PATHS.carbon / f"{zone}.parquet"


def carbon_intensity(zone: str | None = None) -> pd.Series:
    """Carbon intensity of the grid [gCO₂/kWh] over time (UTC index); see `carbon_trace_path`."""
    trace = pd.read_parquet(carbon_trace_path(zone)).set_index("timestamp")["carbon_intensity"]
    return trace.tz_localize("UTC")


def to_utc(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
