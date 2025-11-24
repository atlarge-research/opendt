"""Result caching for simulation worker.

Caches simulation results based on inputs (topology + task count) to avoid
redundant OpenDC invocations when inputs haven't changed.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from opendt_common.models import Topology

from .runner import SimulationResults


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
    
    Caches the last simulation's inputs (topology hash + task count) and outputs
    (SimulationResults). If the next window has identical inputs, the cached
    results are reused.
    """

    def __init__(self):
        """Initialize empty cache."""
        self.last_state: Optional[SimulationState] = None
        self.last_results: Optional[SimulationResults] = None

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
        if self.last_state is None or self.last_results is None:
            return False

        current_hash = self._compute_topology_hash(topology)

        return (
            current_hash == self.last_state.topology_hash
            and task_count == self.last_state.task_count
        )

    def get_cached_results(self) -> Optional[SimulationResults]:
        """Get cached simulation results.

        Returns:
            Cached SimulationResults if available, None otherwise
        """
        return self.last_results

    def update(self, topology: Topology, task_count: int, results: SimulationResults) -> None:
        """Update cache with new simulation state and results.

        Args:
            topology: Topology used in simulation
            task_count: Number of tasks in simulation
            results: Simulation results to cache
        """
        topology_hash = self._compute_topology_hash(topology)
        self.last_state = SimulationState(topology_hash=topology_hash, task_count=task_count)
        self.last_results = results
