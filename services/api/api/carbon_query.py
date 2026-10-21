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


class CarbonDataQuery:
    """Query carbon emission data from simulation results."""

    def __init__(self, run: Path):
        """The CO2 emissions of a run (its folder)."""
        self.run_id = run.name
        self.sim_results_path = run / "simulator" / "agg_results.parquet"

    def query(
        self, interval_seconds: int = 60, start_time: datetime | None = None
    ) -> CarbonDataResponse:
        """Query carbon emission data at specified interval."""
        # Load simulated data
        if not self.sim_results_path.exists():
            raise FileNotFoundError(f"Simulation results not found: {self.sim_results_path}")

        df = pd.read_parquet(self.sim_results_path)

        # Validate required columns
        required_cols = ["timestamp", "power_draw", "carbon_intensity"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        # Calculate carbon emission: power_draw (W) * carbon_intensity (gCO2/kWh) / 1000
        # This gives gCO2/h (grams of CO2 per hour at current power draw)
        df["carbon_emission"] = df["power_draw"] * df["carbon_intensity"] / 1000

        # Sort by timestamp
        df = df.sort_values("timestamp", ignore_index=True)

        # Filter by start time if provided
        if start_time:
            df = df.loc[df["timestamp"] >= start_time].copy()

        # Resample to specified interval
        df = self._resample_data(df, interval_seconds)

        # Convert to response model
        data_points = []
        for _, row in df.iterrows():
            timestamp = row["timestamp"]
            if isinstance(timestamp, pd.Timestamp):
                timestamp_dt = timestamp.to_pydatetime()
            else:
                timestamp_dt = pd.to_datetime(timestamp).to_pydatetime()  # type: ignore[union-attr]

            data_points.append(
                CarbonDataPoint(
                    timestamp=timestamp_dt,
                    carbon_intensity=float(row["carbon_intensity"]),
                    power_draw=float(row["power_draw"]),
                    carbon_emission=float(row["carbon_emission"]),
                )
            )

        metadata = {
            "run_id": self.run_id,
            "interval_seconds": interval_seconds,
            "count": len(data_points),
            "start_time": df["timestamp"].min().isoformat() if not df.empty else None,
            "end_time": df["timestamp"].max().isoformat() if not df.empty else None,
        }

        return CarbonDataResponse(data=data_points, metadata=metadata)

    def _resample_data(self, df: pd.DataFrame, interval_seconds: int) -> pd.DataFrame:
        """Resample data to specified interval."""
        # Set timestamp as index
        df = df.set_index("timestamp")

        # Resample and take mean of numeric columns
        resampled = (
            df[["power_draw", "carbon_intensity", "carbon_emission"]]
            .resample(f"{interval_seconds}s")
            .mean()
        )

        # Remove NaN rows and reset index
        resampled = resampled.dropna().reset_index()

        return resampled
