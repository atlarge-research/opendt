"""OpenDC Experiment Runner wrapper for sim-worker."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from opendt_common.models import Task, Topology

from .java_home import detect_java_home
from .models import SimulationResults

logger = logging.getLogger(__name__)


class OpenDCRunner:
    """Wrapper around OpenDC ExperimentRunner binary.

    This runner handles:
    - Converting Task/Fragment models to Parquet files
    - Creating OpenDC experiment JSON files
    - Invoking the OpenDC binary
    - Parsing results from output Parquet files
    """

    def __init__(self, opendc_bin_path: Path | None = None) -> None:
        """Initialize the OpenDC runner.

        Args:
            opendc_bin_path: Path to OpenDCExperimentRunner binary.
                Defaults to /app/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner
        """
        if opendc_bin_path is None:
            opendc_bin_path = Path(
                "/app/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner"
            )

        self.opendc_path = opendc_bin_path

        # Verify the binary exists
        if not self.opendc_path.exists():
            raise FileNotFoundError(
                f"OpenDC runner not found at {self.opendc_path}. "
                "Ensure the OpenDC binaries are mounted into the container."
            )

        # Ensure it's executable
        if not os.access(self.opendc_path, os.X_OK):
            logger.warning(
                f"OpenDC runner not executable, attempting to fix permissions: {self.opendc_path}"
            )
            try:
                os.chmod(self.opendc_path, 0o755)
            except Exception as e:
                logger.error(f"Failed to make OpenDC runner executable: {e}")

        logger.info(f"✅ OpenDC runner initialized: {self.opendc_path}")

    def _create_tasks_parquet(self, tasks: list[Task], output_path: Path) -> None:
        """Create tasks.parquet file from Task models."""
        if not tasks:
            logger.warning("No tasks provided, creating empty tasks.parquet")
            schema = pa.schema(
                [
                    ("id", pa.int64()),
                    ("submission_time", pa.int64()),
                    ("duration", pa.int64()),
                    ("cpu_count", pa.int32()),
                    ("cpu_capacity", pa.float64()),
                    ("mem_capacity", pa.int64()),
                ]
            )
            table = pa.Table.from_pydict({}, schema=schema)
            pq.write_table(table, output_path)
            return

        # Create explicit schema (OpenDC requires non-nullable columns)
        schema = pa.schema(
            [
                ("id", pa.int32(), False),  # required (not nullable)
                ("submission_time", pa.int64(), False),
                ("duration", pa.int64(), False),
                ("cpu_count", pa.int32(), False),
                ("cpu_capacity", pa.float64(), False),
                ("mem_capacity", pa.int64(), False),
            ]
        )

        data = {
            "id": [t.id for t in tasks],
            "submission_time": [int(t.submission_time.timestamp() * 1000) for t in tasks],
            "duration": [t.duration for t in tasks],
            "cpu_count": [t.cpu_count for t in tasks],
            "cpu_capacity": [t.cpu_capacity for t in tasks],
            "mem_capacity": [t.mem_capacity for t in tasks],
        }

        table = pa.Table.from_pydict(data, schema=schema)
        pq.write_table(table, output_path)
        logger.debug(f"Created tasks.parquet with {len(tasks)} tasks")

    def _create_fragments_parquet(self, tasks: list[Task], output_path: Path) -> None:
        """Create fragments.parquet file from Task models."""
        all_fragments = []
        for task in tasks:
            all_fragments.extend(task.fragments)

        if not all_fragments:
            logger.warning("No fragments provided, creating empty fragments.parquet")
            schema = pa.schema(
                [
                    ("id", pa.int64()),
                    ("duration", pa.int64()),
                    ("cpu_count", pa.int32()),
                    ("cpu_usage", pa.float64()),
                ]
            )
            table = pa.Table.from_pydict({}, schema=schema)
            pq.write_table(table, output_path)
            return

        # Create explicit schema (OpenDC requires non-nullable columns)
        schema = pa.schema(
            [
                ("id", pa.int32(), False),  # required (not nullable)
                ("duration", pa.int64(), False),
                ("cpu_count", pa.int32(), False),
                ("cpu_usage", pa.float64(), False),
            ]
        )

        data = {
            "id": [f.task_id for f in all_fragments],
            "duration": [f.duration for f in all_fragments],
            "cpu_count": [f.cpu_count for f in all_fragments],
            "cpu_usage": [f.cpu_usage for f in all_fragments],
        }

        table = pa.Table.from_pydict(data, schema=schema)
        pq.write_table(table, output_path)
        logger.debug(f"Created fragments.parquet with {len(all_fragments)} fragments")

    def _create_topology_json(self, topology: Topology, output_path: Path) -> None:
        """Create topology.json file from Topology model."""
        topology_dict = topology.model_dump(mode="json")

        with open(output_path, "w") as f:
            json.dump(topology_dict, f, indent=2)

        logger.debug(f"Created topology.json at {output_path}")

    def _create_experiment_json(
        self,
        experiment_name: str,
        workload_path: Path,
        topology_path: Path,
        output_path: Path,
    ) -> None:
        """Create experiment.json file for OpenDC."""
        experiment = {
            "name": experiment_name,
            "topologies": [{"pathToFile": str(topology_path)}],
            "workloads": [{"pathToFile": str(workload_path), "type": "ComputeWorkload"}],
            "exportModels": [
                {
                    "exportInterval": 150,
                    "filesToExport": ["powerSource", "host", "task", "service"],
                    "computeExportConfig": {
                        "powerSourceExportColumns": ["energy_usage", "power_draw"]
                    },
                }
            ],
        }

        with open(output_path, "w") as f:
            json.dump(experiment, f, indent=2)

        logger.debug(f"Created experiment.json at {output_path}")

    def run_simulation(
        self,
        tasks: list[Task],
        topology: Topology,
        experiment_name: str = "sim-worker-window",
        timeout_seconds: int = 120,
    ) -> SimulationResults:
        """Run OpenDC simulation with given tasks and topology.

        Args:
            tasks: List of Task models (with fragments)
            topology: Topology model
            experiment_name: Name for this simulation run
            timeout_seconds: Maximum time to wait for simulation

        Returns:
            SimulationResults object with summary stats and timeseries data
        """
        logger.info(f"Starting OpenDC simulation: {experiment_name}")
        logger.debug(f"Tasks: {len(tasks)}, Fragments: {sum(len(t.fragments) for t in tasks)}")

        # Create temp directory for this simulation
        tmp_dir = Path("/tmp") / f"opendc-{experiment_name}-{os.getpid()}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        workload_dir = tmp_dir / "workload"
        workload_dir.mkdir(exist_ok=True)

        topology_file = tmp_dir / "topology.json"
        experiment_file = tmp_dir / "experiment.json"

        try:
            # Create input files
            self._create_tasks_parquet(tasks, workload_dir / "tasks.parquet")
            self._create_fragments_parquet(tasks, workload_dir / "fragments.parquet")
            self._create_topology_json(topology, topology_file)
            self._create_experiment_json(
                experiment_name, workload_dir, topology_file, experiment_file
            )

            # Run OpenDC
            result = self._execute_opendc(experiment_file, timeout_seconds)

            if result.returncode != 0:
                logger.error(f"OpenDC simulation failed with exit code {result.returncode}")
                logger.error(f"stdout: {result.stdout[:500] if result.stdout else '(empty)'}")
                logger.error(f"stderr: {result.stderr[:500] if result.stderr else '(empty)'}")

                error_msg = result.stderr if result.stderr else result.stdout
                if not error_msg:
                    error_msg = f"OpenDC exited with code {result.returncode}"

                return SimulationResults(status="error", error=error_msg)

            # Parse results
            results = self._parse_results(experiment_name)
            logger.info(f"Simulation complete: {experiment_name}")
            return results

        except Exception as e:
            logger.error(f"Error running OpenDC simulation: {e}", exc_info=True)
            return SimulationResults(status="error", error=str(e))

    def _execute_opendc(
        self, experiment_file: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        """Execute the OpenDC binary."""
        # Set up environment with JAVA_HOME
        env = os.environ.copy()
        if "JAVA_HOME" not in env:
            env["JAVA_HOME"] = detect_java_home()

        logger.debug(f"Using JAVA_HOME: {env['JAVA_HOME']}")

        # Build command
        command = [str(self.opendc_path), "--experiment-path", str(experiment_file)]
        logger.debug(f"Command: {' '.join(command)}")

        # Execute
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            logger.error(f"OpenDC timed out after {timeout}s")
            raise TimeoutError(f"OpenDC simulation timed out after {timeout}s") from e

        logger.debug(f"Exit code: {result.returncode}")
        if result.stdout:
            logger.debug(f"stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"stderr: {result.stderr}")

        return result

    def _parse_results(self, experiment_name: str) -> SimulationResults:
        """Parse OpenDC output files to extract metrics and timeseries data."""
        output_dir = Path("output") / experiment_name / "raw-output" / "0" / "seed=0"

        logger.debug(f"Looking for output in: {output_dir}")

        if not output_dir.exists():
            logger.warning(f"Output directory not found: {output_dir}")
            return SimulationResults(status="error", error="Output directory not found")

        try:
            from .models import TimeseriesData

            # Read power data (timeseries + summary)
            power_file = output_dir / "powerSource.parquet"
            power_series = []
            energy_kwh = 0.0
            max_power = 0.0

            if power_file.exists():
                power_df = pd.read_parquet(power_file)

                # Extract timeseries
                if "timestamp" in power_df.columns and "power_draw" in power_df.columns:
                    for _, row in power_df.iterrows():
                        power_series.append(
                            TimeseriesData(
                                timestamp=int(row["timestamp"]),
                                value=float(row["power_draw"]),
                            )
                        )

                # Calculate summary stats
                energy_kwh = power_df["energy_usage"].sum() / 3_600_000
                max_power = float(power_df["power_draw"].max())
            else:
                logger.warning("powerSource.parquet not found")

            # Read host data for CPU utilization (timeseries + summary)
            # host_file = output_dir / "host.parquet"
            # cpu_series = []
            cpu_util = 0.0

            # if host_file.exists():
            #     host_df = pd.read_parquet(host_file)

            #     if "cpu_utilization" in host_df.columns:
            #         # Extract timeseries
            #         if "timestamp" in host_df.columns:
            #             for _, row in host_df.iterrows():
            #                 cpu_series.append(
            #                     TimeseriesData(
            #                         timestamp=int(row["timestamp"]),
            #                         value=float(row["cpu_utilization"]),
            #                     )
            #                 )

            #         # Calculate summary stat (mean across all hosts and time)
            #         cpu_util = float(host_df["cpu_utilization"].mean())
            # else:
            #     logger.warning("host.parquet not found")

            # Read service data for runtime
            service_file = output_dir / "service.parquet"
            runtime_hours = 0.0

            if service_file.exists():
                service_df = pd.read_parquet(service_file)
                if "timestamp" in service_df.columns and len(service_df) > 0:
                    runtime_ms = service_df["timestamp"].max() - service_df["timestamp"].min()
                    runtime_hours = float(runtime_ms) / (1000 * 3600)
            else:
                logger.warning("service.parquet not found")

            logger.debug(f"Parsed {len(power_series)} power points")

            return SimulationResults(
                energy_kwh=round(float(energy_kwh), 4),
                cpu_utilization=round(float(cpu_util), 3),
                max_power_draw=round(float(max_power), 1),
                runtime_hours=round(float(runtime_hours), 2),
                status="success",
                power_draw_series=power_series,
                cpu_utilization_series=[],
            )

        except Exception as e:
            logger.error(f"Error parsing OpenDC results: {e}", exc_info=True)
            return SimulationResults(status="error", error=str(e))
