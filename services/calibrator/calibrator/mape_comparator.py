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

        # Log input data ranges
        sim_count = len(simulated_power)
        actual_count = len(actual_power)
        earliest_sim = pd.to_datetime(simulated_power["timestamp"].min())
        latest_sim = pd.to_datetime(simulated_power["timestamp"].max())
        earliest_actual = pd.to_datetime(actual_power["timestamp"].min())
        latest_actual = pd.to_datetime(actual_power["timestamp"].max())

        logger.info("=" * 80)
        logger.info("📊 MAPE Calculation - Data Windowing")
        logger.info("=" * 80)
        logger.info(
            f"Input Data Ranges:\n"
            f"  Simulated power: {sim_count} points\n"
            f"    └─ {earliest_sim.isoformat()} to {latest_sim.isoformat()}\n"
            f"  Actual power:    {actual_count} points\n"
            f"    └─ {earliest_actual.isoformat()} to {latest_actual.isoformat()}"
        )

        # Calculate rolling window: use last N minutes where N = mape_window_minutes
        # Window END should be the simulation_end_time (latest task time)
        # Window START should be END - mape_window_minutes (but not before data starts)
        logger.info(
            f"\nMAPE Window Calculation:\n"
            f"  Target window end:  {window_end.isoformat()}\n"
            f"  Max window length:  {self.mape_window_minutes} minutes\n"
            f"  → Calculate start:  {window_end.isoformat()} - {self.mape_window_minutes} min"
        )

        # Start from the END and go back mape_window_minutes
        ideal_window_start = window_end - self.mape_window
        
        # But ensure we have data available (don't go before earliest data)
        earliest_available = max(earliest_sim, earliest_actual)
        window_start = max(ideal_window_start, earliest_available)

        window_span_minutes = (window_end - window_start).total_seconds() / 60
        is_using_full_window = window_span_minutes >= self.mape_window_minutes

        logger.info(
            f"\nFinal MAPE Window:\n"
            f"  Start: {window_start.isoformat()}\n"
            f"  End:   {window_end.isoformat()}\n"
            f"  Span:  {window_span_minutes:.1f} minutes "
            f"({'CAPPED at max' if is_using_full_window else f'LIMITED by data ({window_span_minutes:.1f} < {self.mape_window_minutes})'})"
        )
        logger.info("=" * 80)

        # Filter both series to window
        sim_windowed = simulated_power[
            (pd.to_datetime(simulated_power["timestamp"]) >= window_start)
            & (pd.to_datetime(simulated_power["timestamp"]) <= window_end)
        ].copy()

        actual_windowed = actual_power[
            (pd.to_datetime(actual_power["timestamp"]) >= window_start)
            & (pd.to_datetime(actual_power["timestamp"]) <= window_end)
        ].copy()

        # Log what data actually fell within the window
        if not sim_windowed.empty and not actual_windowed.empty:
            sim_windowed_start = pd.to_datetime(sim_windowed["timestamp"].min())
            sim_windowed_end = pd.to_datetime(sim_windowed["timestamp"].max())
            actual_windowed_start = pd.to_datetime(actual_windowed["timestamp"].min())
            actual_windowed_end = pd.to_datetime(actual_windowed["timestamp"].max())
            
            logger.info(
                f"Data After Windowing:\n"
                f"  Simulated: {len(sim_windowed)} points from {sim_windowed_start.isoformat()} "
                f"to {sim_windowed_end.isoformat()}\n"
                f"  Actual:    {len(actual_windowed)} points from {actual_windowed_start.isoformat()} "
                f"to {actual_windowed_end.isoformat()}"
            )
        else:
            logger.debug(
                f"After windowing: {len(sim_windowed)} simulated, {len(actual_windowed)} actual"
            )

        if sim_windowed.empty or actual_windowed.empty:
            logger.warning(
                f"No data in MAPE window: {len(sim_windowed)} simulated, "
                f"{len(actual_windowed)} actual"
            )
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

        logger.debug(
            f"Aligned {len(aligned_df)} points: "
            f"mean_sim={np.mean(simulated):.1f}W, mean_actual={np.mean(actual):.1f}W"
        )

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

        logger.info(
            f"\n✅ MAPE Calculation Complete:\n"
            f"  Result:       {mape:.2f}%\n"
            f"  Valid points: {len(aligned_df[mask])}/{len(aligned_df)}\n"
            f"  Mean actual:  {np.mean(actual):.1f} W\n"
            f"  Mean simulated: {np.mean(simulated):.1f} W"
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
