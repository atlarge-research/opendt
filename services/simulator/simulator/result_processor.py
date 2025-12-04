"""Result processor for OpenDC simulation outputs.

This module handles:
- Reading power usage results from OpenDC output
- Clipping results to only new data since last simulation
- Appending to aggregated results file
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class SimulationResultProcessor:
    """Processes and aggregates OpenDC simulation results."""

    def __init__(self, simulator_output_dir: Path):
        """Initialize the result processor.

        Args:
            simulator_output_dir: Base directory for simulator outputs
                                  (e.g., data/run_id/simulator/)
        """
        self.simulator_output_dir = Path(simulator_output_dir)
        self.agg_results_file = self.simulator_output_dir / "agg_results.parquet"
        self.last_processed_time: datetime | None = None

        # Initialize aggregated results file if needed
        if self.agg_results_file.exists():
            # Load the last timestamp from existing aggregated results
            try:
                existing_df = pd.read_parquet(self.agg_results_file)
                if not existing_df.empty and "timestamp" in existing_df.columns:
                    max_timestamp = pd.to_datetime(existing_df["timestamp"].max())
                    self.last_processed_time = max_timestamp.to_pydatetime()
                    if self.last_processed_time:
                        logger.info(
                            f"Resuming aggregation from {self.last_processed_time.isoformat()}"
                        )
            except Exception as e:
                logger.warning(f"Could not read existing aggregated results: {e}")

    def process_simulation_results(
        self,
        run_number: int,
        output_dir: Path,
        aligned_simulated_time: datetime,
        cached: bool = False,
    ) -> None:
        """Process results from a simulation run and append new data to aggregated file.

        Args:
            run_number: The simulation run number
            output_dir: Path to the output directory for this run (e.g., run_17/output/)
            aligned_simulated_time: The end time of this simulation run
            cached: Whether this was a cached result
        """
        logger.debug(
            f"Processing results for run {run_number} (cached: {cached}, "
            f"simulated_time: {aligned_simulated_time.isoformat()}, output_dir: {output_dir})"
        )

        try:
            # Read power source data from OpenDC output (search recursively)
            power_files = list(output_dir.rglob("powerSource.parquet"))

            if not power_files:
                logger.warning(f"No powerSource.parquet found in {output_dir}")
                return

            if len(power_files) > 1:
                logger.warning(
                    f"Found {len(power_files)} powerSource.parquet files, using first one"
                )

            power_file = power_files[0]
            logger.debug(f"Found power source file: {power_file.relative_to(output_dir)}")

            power_df = pd.read_parquet(power_file)
            logger.debug(f"Read {len(power_df)} rows from power source file")

            # Convert timestamp_absolute (in milliseconds) to datetime
            if "timestamp_absolute" not in power_df.columns:
                logger.error("No timestamp_absolute column found in power data")
                return

            # Convert from milliseconds to datetime (UTC-aware)
            power_df["timestamp"] = pd.to_datetime(
                power_df["timestamp_absolute"], unit="ms", utc=True
            )
            logger.debug(f"Converted timestamp_absolute to datetime for {len(power_df)} rows")

            # Clip to only new data since last processed time (start boundary)
            if self.last_processed_time is not None:
                original_count = len(power_df)
                power_df = power_df.loc[power_df["timestamp"] > self.last_processed_time].copy()
                logger.debug(
                    f"Clipped data at start: {original_count} -> {len(power_df)} rows "
                    f"(keeping data after {self.last_processed_time.isoformat()})"
                )

            # Clip data at end boundary (aligned_simulated_time)
            original_count = len(power_df)
            power_df = power_df.loc[power_df["timestamp"] <= aligned_simulated_time].copy()
            logger.debug(
                f"Clipped data at end: {original_count} -> {len(power_df)} rows "
                f"(keeping data up to {aligned_simulated_time.isoformat()})"
            )

            if power_df.empty:
                logger.info("No new data to append after clipping")
                return

            # Add metadata columns
            power_df["run_number"] = run_number
            power_df["cached"] = cached

            # Select and reorder columns to only retain required fields
            required_columns = [
                "timestamp",
                "run_number",
                "power_draw",
                "energy_usage",
                "carbon_intensity",
                "carbon_emission",
                "cached",
            ]

            # Check if all required columns exist
            missing_columns = [col for col in required_columns if col not in power_df.columns]
            if missing_columns:
                logger.warning(f"Missing columns in power data: {missing_columns}")
                # Only select columns that exist
                available_columns = [col for col in required_columns if col in power_df.columns]
                power_df = power_df[available_columns].copy()
            else:
                power_df = power_df[required_columns].copy()

            # Append to aggregated results
            if self.agg_results_file.exists():
                # Append to existing file
                existing_df = pd.read_parquet(self.agg_results_file)

                # Ensure existing data also only has required columns (for backwards compatibility)
                existing_columns = [col for col in required_columns if col in existing_df.columns]
                if existing_columns != list(existing_df.columns):
                    logger.info(f"Filtering existing data to required columns: {required_columns}")
                    existing_df = existing_df[existing_columns].copy()

                combined_df = pd.concat([existing_df, power_df], ignore_index=True)
                combined_df.to_parquet(self.agg_results_file, index=False)
                logger.info(
                    f"Appended {len(power_df)} rows to existing aggregated results "
                    f"(total: {len(combined_df)} rows)"
                )
            else:
                # Create new aggregated file
                power_df.to_parquet(self.agg_results_file, index=False)
                logger.info(f"Created new aggregated results file with {len(power_df)} rows")

            # Update last processed time
            max_timestamp = pd.to_datetime(power_df["timestamp"].max())
            self.last_processed_time = max_timestamp.to_pydatetime()
            if self.last_processed_time:
                logger.debug(
                    f"Updated last processed time to {self.last_processed_time.isoformat()}"
                )

        except Exception as e:
            logger.error(f"Error processing simulation results: {e}", exc_info=True)
            raise

    def get_aggregated_results(self) -> pd.DataFrame | None:
        """Get the current aggregated results.

        Returns:
            DataFrame with aggregated results, or None if no results exist
        """
        if not self.agg_results_file.exists():
            return None

        try:
            return pd.read_parquet(self.agg_results_file)
        except Exception as e:
            logger.error(f"Error reading aggregated results: {e}")
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the aggregated results.

        Returns:
            Dictionary with statistics
        """
        if not self.agg_results_file.exists():
            return {
                "exists": False,
                "row_count": 0,
                "last_processed_time": None,
            }

        try:
            df = pd.read_parquet(self.agg_results_file)
            return {
                "exists": True,
                "row_count": len(df),
                "last_processed_time": self.last_processed_time.isoformat()
                if self.last_processed_time
                else None,
                "time_range": {
                    "start": df["timestamp"].min().isoformat() if not df.empty else None,
                    "end": df["timestamp"].max().isoformat() if not df.empty else None,
                },
                "run_numbers": sorted(df["run_number"].unique().tolist()) if not df.empty else [],
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"exists": True, "error": str(e)}
