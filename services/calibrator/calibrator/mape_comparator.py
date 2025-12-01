"""MAPE (Mean Absolute Percentage Error) calculator for power consumption comparison.

Compares simulated vs actual power timeseries and calculates error metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MapeComparator:
    """Compares simulated and actual power consumption using MAPE metric."""

    def __init__(self, mape_window_minutes: int):
        """Initialize the MAPE comparator.

        Args:
            mape_window_minutes: Maximum time window for MAPE calculation
        """
        self.mape_window_minutes = mape_window_minutes
        self.mape_window = timedelta(minutes=mape_window_minutes)

        logger.info(f"Initialized MapeComparator with window {mape_window_minutes} minutes")

    def compare(
        self,
        simulated_power: pd.DataFrame,
        actual_power: pd.DataFrame,
        simulation_end_time: datetime,
    ) -> dict[str, Any]:
        """Compare simulated vs actual power and calculate MAPE.

        Args:
            simulated_power: DataFrame with columns [timestamp, power_draw]
            actual_power: DataFrame with columns [timestamp, power_draw]
            simulation_end_time: End time of simulation (determines window end)

        Returns:
            Dictionary with:
                - mape: Mean absolute percentage error (%)
                - window_start: Start of comparison window
                - window_end: End of comparison window
                - num_points: Number of aligned data points
                - mean_simulated: Mean simulated power
                - mean_actual: Mean actual power
        """
        # Determine comparison window (rolling, capped at mape_window)
        window_end = simulation_end_time

        # Find earliest available timestamp from both series
        if simulated_power.empty or actual_power.empty:
            logger.warning("Empty power data provided for MAPE calculation")
            return {
                "mape": float("inf"),
                "window_start": None,
                "window_end": None,
                "num_points": 0,
                "mean_simulated": 0.0,
                "mean_actual": 0.0,
            }

        earliest_sim = pd.to_datetime(simulated_power["timestamp"].min())
        earliest_actual = pd.to_datetime(actual_power["timestamp"].min())
        earliest_available = max(earliest_sim, earliest_actual)

        # Calculate window start (rolling window, but capped)
        max_window_start = window_end - self.mape_window
        window_start = max(earliest_available, max_window_start)

        logger.debug(
            f"MAPE window: {window_start.isoformat()} to {window_end.isoformat()} "
            f"({(window_end - window_start).total_seconds() / 60:.1f} minutes)"
        )

        # Filter both series to window
        sim_windowed = simulated_power[
            (pd.to_datetime(simulated_power["timestamp"]) >= window_start)
            & (pd.to_datetime(simulated_power["timestamp"]) <= window_end)
        ].copy()

        actual_windowed = actual_power[
            (pd.to_datetime(actual_power["timestamp"]) >= window_start)
            & (pd.to_datetime(actual_power["timestamp"]) <= window_end)
        ].copy()

        if sim_windowed.empty or actual_windowed.empty:
            logger.warning("No data in comparison window")
            return {
                "mape": float("inf"),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "num_points": 0,
                "mean_simulated": 0.0,
                "mean_actual": 0.0,
            }

        # Align timeseries by interpolation
        aligned_df = self._align_timeseries(
            cast(pd.DataFrame, sim_windowed), cast(pd.DataFrame, actual_windowed)
        )

        if aligned_df.empty:
            logger.warning("Failed to align timeseries")
            return {
                "mape": float("inf"),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "num_points": 0,
                "mean_simulated": 0.0,
                "mean_actual": 0.0,
            }

        # Calculate MAPE
        simulated = np.array(aligned_df["simulated_power"].values)
        actual = np.array(aligned_df["actual_power"].values)

        # Avoid division by zero
        mask = actual != 0
        if not np.any(mask):
            logger.error("All actual power values are zero, cannot calculate MAPE")
            return {
                "mape": float("inf"),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "num_points": len(aligned_df),
                "mean_simulated": float(np.mean(simulated)),
                "mean_actual": 0.0,
            }

        # MAPE formula: mean(abs((actual - simulated) / actual)) * 100
        percentage_errors = np.abs((actual[mask] - simulated[mask]) / actual[mask]) * 100
        mape = float(np.mean(percentage_errors))

        logger.debug(
            f"MAPE: {mape:.2f}% (n={len(aligned_df)}, "
            f"mean_sim={np.mean(simulated):.1f}W, mean_actual={np.mean(actual):.1f}W)"
        )

        return {
            "mape": mape,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "num_points": len(aligned_df),
            "mean_simulated": float(np.mean(simulated)),
            "mean_actual": float(np.mean(actual)),
        }

    def _align_timeseries(self, sim_df: pd.DataFrame, actual_df: pd.DataFrame) -> pd.DataFrame:
        """Align simulated and actual power timeseries by interpolation.

        Args:
            sim_df: Simulated power with columns [timestamp, power_draw]
            actual_df: Actual power with columns [timestamp, power_draw]

        Returns:
            Aligned DataFrame with columns [timestamp, simulated_power, actual_power]
        """
        # Ensure timestamps are datetime
        sim_df = sim_df.copy()
        actual_df = actual_df.copy()
        sim_df["timestamp"] = pd.to_datetime(sim_df["timestamp"])
        actual_df["timestamp"] = pd.to_datetime(actual_df["timestamp"])

        # Rename power columns
        sim_df = sim_df.rename(columns={"power_draw": "simulated_power"})
        actual_df = actual_df.rename(columns={"power_draw": "actual_power"})

        # Determine time range
        start_time = max(sim_df["timestamp"].min(), actual_df["timestamp"].min())
        end_time = min(sim_df["timestamp"].max(), actual_df["timestamp"].max())

        if start_time >= end_time:
            logger.warning("No overlapping time range between simulated and actual data")
            return pd.DataFrame({"timestamp": [], "simulated_power": [], "actual_power": []})

        # Create common time grid (use 60 second intervals)
        time_grid = pd.date_range(start=start_time, end=end_time, freq="60s")

        if len(time_grid) == 0:
            logger.warning("Empty time grid after alignment")
            return pd.DataFrame({"timestamp": [], "simulated_power": [], "actual_power": []})

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

        # Combine into single DataFrame
        aligned_df = pd.DataFrame(
            {
                "timestamp": time_grid,
                "simulated_power": sim_interpolated["simulated_power"].values,
                "actual_power": actual_interpolated["actual_power"].values,
            }
        )

        # Drop any rows with NaN
        aligned_df = aligned_df.dropna()

        logger.debug(f"Aligned {len(aligned_df)} data points on common time grid")

        return aligned_df
