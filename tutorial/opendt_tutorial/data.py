"""The SURF trace (jobs, their CPU use, measured power) and carbon-intensity traces."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from odt_common.config import WorkloadMetadata

from .paths import PATHS

# The SURF trace covers exactly one week (first job submitted 2022-10-06 22:00 UTC).
TRACE_START = pd.Timestamp("2022-10-06 22:00", tz="UTC")
TRACE_END = TRACE_START + pd.Timedelta(days=7)

# Electricity Maps zones shipped in tutorial/carbon_traces/ (October 2022).
CARBON_ZONES = ("SE", "NO", "FR", "NL", "DE", "PL")


@dataclass(frozen=True)
class Surf:
    tasks: pd.DataFrame  # one row per job: id, submission_time (UTC), duration [ms], cpu_count, ...
    fragments: pd.DataFrame  # 30-s CPU-usage samples per job: id (= job id), duration, cpu_count, cpu_usage [MHz]
    measured: pd.Series  # measured cluster power [W], indexed by UTC timestamp (30-s samples)


@lru_cache(maxsize=1)
def load_surf() -> Surf:
    """Load the SURF workload and the measured power of the real cluster."""
    tasks = pd.read_parquet(PATHS.workload / "tasks.parquet")
    tasks["id"] = tasks["id"].astype("int64")
    tasks["submission_time"] = pd.to_datetime(tasks["submission_time"]).dt.tz_localize("UTC")

    fragments = pd.read_parquet(PATHS.workload / "fragments.parquet")
    fragments["id"] = fragments["id"].astype("int64")

    # Consumption timestamps are milliseconds since the first job, plus a per-workload offset
    # (same rule as OpenDT's API, services/api/api/power_query.py).
    offset_ms = WorkloadMetadata.load(PATHS.workload / "workload.yaml").consumption_offset_ms
    consumption = pd.read_parquet(PATHS.workload / "consumption.parquet", columns=["timestamp", "power_draw"])
    start = tasks["submission_time"].min()
    index = start + pd.to_timedelta(consumption["timestamp"] + offset_ms, unit="ms")
    measured = pd.Series(consumption["power_draw"].to_numpy(), index=pd.DatetimeIndex(index, name="timestamp"),
                         name="power_draw").sort_index()

    return Surf(tasks=tasks, fragments=fragments, measured=measured)


def measured_power(start=None, end=None) -> pd.Series:
    """Measured power of the real SURF cluster [W] between `start` and `end` (inclusive)."""
    return load_surf().measured.loc[_utc(start) : _utc(end)]


def carbon_trace_path(zone: str) -> Path:
    """Path of the carbon-intensity trace for an Electricity Maps zone."""
    if zone not in CARBON_ZONES:
        raise ValueError(f"Unknown zone {zone!r}. Available zones: {', '.join(CARBON_ZONES)}")
    return PATHS.carbon / f"{zone}.parquet"


@lru_cache(maxsize=len(CARBON_ZONES))
def carbon_intensity(zone: str) -> pd.Series:
    """Carbon intensity of the electricity grid in `zone` [gCO₂/kWh], indexed by UTC timestamp."""
    df = pd.read_parquet(carbon_trace_path(zone))
    index = pd.DatetimeIndex(pd.to_datetime(df["timestamp"]).dt.tz_localize("UTC"), name="timestamp")
    return pd.Series(df["carbon_intensity"].to_numpy(), index=index, name="carbon_intensity")


def _utc(t) -> pd.Timestamp | None:
    if t is None:
        return None
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
