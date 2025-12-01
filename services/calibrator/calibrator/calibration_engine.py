"""Calibration engine for running parallel OpenDC simulations with different parameter values.

Uses ProcessPoolExecutor for parallel execution and manages directory structure.
"""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from odt_common.models import Task, Topology
from odt_common.odc_runner import OpenDCRunner

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """Result from a single calibration simulation."""

    sim_number: int  # Index of this simulation (0, 1, 2, ...)
    param_value: float  # Value of calibrated parameter
    sim_dir: Path  # Directory for this simulation (run_X/sim_Y/)
    power_df: pd.DataFrame | None  # Power timeseries from OpenDC (timestamp, power_draw)
    success: bool  # Whether simulation succeeded
    error_message: str | None  # Error message if failed


def _run_single_simulation(
    sim_number: int,
    param_value: float,
    topology: Topology,
    tasks: list[Task],
    sim_dir: Path,
    simulated_time: datetime,
    timeout_seconds: int,
) -> CalibrationResult:
    """Run a single OpenDC simulation (executed in worker process).

    Args:
        sim_number: Simulation index
        param_value: Value of calibrated parameter
        topology: Topology variant to simulate
        tasks: List of tasks to simulate
        sim_dir: Directory for this simulation
        simulated_time: Simulation time for metadata
        timeout_seconds: OpenDC timeout

    Returns:
        CalibrationResult with simulation outcome
    """
    try:
        # Initialize OpenDC runner in this process
        opendc_runner = OpenDCRunner()

        # Run simulation
        success, output_dir = opendc_runner.run_simulation(
            tasks=tasks,
            topology=topology,
            run_dir=sim_dir,
            run_number=sim_number,
            simulated_time=simulated_time,
            timeout_seconds=timeout_seconds,
        )

        if not success:
            return CalibrationResult(
                sim_number=sim_number,
                param_value=param_value,
                sim_dir=sim_dir,
                power_df=None,
                success=False,
                error_message="OpenDC simulation failed",
            )

        # Read power output
        power_files = list(output_dir.rglob("powerSource.parquet"))

        if not power_files:
            return CalibrationResult(
                sim_number=sim_number,
                param_value=param_value,
                sim_dir=sim_dir,
                power_df=None,
                success=False,
                error_message="No powerSource.parquet found in output",
            )

        power_file = power_files[0]
        power_raw_df = pd.read_parquet(power_file)

        # Convert timestamp_absolute (milliseconds) to datetime
        if "timestamp_absolute" not in power_raw_df.columns:
            return CalibrationResult(
                sim_number=sim_number,
                param_value=param_value,
                sim_dir=sim_dir,
                power_df=None,
                success=False,
                error_message="No timestamp_absolute column in power data",
            )

        power_raw_df["timestamp"] = pd.to_datetime(
            power_raw_df["timestamp_absolute"], unit="ms", utc=True
        )

        # Keep only needed columns - explicitly type as DataFrame
        power_df = cast(pd.DataFrame, power_raw_df[["timestamp", "power_draw"]].copy())

        return CalibrationResult(
            sim_number=sim_number,
            param_value=param_value,
            sim_dir=sim_dir,
            power_df=power_df,
            success=True,
            error_message=None,
        )

    except Exception as e:
        logger.error(f"Error in simulation {sim_number}: {e}", exc_info=True)
        return CalibrationResult(
            sim_number=sim_number,
            param_value=param_value,
            sim_dir=sim_dir,
            power_df=None,
            success=False,
            error_message=str(e),
        )


class CalibrationEngine:
    """Orchestrates parallel OpenDC simulations for calibration."""

    def __init__(self, max_workers: int = 4):
        """Initialize the calibration engine.

        Args:
            max_workers: Maximum number of parallel OpenDC simulations
        """
        self.max_workers = max_workers
        logger.info(f"Initialized CalibrationEngine with max_workers={max_workers}")

    def run_calibration_sweep(
        self,
        base_topology: Topology,
        tasks: list[Task],
        property_path: str,
        min_value: float,
        max_value: float,
        num_points: int,
        run_number: int,
        calibrator_run_dir: Path,
        simulated_time: datetime,
        topology_modifier_func: Any,
        timeout_seconds: int = 120,
    ) -> list[CalibrationResult]:
        """Run calibration sweep across parameter values.

        Args:
            base_topology: Base topology to modify
            tasks: List of tasks to simulate
            property_path: Dot-notation path to property to calibrate
            min_value: Minimum parameter value
            max_value: Maximum parameter value
            num_points: Number of linspace points
            run_number: Calibration run number
            calibrator_run_dir: Base directory for this calibration run (run_X/)
            simulated_time: Simulation time for metadata
            topology_modifier_func: Function to create topology variants
            timeout_seconds: OpenDC timeout

        Returns:
            List of CalibrationResult objects
        """
        # Generate parameter values to test (rounded to 2 decimal places)
        param_values = np.linspace(min_value, max_value, num_points)
        param_values = np.round(param_values, 2)

        logger.info(
            f"Starting calibration sweep for {property_path}: "
            f"{num_points} points from {min_value} to {max_value}"
        )

        # Create topology variants
        topologies = []
        for i, value in enumerate(param_values):
            rounded_value = round(float(value), 2)
            topology_variant = topology_modifier_func(property_path, rounded_value)
            if topology_variant is None:
                logger.error(f"Failed to create topology variant for value {rounded_value}")
                continue
            topologies.append((i, rounded_value, topology_variant))

        if not topologies:
            logger.error("No topology variants created, aborting calibration")
            return []

        # Create simulation directories
        sim_dirs = []
        for i, _value, _ in topologies:
            sim_dir = calibrator_run_dir / f"sim_{i}"
            sim_dir.mkdir(parents=True, exist_ok=True)
            sim_dirs.append(sim_dir)

        # Run simulations in parallel
        results = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all simulations
            futures = {}
            for (sim_num, param_value, topology_variant), sim_dir in zip(
                topologies, sim_dirs, strict=False
            ):
                future = executor.submit(
                    _run_single_simulation,
                    sim_num,
                    param_value,
                    topology_variant,
                    tasks,
                    sim_dir,
                    simulated_time,
                    timeout_seconds,
                )
                futures[future] = (sim_num, param_value)

            # Collect results as they complete
            for future in as_completed(futures):
                sim_num, param_value = futures[future]
                try:
                    result = future.result()
                    results.append(result)

                    if result.success:
                        logger.info(
                            f"✓ Simulation {sim_num} ({property_path}={param_value:.3f}) complete"
                        )
                    else:
                        logger.error(
                            f"✗ Simulation {sim_num} ({property_path}={param_value:.3f}) "
                            f"failed: {result.error_message}"
                        )

                except Exception as e:
                    logger.error(f"Exception in simulation {sim_num}: {e}", exc_info=True)
                    results.append(
                        CalibrationResult(
                            sim_number=sim_num,
                            param_value=param_value,
                            sim_dir=sim_dirs[sim_num],
                            power_df=None,
                            success=False,
                            error_message=str(e),
                        )
                    )

        # Sort results by sim_number for consistent ordering
        results.sort(key=lambda r: r.sim_number)

        successful = sum(1 for r in results if r.success)
        logger.info(
            f"Calibration sweep complete: {successful}/{len(results)} simulations succeeded"
        )

        return results
