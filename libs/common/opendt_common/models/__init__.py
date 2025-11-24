"""Shared Pydantic models for OpenDT."""

from opendt_common.models.consumption import Consumption
from opendt_common.models.fragment import Fragment
from opendt_common.models.task import Task
from opendt_common.models.topology import (
    CPU,
    Cluster,
    CPUPowerModel,
    Host,
    Memory,
    Topology,
    TopologySnapshot,
)
from opendt_common.models.workload_message import WorkloadMessage

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
