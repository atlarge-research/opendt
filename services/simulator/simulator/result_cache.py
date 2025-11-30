"""Result caching for simulation service.

Caches simulation output directory paths based on inputs (topology + task count) to avoid
redundant OpenDC invocations when inputs haven't changed.
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
        topology_hash: SHA256 hash of topology JSON
        task_count: Number of tasks in the simulation
    """

    topology_hash: str
    task_count: int


class ResultCache:
    """Simple cache for simulation results to avoid redundant runs.

    Caches the last simulation's inputs (topology hash + task count) and run
    directory path. If the next simulation has identical inputs, the entire
    cached run directory (input/, output/, metadata.json) is copied to the
    new run location.
    """

    def __init__(self) -> None:
        """Initialize empty cache."""
        self.last_state: SimulationState | None = None
        self.last_run_dir: Path | None = None

    def _compute_topology_hash(self, topology: Topology) -> str:
        """Compute deterministic hash of topology.

        Args:
            topology: Topology to hash

        Returns:
            SHA256 hash of sorted JSON representation
        """
        topology_dict = topology.model_dump(mode="json")
        topology_json = json.dumps(topology_dict, sort_keys=True)
        return hashlib.sha256(topology_json.encode()).hexdigest()

    def can_reuse(self, topology: Topology, task_count: int) -> bool:
        """Check if cached results can be reused for given inputs.

        Args:
            topology: Current topology
            task_count: Current cumulative task count

        Returns:
            True if cache hit (topology and task count match), False otherwise
        """
        if self.last_state is None or self.last_run_dir is None:
            return False

        if not self.last_run_dir.exists():
            return False

        current_hash = self._compute_topology_hash(topology)

        return (
            current_hash == self.last_state.topology_hash
            and task_count == self.last_state.task_count
        )

    def get_cached_run_dir(self) -> Path | None:
        """Get cached run directory path.

        Returns:
            Path to cached run directory if available, None otherwise
        """
        return self.last_run_dir

    def copy_to_new_run(self, source_run_dir: Path, destination_run_dir: Path) -> None:
        """Copy all contents from cached run directory to new run location.

        This recursively copies all files and folders (input/, output/, metadata.json)
        from the cached run to the new run directory.

        Args:
            source_run_dir: Source run directory (e.g., run_3/)
            destination_run_dir: Destination run directory (e.g., run_5/)
        """
        if source_run_dir is None or not source_run_dir.exists():
            return

        # Create parent directory if needed
        destination_run_dir.parent.mkdir(parents=True, exist_ok=True)

        # Remove destination if it exists
        if destination_run_dir.exists():
            shutil.rmtree(destination_run_dir)

        # Copy entire run directory recursively
        shutil.copytree(source_run_dir, destination_run_dir)

    def update(self, topology: Topology, task_count: int, run_dir: Path) -> None:
        """Update cache with new simulation state and run directory.

        Args:
            topology: Topology used in simulation
            task_count: Number of tasks in simulation
            run_dir: Path to run directory (e.g., run_3/)
        """
        topology_hash = self._compute_topology_hash(topology)
        self.last_state = SimulationState(topology_hash=topology_hash, task_count=task_count)
        self.last_run_dir = run_dir

    def clear(self) -> None:
        """Clear the cache (e.g., when topology changes)."""
        self.last_state = None
        self.last_run_dir = None
