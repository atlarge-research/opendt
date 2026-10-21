"""Power data query and alignment module for dashboard API."""

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


class PowerDataQuery:
    """Query and align power data from simulation and actual consumption."""

    def __init__(self, run: Path, workload_context: WorkloadContext):
        """The power of a run (its folder) and of its workload."""
        self.run_id = run.name
        self.workload_context = workload_context

        # Path to aggregated simulation results
        self.sim_results_path = run / "simulator" / "agg_results.parquet"

        # Path to actual consumption data
        self.consumption_path = workload_context.consumption_file

        # Path to tasks data (needed for earliest task time)
        self.tasks_path = workload_context.tasks_file

    def query(
        self, interval_seconds: int = 60, start_time: datetime | None = None
    ) -> PowerDataResponse:
        """Query and align power data at specified interval."""
        # Load simulated power data
        if not self.sim_results_path.exists():
            raise FileNotFoundError(f"Simulation results not found: {self.sim_results_path}")

        sim_df = pd.read_parquet(self.sim_results_path)

        # Load actual consumption data
        if not self.consumption_path.exists():
            raise FileNotFoundError(f"Consumption data not found: {self.consumption_path}")

        actual_df = pd.read_parquet(self.consumption_path)

        # Prepare simulated data
        sim_df = self._prepare_simulated_data(sim_df)

        # Prepare actual data
        actual_df = self._prepare_actual_data(actual_df)

        # Filter by start time if provided
        if start_time:
            sim_df = sim_df.loc[sim_df["timestamp"] >= start_time].copy()
            actual_df = actual_df.loc[actual_df["timestamp"] >= start_time].copy()

        # Align timeseries at specified interval
        aligned_df = self._align_timeseries(sim_df, actual_df, interval_seconds)

        # Convert to response model
        data_points = []
        for _, row in aligned_df.iterrows():
            timestamp = row["timestamp"]
            if isinstance(timestamp, pd.Timestamp):
                timestamp_dt = timestamp.to_pydatetime()
            else:
                timestamp_dt = pd.to_datetime(timestamp).to_pydatetime()  # type: ignore[union-attr]

            data_points.append(
                PowerDataPoint(
                    timestamp=timestamp_dt,
                    simulated_power=float(row["simulated_power"]),
                    actual_power=float(row["actual_power"]),
                )
            )

        metadata = {
            "run_id": self.run_id,
            "workload": self.workload_context.name,
            "interval_seconds": interval_seconds,
            "count": len(data_points),
            "start_time": aligned_df["timestamp"].min().isoformat()
            if not aligned_df.empty
            else None,
            "end_time": aligned_df["timestamp"].max().isoformat() if not aligned_df.empty else None,
        }

        return PowerDataResponse(data=data_points, metadata=metadata)

    def _prepare_simulated_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare simulated data for alignment."""
        if "timestamp" not in df.columns:
            raise ValueError("Simulation data missing 'timestamp' column")

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        # Use power_draw column
        if "power_draw" not in df.columns:
            raise ValueError("Simulation data missing 'power_draw' column")

        # Select and rename relevant columns
        result = df[["timestamp", "power_draw"]].copy()
        # Use type: ignore for pandas rename signature mismatch
        result = result.rename(columns={"power_draw": "simulated_power"})  # type: ignore[call-overload]

        # Sort by timestamp
        result = result.sort_values("timestamp", ignore_index=True)

        return result

    def _prepare_actual_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare actual consumption data for alignment."""
        # Get earliest task time from tasks.parquet
        if not self.tasks_path.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_path}")

        tasks_df = pd.read_parquet(self.tasks_path)
        if tasks_df.empty or "submission_time" not in tasks_df.columns:
            raise ValueError("Tasks data missing or invalid")

        # Get earliest task submission time and convert to milliseconds
        earliest_task_time = pd.to_datetime(tasks_df["submission_time"].min())
        earliest_task_time_ms = int(earliest_task_time.timestamp() * 1000)

        # Get consumption offset from workload context
        offset_ms = self.workload_context.consumption_offset_ms

        # Convert relative timestamps to absolute timestamps
        # Formula: absolute_time_ms = earliest_task_time_ms + relative_ms + offset_ms
        if "timestamp" not in df.columns:
            raise ValueError("Consumption data missing 'timestamp' column")

        df["timestamp"] = earliest_task_time_ms + df["timestamp"] + offset_ms

        # Convert from milliseconds to datetime (UTC-aware)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

        # Use power_draw column
        if "power_draw" not in df.columns:
            raise ValueError("Consumption data missing 'power_draw' column")

        # Select and rename relevant columns
        result = df[["timestamp", "power_draw"]].copy()
        # Use type: ignore for pandas rename signature mismatch
        result = result.rename(columns={"power_draw": "actual_power"})  # type: ignore[call-overload]

        # Sort by timestamp
        result = result.sort_values("timestamp", ignore_index=True)

        return result

    def _align_timeseries(
        self, sim_df: pd.DataFrame, actual_df: pd.DataFrame, interval_seconds: int
    ) -> pd.DataFrame:
        """Align two timeseries to the same interval."""
        # Create common time range (limited by shortest series)
        start_time = max(sim_df["timestamp"].min(), actual_df["timestamp"].min())
        end_time = min(sim_df["timestamp"].max(), actual_df["timestamp"].max())

        # Generate regular time grid at specified interval
        time_grid = pd.date_range(start=start_time, end=end_time, freq=f"{interval_seconds}s")

        # Interpolate simulated data to time grid
        sim_df = sim_df.set_index("timestamp")
        sim_interpolated = sim_df.reindex(sim_df.index.union(time_grid)).interpolate(method="time")
        sim_interpolated = sim_interpolated.reindex(time_grid)

        # Interpolate actual data to time grid
        actual_df = actual_df.set_index("timestamp")
        actual_interpolated = actual_df.reindex(actual_df.index.union(time_grid)).interpolate(
            method="time"
        )
        actual_interpolated = actual_interpolated.reindex(time_grid)

        # Combine into single dataframe
        aligned = pd.DataFrame(
            {
                "timestamp": time_grid,
                "simulated_power": sim_interpolated["simulated_power"].values,
                "actual_power": actual_interpolated["actual_power"].values,
            }
        )

        # Remove rows with NaN values (shouldn't happen with interpolation, but just in case)
        aligned = aligned.dropna()

        return aligned
