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
from typing import Annotated, Literal

from pydantic import BaseModel, Discriminator, Field, Tag


class CPU(BaseModel):
    """CPU specification for a host."""

    coreCount: int = Field(..., description="Number of CPU cores", gt=0)
    coreSpeed: float = Field(..., description="CPU speed in MHz", gt=0)


class Memory(BaseModel):
    """Memory specification for a host."""

    memorySize: int = Field(..., description="Memory size in bytes", gt=0)


class AsymptoticCPUPowerModel(BaseModel):
    """Asymptotic CPU power consumption model.

    Defines how CPU utilization translates to power consumption using
    an asymptotic curve.
    """

    modelType: Literal["asymptotic"] = Field(
        "asymptotic", description="Power model type (asymptotic)"
    )
    power: float = Field(..., description="Nominal power consumption in Watts", gt=0)
    idlePower: float = Field(..., description="Power at 0% utilization in Watts", ge=0)
    maxPower: float = Field(..., description="Power at 100% utilization in Watts", gt=0)
    asymUtil: float = Field(
        default=0.5,
        description="Asymptotic utilization coefficient",
        ge=0,
        le=1,
    )
    dvfs: bool = Field(
        default=False,
        description="Dynamic Voltage and Frequency Scaling enabled",
    )


class MseCPUPowerModel(BaseModel):
    """MSE-based CPU power consumption model.

    Defines how CPU utilization translates to power consumption using
    a calibration factor optimized via Mean Squared Error.
    """

    modelType: Literal["mse"] = Field("mse", description="Power model type (MSE)")
    power: float = Field(..., description="Nominal power consumption in Watts", gt=0)
    idlePower: float = Field(..., description="Power at 0% utilization in Watts", ge=0)
    maxPower: float = Field(..., description="Power at 100% utilization in Watts", gt=0)
    calibrationFactor: float = Field(
        default=0.5,
        description="Calibration factor for MSE model",
        ge=0,
        le=50,
    )


# Union of all CPU power model types
CPUPowerModel = Annotated[
    Annotated[AsymptoticCPUPowerModel, Tag("asymptotic")] | Annotated[MseCPUPowerModel, Tag("mse")],
    Discriminator("modelType"),
]


class Host(BaseModel):
    """Host (physical server) in a datacenter cluster."""

    name: str = Field(..., description="Host identifier/name")
    count: int = Field(..., description="Number of identical hosts", gt=0)
    cpu: CPU = Field(..., description="CPU specification")
    memory: Memory = Field(..., description="Memory specification")
    cpuPowerModel: AsymptoticCPUPowerModel | MseCPUPowerModel = Field(
        ..., description="CPU power consumption model"
    )


class PowerSource(BaseModel):
    """Power source configuration for a cluster."""

    carbonTracePath: str = Field(..., description="Path to carbon trace parquet file")


class Cluster(BaseModel):
    """Cluster of hosts in a datacenter."""

    name: str = Field(..., description="Cluster identifier/name")
    hosts: list[Host] = Field(..., description="List of host types in this cluster", min_length=1)
    powerSource: PowerSource | None = Field(
        None, description="Power source configuration (optional)"
    )


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
