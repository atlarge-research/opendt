"""Shared Pydantic models for ODT."""

from odt_common.models.consumption import Consumption
from odt_common.models.fragment import Fragment
from odt_common.models.task import Task
from odt_common.models.topology import (
    CPU,
    Cluster,
    CPUPowerModel,
    Host,
    Memory,
    Topology,
    TopologySnapshot,
)
from odt_common.models.workload_message import WorkloadMessage

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
    "CPUPowerModel",
    "WorkloadMessage",
]
