"""OpenDC Experiment Runner wrapper for simulator service."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from odt_common.models import Fragment, Task, Topology

from .java_home import detect_java_home

logger = logging.getLogger(__name__)

# OpenDC's input as OpenDT writes it, for the twin and the tutorial: columns without nulls, as
# OpenDC requires
TASK_SCHEMA = pa.schema(
    [
        ("id", pa.int32(), False),
        ("submission_time", pa.int64(), False),
        ("duration", pa.int64(), False),
        ("cpu_count", pa.int32(), False),
        ("cpu_capacity", pa.float64(), False),
        ("mem_capacity", pa.int64(), False),
    ]
)
FRAGMENT_SCHEMA = pa.schema(
    [
        ("id", pa.int32(), False),
        ("duration", pa.int64(), False),
        ("cpu_count", pa.int32(), False),
        ("cpu_usage", pa.float64(), False),
    ]
)
# How long past its time a run simulates the tasks: a run also serves the windows of the next hour,
# while no task arrives and the topology stays (ResultCache)
HORIZON = timedelta(hours=1)
# the columns the API reads (services/api/api/twin.py); OpenDC writes only these
COLUMNS = {
    "hostExportColumns": [
        "core_count",
        "cpu_capacity",
        "cpu_demand",
        "cpu_utilization",
        "tasks_running",
        "power_draw",
        "embodied_carbon",
    ],
    "taskExportColumns": ["task_id", "submission_time", "schedule_time", "finish_time"],
}


def experiment(
    name: str,
    inputs: Path,
    output: Path,
    exports: list[str],
    scheduler: str | None = None,
    workload: str = "workload",
    columns: dict | None = None,
) -> dict:
    """OpenDC's experiment: the topology.json and the `workload` folder in `inputs`, a sample of the
    `exports` every 150 s into `output`, only the `columns` given (e.g., COLUMNS); without a
    scheduler, OpenDC's default."""
    export = {"exportInterval": 150, "filesToExport": exports}
    if columns:
        export["computeExportConfig"] = columns
    experiment = {
        "name": name,
        "topologies": [{"pathToFile": str(inputs / "topology.json")}],
        "workloads": [{"pathToFile": str(inputs / workload), "type": "ComputeWorkload"}],
        "outputFolder": str(output),
        "exportModels": [export],
    }
    if scheduler:
        experiment["allocationPolicies"] = [{"type": "prefab", "policyName": scheduler}]
    return experiment


def cut(task: Task, until: datetime) -> list[Fragment]:
    """The task's fragments up to `until`, at most as long as since its submission: by then, the
    task has not run longer, so OpenDC's output up to `until` stays the same, while OpenDC stops
    soon after `until` instead of at the end of the last task, days later."""
    fragments, left = [], int((until - task.submission_time) / timedelta(milliseconds=1))
    for f in task.fragments:
        if left <= 0:
            break
        fragments.append(f if f.duration <= left else f.model_copy(update={"duration": left}))
        left -= f.duration
    return fragments


def environment() -> dict[str, str]:
    """OpenDC's JVM: within 1 GB (a week of SURF needs less), so the twin's parallel runs fit
    Docker's 8 GB; host names from /etc/hosts (without it, parallel runs can wait 5 s for DNS at
    start-up); and the serial garbage collector, which needs less CPU and memory on 2-core machines
    (e.g., Codespaces)."""
    opts = "-Xmx1g -Djdk.net.hosts.file=/etc/hosts -XX:+UseSerialGC"
    return {**os.environ, "JAVA_HOME": detect_java_home(), "OPEN_DC_EXPERIMENT_RUNNER_OPTS": opts}


class OpenDCRunner:
    """Wrapper around OpenDC ExperimentRunner binary.

    This runner handles:
    - Converting Task/Fragment models to Parquet files
    - Creating OpenDC experiment JSON files
    - Invoking the OpenDC binary
    - Parsing results from output Parquet files
    """

    def __init__(self, opendc_bin_path: Path | None = None) -> None:
        """Initialize the OpenDC runner."""
        if opendc_bin_path is None:
            opendc_bin_path = Path(
                "/app/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner"
            )

        self.opendc_path = opendc_bin_path

        if not self.opendc_path.exists():
            raise FileNotFoundError(
                f"OpenDC runner not found at {self.opendc_path}; mount OpenDC into the container"
            )

        logger.info(f"OpenDC runner initialized: {self.opendc_path}")

    def _create_tasks_parquet(self, tasks: list[Task], output_path: Path) -> None:
        """Create tasks.parquet file from Task models."""
        data = {
            "id": [t.id for t in tasks],
            "submission_time": [int(t.submission_time.timestamp() * 1000) for t in tasks],
            "duration": [t.duration for t in tasks],
            "cpu_count": [t.cpu_count for t in tasks],
            "cpu_capacity": [t.cpu_capacity for t in tasks],
            "mem_capacity": [t.mem_capacity for t in tasks],
        }

        pq.write_table(pa.Table.from_pydict(data, schema=TASK_SCHEMA), output_path)
        logger.debug(f"Created tasks.parquet with {len(tasks)} tasks")

    def _create_fragments_parquet(
        self, tasks: list[Task], output_path: Path, until: datetime | None = None
    ) -> None:
        """Create fragments.parquet file from Task models; with `until`, only the fragments up to
        then (see `cut`)."""
        all_fragments = [
            f for task in tasks for f in (cut(task, until) if until else task.fragments)
        ]
        data = {
            "id": [f.task_id for f in all_fragments],
            "duration": [f.duration for f in all_fragments],
            "cpu_count": [f.cpu_count for f in all_fragments],
            "cpu_usage": [f.cpu_usage for f in all_fragments],
        }

        pq.write_table(pa.Table.from_pydict(data, schema=FRAGMENT_SCHEMA), output_path)
        logger.debug(f"Created fragments.parquet with {len(all_fragments)} fragments")

    def _create_topology_json(self, topology: Topology, output_path: Path) -> None:
        """Create topology.json file from Topology model."""
        topology_dict = topology.model_dump(mode="json")

        with open(output_path, "w") as f:
            json.dump(topology_dict, f, indent=2)

        logger.debug(f"Created topology.json at {output_path}")

    def run_simulation(
        self,
        tasks: list[Task],
        topology: Topology,
        run_dir: Path,
        run_number: int,
        simulated_time: datetime,
        timeout_seconds: int = 120,
        scheduler: str | None = None,
        exports: tuple[str, ...] = ("powerSource",),
        future: bool = False,
    ) -> tuple[bool, Path]:
        """Run OpenDC on the tasks cut HORIZON after `simulated_time` (see `cut`), its `exports`
        into output/now/: up to the cut, the same as for the whole tasks. With `future`, a second
        OpenDC runs at once on the whole tasks, for their real start and finish times
        (output/future/task.parquet)."""

        logger.info(f"Starting OpenDC simulation: run_{run_number}")
        logger.debug(f"Tasks: {len(tasks)}, Fragments: {sum(len(t.fragments) for t in tasks)}")

        input_dir, output_dir = run_dir / "input", run_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = run_dir / "metadata.json"

        # the run up to now (in experiment.json, where the API reads the scheduler), and with
        # `future`, the whole tasks' run: per experiment, its name, exports, and cut
        runs = {"experiment.json": ("now", list(exports), simulated_time + HORIZON)}
        if future:
            runs["future.json"] = ("future", ["task"], None)

        try:
            # Create input files
            self._create_topology_json(topology, input_dir / "topology.json")
            for file, (name, files, until) in runs.items():
                workload_dir = input_dir / name
                workload_dir.mkdir(parents=True, exist_ok=True)
                self._create_tasks_parquet(tasks, workload_dir / "tasks.parquet")
                self._create_fragments_parquet(tasks, workload_dir / "fragments.parquet", until)
                run = experiment(name, input_dir, output_dir, files, scheduler, name, COLUMNS)
                (input_dir / file).write_text(json.dumps(run, indent=2))

            # Run OpenDC, the runs at once
            with ThreadPoolExecutor() as pool:
                results = list(
                    pool.map(
                        lambda file: self._execute_opendc(input_dir / file, timeout_seconds), runs
                    )
                )

            for result in results:
                if result.returncode != 0:
                    logger.error(f"OpenDC simulation failed with exit code {result.returncode}")
                    logger.error(f"stdout: {result.stdout[:500] if result.stdout else '(empty)'}")
                    logger.error(f"stderr: {result.stderr[:500] if result.stderr else '(empty)'}")
                    return False, output_dir

            # Write metadata
            metadata = {
                "run_number": run_number,
                "simulated_time": simulated_time.replace(microsecond=0).isoformat(),
                "last_task_time": (
                    tasks[-1].submission_time.replace(microsecond=0).isoformat() if tasks else None
                ),
                "task_count": len(tasks),
                "wall_clock_time": datetime.now(UTC)
                .replace(microsecond=0, tzinfo=None)
                .isoformat(),
                "cached": False,
            }
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Simulation complete: run_{run_number}")
            return True, output_dir

        except Exception as e:
            logger.error(f"Error running OpenDC simulation: {e}", exc_info=True)
            return False, output_dir

    def _execute_opendc(
        self, experiment_file: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        """Execute the OpenDC binary."""
        env = environment()
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
