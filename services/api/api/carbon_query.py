"""Carbon emission data query module for dashboard API."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field


class CarbonDataPoint(BaseModel):
    """Single carbon emission data point."""

    timestamp: datetime = Field(..., description="Timestamp (ISO 8601 format)")
    carbon_intensity: float = Field(..., description="Carbon intensity in gCO2/kWh")
    power_draw: float = Field(..., description="Power draw in Watts")
    carbon_emission: float = Field(..., description="Carbon emission in gCO2/h")


class CarbonDataResponse(BaseModel):
    """Response model for carbon emission query."""

    data: list[CarbonDataPoint]
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata about the query")


def query(run: Path, interval_seconds: int, start_time: datetime | None) -> CarbonDataResponse:
    """The simulated power, carbon intensity, and CO2 emissions of a run (its agg_results.parquet), as means
    every `interval_seconds`, from `start_time` on."""
    df = pd.read_parquet(
        run / "simulator" / "agg_results.parquet",
        columns=["timestamp", "power_draw", "carbon_intensity"],
    )
    df = df.set_index(pd.to_datetime(df["timestamp"], utc=True))[["power_draw", "carbon_intensity"]]
    # power draw [W] x carbon intensity [gCO2/kWh] / 1000 = gCO2/h
    df["carbon_emission"] = df["power_draw"] * df["carbon_intensity"] / 1000
    df = df.sort_index()
    if start_time:
        df = df[df.index >= start_time]
    df = df.resample(f"{interval_seconds}s").mean().dropna()
    data = [
        CarbonDataPoint(
            timestamp=t.to_pydatetime(), power_draw=p, carbon_intensity=i, carbon_emission=e
        )
        for t, p, i, e in df[["power_draw", "carbon_intensity", "carbon_emission"]].itertuples()
    ]
    metadata = {
        "run_id": run.name,
        "interval_seconds": interval_seconds,
        "count": len(data),
        "start_time": df.index.min().isoformat() if data else None,
        "end_time": df.index.max().isoformat() if data else None,
    }
    return CarbonDataResponse(data=data, metadata=metadata)
