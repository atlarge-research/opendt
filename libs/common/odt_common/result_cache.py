"""Result caching for simulation services.

Caches simulation output directory paths based on inputs (topology, scheduler, and task count) to
avoid redundant OpenDC invocations when inputs haven't changed.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from odt_common.models import Topology


@dataclass
class SimulationState:
    """State used to determine if simulation can be cached.

    Attributes:
        topology_hash: SHA256 hash of the topology JSON and the scheduler
        task_count: Number of tasks in the simulation
    """

    topology_hash: str
    task_count: int


class ResultCache:
    """Simple cache for simulation results to avoid redundant runs.

    Caches the last simulation's inputs (topology hash + task count) and run
    directory path. If the next simulation has identical inputs, the cached
    run directory (input/, output/) is copied to the new run location; the
    caller writes its metadata.json last.
    """

    def __init__(self) -> None:
        """Initialize empty cache."""
        self.last_state: SimulationState | None = None
        self.last_run_dir: Path | None = None

    def _compute_topology_hash(self, topology: Topology, scheduler: str | None) -> str:
        """Compute deterministic hash of the topology and the scheduler (none: OpenDC's default)."""
        inputs = {"topology": topology.model_dump(mode="json"), "scheduler": scheduler}
        return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

    def can_reuse(self, topology: Topology, scheduler: str | None, task_count: int) -> bool:
        """Check if cached results can be reused for given inputs."""
        if self.last_state is None or self.last_run_dir is None:
            return False

        if not self.last_run_dir.exists():
            return False

        current_hash = self._compute_topology_hash(topology, scheduler)

        return (
            current_hash == self.last_state.topology_hash
            and task_count == self.last_state.task_count
        )

    def get_cached_run_dir(self) -> Path | None:
        """Get cached run directory path."""
        return self.last_run_dir

    def copy_to_new_run(self, source_run_dir: Path, destination_run_dir: Path) -> None:
        """Copy the cached run directory to the new run location, without its metadata.json.

        Readers take a run with metadata.json as complete, so the caller writes that one last.
        """
        if source_run_dir is None or not source_run_dir.exists():
            return

        # Create parent directory if needed
        destination_run_dir.parent.mkdir(parents=True, exist_ok=True)

        # Remove destination if it exists
        if destination_run_dir.exists():
            shutil.rmtree(destination_run_dir)

        shutil.copytree(
            source_run_dir, destination_run_dir, ignore=shutil.ignore_patterns("metadata.json")
        )

    def update(
        self, topology: Topology, scheduler: str | None, task_count: int, run_dir: Path
    ) -> None:
        """Update cache with new simulation state and run directory."""
        topology_hash = self._compute_topology_hash(topology, scheduler)
        self.last_state = SimulationState(topology_hash=topology_hash, task_count=task_count)
        self.last_run_dir = run_dir
