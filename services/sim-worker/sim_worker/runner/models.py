"""Pydantic models for OpenDC simulation results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TimeseriesData(BaseModel):
    """Timeseries data point from simulation."""

    timestamp: int = Field(..., description="Simulation timestamp in milliseconds")
    value: float = Field(..., description="Metric value at this timestamp")


class SimulationResults(BaseModel):
    """Results from an OpenDC simulation run.

    Contains both summary statistics and full timeseries data for power and CPU metrics.
    """

    # Summary statistics
    energy_kwh: float = Field(
        default=0.0, description="Total energy consumed during simulation (kWh)"
    )
    cpu_utilization: float = Field(
        default=0.0, description="Average CPU utilization across all hosts (0-1)"
    )
    max_power_draw: float = Field(default=0.0, description="Maximum power draw observed (Watts)")
    runtime_hours: float = Field(default=0.0, description="Simulated runtime duration (hours)")
    status: Literal["success", "error"] = Field(default="success", description="Simulation status")
    error: str | None = Field(default=None, description="Error message if status is error")

    # Timeseries data
    power_draw_series: list[TimeseriesData] = Field(
        default_factory=list,
        description="Timeseries of power draw measurements (Watts) over simulation time",
    )
    cpu_utilization_series: list[TimeseriesData] = Field(
        default_factory=list,
        description="Timeseries of CPU utilization measurements (0-1) over simulation time",
    )
    
    # File paths (for experiment mode)
    temp_dir: str | None = Field(
        default=None, description="Temporary directory containing OpenDC input files"
    )
    opendc_output_dir: str | None = Field(
        default=None, description="Directory where OpenDC wrote its output files"
    )

    class Config:
        """Pydantic config."""

        frozen = False
