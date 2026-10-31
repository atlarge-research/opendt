"""The simulated and the measured power of a run, on one grid: what the Dashboard plots, and the MAPE compares."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from odt_common import WorkloadContext
from pydantic import BaseModel, Field


class PowerDataPoint(BaseModel):
    """Single power data point with both simulated and actual values."""

    timestamp: datetime = Field(..., description="Timestamp (ISO 8601 format)")
    simulated_power: float = Field(..., description="Simulated power draw in Watts")
    actual_power: float = Field(..., description="Actual power draw in Watts")


class PowerDataResponse(BaseModel):
    """Response model for power data query."""

    data: list[PowerDataPoint]
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata about the query")


def measured_power(workload: WorkloadContext) -> pd.Series:
    """The measured power [W] at absolute times; consumption.parquet counts its timestamps [ms] from the
    workload's first task."""
    start = pd.read_parquet(workload.tasks_file, columns=["submission_time"])[
        "submission_time"
    ].min()
    df = pd.read_parquet(workload.consumption_file, columns=["timestamp", "power_draw"])
    ms = int(start.timestamp() * 1000) + df["timestamp"] + workload.consumption_offset_ms
    return df.set_index(pd.to_datetime(ms, unit="ms", utc=True))["power_draw"].sort_index()


def on_grid(series: pd.Series, grid: pd.DatetimeIndex) -> pd.Series:
    """`series` interpolated in time onto `grid`."""
    return series.reindex(series.index.union(grid)).interpolate(method="time").reindex(grid)


def query(
    run: Path, workload: WorkloadContext, interval_seconds: int, start_time: datetime | None
) -> PowerDataResponse:
    """The simulated power (the run's agg_results.parquet) and the measured power, interpolated every
    `interval_seconds` where both have data, from `start_time` on."""
    df = pd.read_parquet(
        run / "simulator" / "agg_results.parquet", columns=["timestamp", "power_draw"]
    )
    simulated = df.set_index(pd.to_datetime(df["timestamp"], utc=True))["power_draw"].sort_index()
    measured = measured_power(workload)
    if start_time:
        simulated, measured = (
            simulated[simulated.index >= start_time],
            measured[measured.index >= start_time],
        )
    first = max(simulated.index.min(), measured.index.min())
    last = min(simulated.index.max(), measured.index.max())
    grid = pd.date_range(first, last, freq=f"{interval_seconds}s")
    aligned = pd.DataFrame(
        {
            "simulated_power": on_grid(simulated, grid).to_numpy(),
            "actual_power": on_grid(measured, grid).to_numpy(),
        },
        index=grid,
    ).dropna()
    data = [
        PowerDataPoint(timestamp=t.to_pydatetime(), simulated_power=float(s), actual_power=float(a))
        for t, s, a in aligned.itertuples()
    ]
    metadata = {
        "run_id": run.name,
        "workload": workload.workload_dir.name,
        "interval_seconds": interval_seconds,
        "count": len(data),
        "start_time": aligned.index.min().isoformat() if data else None,
        "end_time": aligned.index.max().isoformat() if data else None,
    }
    return PowerDataResponse(data=data, metadata=metadata)
