"""Consumption model from consumption.parquet."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Consumption(BaseModel):
    """Represents power/resource consumption data.

    Schema matches consumption.parquet:
    - power_draw: Power consumption in watts
    - energy_usage: Energy consumed in joules
    - timestamp: Absolute timestamp of measurement
    """

    power_draw: float = Field(..., description="Power consumption in watts", ge=0)
    energy_usage: float = Field(..., description="Energy consumed in joules", ge=0)
    timestamp: datetime = Field(..., description="Absolute timestamp of measurement")

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: datetime | int | float) -> datetime:
        """Parse timestamp from epoch milliseconds to datetime."""
        if isinstance(v, (int, float)):
            # Convert milliseconds to seconds for datetime
            return datetime.fromtimestamp(v / 1000.0)
        return v

    @property
    def energy_usage_kwh(self) -> float:
        """Get energy usage in kilowatt-hours (kWh).

        1 kWh = 3,600,000 joules
        """
        return self.energy_usage / 3_600_000.0

    @property
    def power_draw_kw(self) -> float:
        """Get power draw in kilowatts (kW)."""
        return self.power_draw / 1000.0

    class Config:
        json_schema_extra = {
            "example": {
                "power_draw": 250.5,
                "energy_usage": 125250.0,
                "timestamp": "2024-01-01T00:00:00Z",
            }
        }
