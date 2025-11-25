"""Experiment Manager for sim-worker.

Handles all experiment-specific functionality:
- Result persistence to parquet files
- OpenDC I/O file archiving
- Power consumption plotting (actual vs simulated)
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from opendt_common.models import Task

from .runner import SimulationResults
from .window_manager import TimeWindow

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class ExperimentManager:
    """Manages experiment-specific operations for sim-worker.

    Responsibilities:
    - Writing simulation results to parquet files
    - Archiving OpenDC input/output files
    - Collecting actual power consumption data
    - Generating comparison plots (actual vs simulated power)
    """

    def __init__(
        self,
        experiment_name: str,
        experiment_output_dir: str,
        run_number: int,
    ):
        """Initialize the experiment manager.

        Args:
            experiment_name: Name of the experiment
            experiment_output_dir: Base directory for experiment outputs
            run_number: Run number for this experiment instance
        """
        self.experiment_name = experiment_name
        self.run_number = run_number

        # Setup directory structure
        self.experiment_run_dir = (
            Path(experiment_output_dir) / experiment_name / f"run_{run_number}"
        )
        self.experiment_run_dir.mkdir(parents=True, exist_ok=True)

        self.results_parquet_path = self.experiment_run_dir / "results.parquet"
        self.opendc_dir = self.experiment_run_dir / "opendc"
        self.opendc_dir.mkdir(parents=True, exist_ok=True)
        self.plot_path = self.experiment_run_dir / "power_plot.png"

        # Data collection
        self.actual_power_data: list[dict[str, Any]] = []

        logger.info("📁 Experiment directories created:")
        logger.info(f"   Run dir: {self.experiment_run_dir}")
        logger.info(f"   Results: {self.results_parquet_path}")
        logger.info(f"   OpenDC I/O: {self.opendc_dir}")
        logger.info(f"   Plot: {self.plot_path}")

    def record_actual_power(self, timestamp: datetime, power_draw: float) -> None:
        """Record actual power consumption from dc.power topic.

        Args:
            timestamp: Timestamp of the measurement
            power_draw: Power draw in Watts
        """
        self.actual_power_data.append(
            {
                "timestamp": timestamp,
                "power_draw": power_draw,
            }
        )
        logger.debug(f"Recorded actual power: {power_draw:.2f} W at {timestamp}")

    def write_simulation_results(
        self,
        window: TimeWindow,
        simulated_results: SimulationResults,
        cumulative_tasks: list[Task],
    ) -> None:
        """Write simulation results to parquet file.

        Extracts power draw for this specific window from cumulative simulation.

        Args:
            window: The window that was simulated
            simulated_results: Results from simulated topology simulation
            cumulative_tasks: All cumulative tasks (used to get first task time)
        """
        if not cumulative_tasks:
            logger.warning(f"No tasks to determine timestamp offset for window {window.window_id}")
            return

        # Get first task submission time for timestamp conversion
        first_task_time = cumulative_tasks[0].submission_time

        # Convert relative timestamps to absolute and filter for this window
        power_data = []
        for point in simulated_results.power_draw_series:
            # point.timestamp is milliseconds offset from first task
            absolute_time = first_task_time + timedelta(milliseconds=point.timestamp)

            # Only include if within this window's time range
            if window.window_start <= absolute_time < window.window_end:
                power_data.append(
                    {
                        "window_id": window.window_id,
                        "window_start": window.window_start,
                        "window_end": window.window_end,
                        "timestamp": absolute_time,
                        "power_draw": point.value,
                    }
                )

        if not power_data:
            logger.warning(
                f"No power draw data in window {window.window_id} time range "
                f"[{window.window_start} - {window.window_end})"
            )
            return

        # Create DataFrame and append to parquet
        df = pd.DataFrame(power_data)
        table = pa.Table.from_pandas(df)

        # Append to parquet file
        if self.results_parquet_path.exists():
            # Read existing and append
            existing_table = pq.read_table(self.results_parquet_path)
            combined_table = pa.concat_tables([existing_table, table])
            pq.write_table(combined_table, self.results_parquet_path)
        else:
            # Write new file
            pq.write_table(table, self.results_parquet_path)

        logger.info(
            f"📊 Wrote {len(power_data)} power measurements for window {window.window_id} "
            f"to {self.results_parquet_path.name}"
        )

    def archive_opendc_files(
        self,
        window: TimeWindow,
        simulated_results: SimulationResults,
        cumulative_tasks: list[Task],
    ) -> None:
        """Archive OpenDC input/output files for this window.

        Creates organized structure:
        - input/summary.json: Window metadata + task submission times
        - input/experiment.json, topology.json, *.parquet: OpenDC input files
        - output/summary.json: Power draw results over time
        - output/*.parquet: OpenDC output files

        Args:
            window: The window that was simulated
            simulated_results: Simulation results containing temp_dir path
            cumulative_tasks: All cumulative tasks used in simulation
        """
        if not simulated_results.temp_dir:
            logger.warning(f"No temp_dir in simulation results for window {window.window_id}")
            return

        import json

        # Create window-specific directory structure
        window_dir = self.opendc_dir / f"window_{window.window_id:04d}"
        input_dir = window_dir / "input"
        output_dir_dest = window_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir_dest.mkdir(parents=True, exist_ok=True)

        temp_dir = Path(simulated_results.temp_dir)

        # Create input/summary.json with window metadata + task submission times
        input_summary = {
            "window_id": window.window_id,
            "window_start": window.window_start.isoformat(),
            "window_end": window.window_end.isoformat(),
            "task_count": len(window.tasks),
            "cumulative_task_count": len(cumulative_tasks),
            "task_submission_times": [
                task.submission_time.isoformat() for task in cumulative_tasks
            ],
        }

        input_summary_path = input_dir / "summary.json"
        with open(input_summary_path, "w") as f:
            json.dump(input_summary, f, indent=2)

        # Copy OpenDC input files
        input_files = [
            temp_dir / "experiment.json",
            temp_dir / "topology.json",
            temp_dir / "workload" / "tasks.parquet",
            temp_dir / "workload" / "fragments.parquet",
        ]

        for input_file in input_files:
            if input_file.exists():
                shutil.copy2(input_file, input_dir / input_file.name)

        # Copy entire OpenDC output directory from temp to archive
        output_dir_src = (
            Path(simulated_results.opendc_output_dir)
            if simulated_results.opendc_output_dir
            else None
        )

        if output_dir_src and output_dir_src.exists():
            # Copy all files from OpenDC output directory
            for item in output_dir_src.iterdir():
                if item.is_file():
                    shutil.copy2(item, output_dir_dest / item.name)
                    logger.debug(f"Copied {item.name} to {output_dir_dest}")

            logger.debug(f"Copied OpenDC output directory: {output_dir_src} -> {output_dir_dest}")
        else:
            logger.warning(f"OpenDC output directory not found or not set: {output_dir_src}")

        # Create output/summary.json with power draw results and summary stats
        output_summary = {
            "window_id": window.window_id,
            "window_start": window.window_start.isoformat(),
            "window_end": window.window_end.isoformat(),
            "summary_statistics": {
                "energy_kwh": simulated_results.energy_kwh,
                "max_power_draw_w": simulated_results.max_power_draw,
                "avg_cpu_utilization": simulated_results.cpu_utilization,
                "runtime_hours": simulated_results.runtime_hours,
            },
            "power_draw_timeseries": [
                {
                    "timestamp_ms": data_point.timestamp,
                    "power_draw_w": data_point.value,
                }
                for data_point in simulated_results.power_draw_series
            ]
            if simulated_results.power_draw_series
            else [],
        }

        output_summary_path = output_dir_dest / "summary.json"
        with open(output_summary_path, "w") as f:
            json.dump(output_summary, f, indent=2)

        logger.debug(f"📁 Archived OpenDC I/O files for window {window.window_id}")

    def generate_power_plot(self) -> None:
        """Generate comparison plot of actual vs predicted power consumption.

        Creates a time-series plot showing:
        - Actual power (ground truth from dc.power)
        - Simulated power (predicted by OpenDC)

        The plot is saved to power_plot.png and overwritten with each update.
        """
        if not self.results_parquet_path.exists():
            logger.warning("No experiment parquet file found, skipping plot generation")
            return

        if not self.actual_power_data:
            logger.warning("No actual power data available, skipping plot generation")
            return

        try:
            # Read simulated power data from parquet
            simulated_df = pq.read_table(self.results_parquet_path).to_pandas()

            # Convert actual power data to DataFrame
            actual_df = pd.DataFrame(self.actual_power_data)

            # Filter actual power to only show up to the latest simulated timestamp
            # (simulator may lag behind real-time data collection)
            max_simulated_time = simulated_df["timestamp"].max()
            actual_df_filtered = actual_df[actual_df["timestamp"] <= max_simulated_time].copy()

            if len(actual_df_filtered) == 0:
                logger.warning("No actual power data available up to simulated time range")
                return

            logger.debug(
                f"Plot time range: {len(actual_df_filtered)}/{len(actual_df)} actual power points "
                f"(up to {max_simulated_time})"
            )

            # Convert power from Watts to Kilowatts
            simulated_df["power_kw"] = simulated_df["power_draw"] / 1000.0
            actual_df_filtered["power_kw"] = actual_df_filtered["power_draw"] / 1000.0

            # Create plot
            plt.figure(figsize=(12, 6))

            # Plot actual power (ground truth) - only up to simulated time
            plt.plot(
                actual_df_filtered["timestamp"],
                actual_df_filtered["power_kw"],
                label="Actual Power (Ground Truth)",
                color="blue",
                linewidth=1.5,
                alpha=0.8,
            )

            # Plot simulated power
            plt.plot(
                simulated_df["timestamp"],
                simulated_df["power_kw"],
                label="Simulated Power (OpenDC)",
                color="orange",
                linewidth=1.5,
                alpha=0.8,
            )

            plt.xlabel("Time")
            plt.ylabel("Power (kW)")
            plt.title(f"Power Consumption: Actual vs Simulated - {self.experiment_name}")
            plt.ylim(0, 32)  # 0-100 kW
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save plot
            plt.savefig(self.plot_path, dpi=150)
            plt.close()

            logger.info(f"📈 Updated power consumption plot: {self.plot_path.name}")

        except Exception as e:
            logger.error(f"Failed to generate power plot: {e}", exc_info=True)

    @staticmethod
    def get_next_run_number(experiment_name: str, experiment_output_dir: str) -> int:
        """Get the next run number for an experiment.

        Scans output/<experiment_name>/ for existing run_N directories
        and returns N+1.

        Args:
            experiment_name: Name of the experiment
            experiment_output_dir: Base output directory path

        Returns:
            Next run number (1 if no existing runs)
        """
        experiment_dir = Path(experiment_output_dir) / experiment_name
        if not experiment_dir.exists():
            return 1

        existing_runs = [
            int(d.name.replace("run_", ""))
            for d in experiment_dir.iterdir()
            if d.is_dir() and d.name.startswith("run_")
        ]

        return max(existing_runs, default=0) + 1
