"""Result processor for calibration outputs.

This module handles:
- Writing metadata for each calibration sweep
- Tracking best calibration values
- Aggregating calibration results to parquet file
- Detecting topology changes
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class CalibrationResultProcessor:
    """Processes and aggregates calibration sweep results."""

    def __init__(self, calibrator_output_dir: Path):
        """Initialize the result processor.

        Args:
            calibrator_output_dir: Base directory for calibrator outputs
                                   (e.g., data/run_id/calibrator/)
        """
        self.calibrator_output_dir = Path(calibrator_output_dir)
        self.agg_results_file = self.calibrator_output_dir / "agg_results.parquet"
        self.last_best_value: float | None = None
        self.last_processed_time: datetime | None = None

        # Initialize by reading existing aggregated results if available
        if self.agg_results_file.exists():
            try:
                existing_df = pd.read_parquet(self.agg_results_file)
                if not existing_df.empty:
                    # Get the last best value
                    last_row = existing_df.iloc[-1]
                    self.last_best_value = float(last_row["best_value"])

                    # Get last processed time
                    if "timestamp" in existing_df.columns:
                        max_timestamp = pd.to_datetime(existing_df["timestamp"].max())
                        self.last_processed_time = max_timestamp.to_pydatetime()

                    logger.info(
                        f"Resuming calibration tracking: "
                        f"last_best_value={self.last_best_value}, "
                        f"last_time={self.last_processed_time}"
                    )
            except Exception as e:
                logger.warning(f"Could not read existing calibration results: {e}")

    def process_calibration_results(
        self,
        run_number: int,
        run_dir: Path,
        aligned_simulated_time: datetime,
        last_task_time: datetime,
        task_count: int,
        wall_clock_time: datetime,
        mape_results: dict[str, Any],
        best_value: float,
        best_mape: float,
        calibrated_property: str,
        topology_changed: bool,
    ) -> None:
        """Process results from a calibration sweep and update aggregated data.

        Args:
            run_number: The calibration run number
            run_dir: Path to the calibration run directory
            aligned_simulated_time: The end time of this calibration run
            last_task_time: Timestamp of the last task in the sweep
            task_count: Number of tasks processed
            wall_clock_time: Wall clock time when calibration completed
            mape_results: Dictionary mapping parameter values to MAPE scores
            best_value: The best calibration parameter value found
            best_mape: The MAPE score of the best value
            calibrated_property: Name of the property being calibrated
            topology_changed: Whether the topology was updated and broadcast
        """
        logger.debug(
            f"Processing calibration results for run {run_number}: "
            f"best_value={best_value}, best_mape={best_mape:.4f}, "
            f"topology_changed={topology_changed}"
        )

        try:
            # 1. Write metadata.json for this sweep
            self._write_sweep_metadata(
                run_dir=run_dir,
                run_number=run_number,
                aligned_simulated_time=aligned_simulated_time,
                last_task_time=last_task_time,
                task_count=task_count,
                wall_clock_time=wall_clock_time,
                mape_results=mape_results,
            )

            # 2. Append to aggregated results
            self._append_to_aggregated_results(
                run_number=run_number,
                timestamp=aligned_simulated_time,
                best_value=best_value,
                best_mape=best_mape,
                calibrated_property=calibrated_property,
                topology_changed=topology_changed,
                task_count=task_count,
            )

            # 3. Update tracking
            self.last_best_value = best_value
            self.last_processed_time = aligned_simulated_time

        except Exception as e:
            logger.error(f"Error processing calibration results: {e}", exc_info=True)
            raise

    def _write_sweep_metadata(
        self,
        run_dir: Path,
        run_number: int,
        aligned_simulated_time: datetime,
        last_task_time: datetime,
        task_count: int,
        wall_clock_time: datetime,
        mape_results: dict[str, Any],
    ) -> None:
        """Write metadata.json for a calibration sweep.

        Args:
            run_dir: Path to the calibration run directory
            run_number: The calibration run number
            aligned_simulated_time: The end time of this calibration run
            last_task_time: Timestamp of the last task
            task_count: Number of tasks processed
            wall_clock_time: Wall clock time
            mape_results: MAPE comparison results including window info
        """
        # Extract window info from mape_results
        # Note: window_start and window_end are already ISO format strings from MAPE comparator
        window_start_str = mape_results.get("window_start")
        window_end_str = mape_results.get("window_end")
        mape_by_value = mape_results.get("mape_by_value", {})

        # Round both MAPE values and keys to 2 decimal places
        rounded_mape_values = {
            f"{float(key):.2f}": round(float(value), 2) for key, value in mape_by_value.items()
        }

        # Build metadata structure
        metadata = {
            "run_number": run_number,
            "task_count": task_count,
            "wall_clock_time": wall_clock_time.replace(microsecond=0, tzinfo=None).isoformat(),
            "window": {
                "start": window_start_str if window_start_str else None,
                "end": (
                    window_end_str
                    if window_end_str
                    else aligned_simulated_time.replace(microsecond=0, tzinfo=None).isoformat()
                ),
            },
            "mape_values": rounded_mape_values,
        }

        metadata_file = run_dir / "metadata.json"
        try:
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.debug(f"Wrote calibration metadata to {metadata_file}")
        except Exception as e:
            logger.error(f"Failed to write metadata: {e}")
            raise

    def _append_to_aggregated_results(
        self,
        run_number: int,
        timestamp: datetime,
        best_value: float,
        best_mape: float,
        calibrated_property: str,
        topology_changed: bool,
        task_count: int,
    ) -> None:
        """Append calibration result to aggregated parquet file.

        Args:
            run_number: The calibration run number
            timestamp: Timestamp for this result
            best_value: The best calibration parameter value (rounded to 2 decimals)
            best_mape: The MAPE score of the best value
            calibrated_property: Name of the property being calibrated
            topology_changed: Whether the topology was updated and broadcast
            task_count: Number of tasks processed
        """
        # Create new row (ensure best_value is rounded to 2 decimal places)
        new_row = pd.DataFrame(
            {
                "timestamp": [timestamp],
                "run_number": [run_number],
                "calibrated_property": [calibrated_property],
                "best_value": [round(best_value, 2)],
                "best_mape": [round(best_mape, 2)],
                "topology_changed": [topology_changed],
                "task_count": [task_count],
            }
        )

        # Ensure timestamp is UTC-aware
        new_row["timestamp"] = pd.to_datetime(new_row["timestamp"], utc=True)

        if self.agg_results_file.exists():
            # Append to existing file
            existing_df = pd.read_parquet(self.agg_results_file)
            combined_df = pd.concat([existing_df, new_row], ignore_index=True)
            combined_df.to_parquet(self.agg_results_file, index=False)
            logger.info(
                f"Appended calibration result to aggregated file "
                f"(run {run_number}, best_value={best_value:.4f}, "
                f"topology_changed={topology_changed}, total: {len(combined_df)} rows)"
            )
        else:
            # Create new aggregated file
            new_row.to_parquet(self.agg_results_file, index=False)
            logger.info(
                f"Created new calibration aggregated results file "
                f"(run {run_number}, best_value={best_value:.4f})"
            )

    def should_broadcast_topology(self, new_best_value: float, tolerance: float = 1e-6) -> bool:
        """Determine if topology should be broadcast based on value change.

        Args:
            new_best_value: The newly found best calibration value
            tolerance: Minimum change to consider as different (default: 1e-6)

        Returns:
            True if topology should be broadcast, False otherwise
        """
        if self.last_best_value is None:
            # First calibration run, always broadcast
            logger.info(f"First calibration: will broadcast best_value={new_best_value:.4f}")
            return True

        value_changed = abs(new_best_value - self.last_best_value) > tolerance

        if value_changed:
            logger.info(
                f"Calibration value changed: {self.last_best_value:.4f} → {new_best_value:.4f} "
                f"(Δ={abs(new_best_value - self.last_best_value):.4f}), will broadcast"
            )
        else:
            logger.info(
                f"Calibration value unchanged: {new_best_value:.4f} "
                f"(Δ={abs(new_best_value - self.last_best_value):.4f} <= {tolerance}), "
                "skipping broadcast"
            )

        return value_changed

    def get_aggregated_results(self) -> pd.DataFrame | None:
        """Get the current aggregated calibration results.

        Returns:
            DataFrame with aggregated results, or None if no results exist
        """
        if not self.agg_results_file.exists():
            return None

        try:
            return pd.read_parquet(self.agg_results_file)
        except Exception as e:
            logger.error(f"Error reading aggregated calibration results: {e}")
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the aggregated calibration results.

        Returns:
            Dictionary with statistics
        """
        if not self.agg_results_file.exists():
            return {
                "exists": False,
                "run_count": 0,
                "last_best_value": None,
                "last_processed_time": None,
            }

        try:
            df = pd.read_parquet(self.agg_results_file)
            return {
                "exists": True,
                "run_count": len(df),
                "last_best_value": self.last_best_value,
                "last_processed_time": self.last_processed_time.isoformat()
                if self.last_processed_time
                else None,
                "time_range": {
                    "start": df["timestamp"].min().isoformat() if not df.empty else None,
                    "end": df["timestamp"].max().isoformat() if not df.empty else None,
                },
                "topology_changes": int(df["topology_changed"].sum()) if not df.empty else 0,
            }
        except Exception as e:
            logger.error(f"Error getting calibration stats: {e}")
            return {"exists": True, "error": str(e)}
