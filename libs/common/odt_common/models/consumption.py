"""Consumption model, as in consumption.parquet."""

from pydantic import BaseModel, Field

from odt_common.models.task import UtcDatetime


class Consumption(BaseModel):
    """A power measurement of the datacenter, at an absolute time."""

    power_draw: float = Field(..., description="Power consumption in watts", ge=0)
    energy_usage: float = Field(..., description="Energy consumed in joules", ge=0)
    timestamp: UtcDatetime = Field(..., description="Absolute timestamp of measurement")
