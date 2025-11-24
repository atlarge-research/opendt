"""Topology models for datacenter infrastructure.

This module defines the hierarchical structure of a datacenter:
- Datacenter (root)
  - Clusters
    - Hosts
      - CPU
      - Memory
      - CPU Power Model
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CPU(BaseModel):
    """CPU specification for a host."""

    coreCount: int = Field(..., description="Number of CPU cores", gt=0)
    coreSpeed: float = Field(..., description="CPU speed in MHz", gt=0)


class Memory(BaseModel):
    """Memory specification for a host."""

    memorySize: int = Field(..., description="Memory size in bytes", gt=0)


class CPUPowerModel(BaseModel):
    """CPU power consumption model.

    Defines how CPU utilization translates to power consumption (Watts).
    """

    modelType: Literal["asymptotic", "linear", "square", "cubic", "sqrt"] = Field(
        ..., description="Power model type"
    )
    power: float = Field(..., description="Nominal power consumption in Watts", gt=0)
    idlePower: float = Field(..., description="Power at 0% utilization in Watts", ge=0)
    maxPower: float = Field(..., description="Power at 100% utilization in Watts", gt=0)
    asymUtil: float = Field(
        default=0.5,
        description="Asymptotic utilization coefficient (for asymptotic model)",
        ge=0,
        le=1,
    )
    dvfs: bool = Field(
        default=False,
        description="Dynamic Voltage and Frequency Scaling enabled",
    )


class Host(BaseModel):
    """Host (physical server) in a datacenter cluster."""

    name: str = Field(..., description="Host identifier/name")
    count: int = Field(..., description="Number of identical hosts", gt=0)
    cpu: CPU = Field(..., description="CPU specification")
    memory: Memory = Field(..., description="Memory specification")
    cpuPowerModel: CPUPowerModel = Field(..., description="CPU power consumption model")


class Cluster(BaseModel):
    """Cluster of hosts in a datacenter."""

    name: str = Field(..., description="Cluster identifier/name")
    hosts: list[Host] = Field(..., description="List of host types in this cluster", min_length=1)


class Topology(BaseModel):
    """Datacenter topology definition.

    Represents the hierarchical structure and hardware capabilities
    of a datacenter for simulation purposes.
    """

    clusters: list[Cluster] = Field(
        ..., description="List of clusters in the datacenter", min_length=1
    )

    def total_host_count(self) -> int:
        """Calculate total number of physical hosts across all clusters."""
        return sum(host.count for cluster in self.clusters for host in cluster.hosts)

    def total_core_count(self) -> int:
        """Calculate total number of CPU cores across all clusters."""
        return sum(
            host.count * host.cpu.coreCount for cluster in self.clusters for host in cluster.hosts
        )

    def total_memory_bytes(self) -> int:
        """Calculate total memory capacity in bytes across all clusters."""
        return sum(
            host.count * host.memory.memorySize
            for cluster in self.clusters
            for host in cluster.hosts
        )

    class Config:
        # Allow extra fields for forward compatibility
        extra = "allow"


class TopologySnapshot(BaseModel):
    """Timestamped topology snapshot for Kafka messages.

    Wraps a Topology with a timestamp indicating when it was captured/published.
    """

    timestamp: datetime = Field(
        ..., description="When this topology snapshot was captured (ISO 8601 format)"
    )
    topology: Topology = Field(..., description="The datacenter topology")

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S")
            if v.microsecond == 0
            else v.isoformat()
        }
