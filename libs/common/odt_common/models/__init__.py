"""Shared Pydantic models for ODT."""

from odt_common.models.consumption import Consumption
from odt_common.models.fragment import Fragment
from odt_common.models.task import Task
from odt_common.models.topology import (
    CPU,
    Cluster,
    Host,
    Memory,
    Topology,
    TopologySnapshot,
)

# Update forward references for Task.fragments
Task.model_rebuild()

__all__ = [
    "Task",
    "Fragment",
    "Consumption",
    "Topology",
    "TopologySnapshot",
    "Cluster",
    "Host",
    "CPU",
    "Memory",
]
