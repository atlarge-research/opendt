"""The twin's levers: a change from the control panel or the Topology table, as a new simulated topology (hosts,
CO2 zone) and as runtime settings, which the services follow on sys.config."""

import copy
from typing import Literal

from odt_common.config import (
    CALIBRATION,
    CALIBRATION_MAX,
    CALIBRATION_MIN,
    CALIBRATION_POINTS,
    MAPE_WINDOW,
    PARALLEL_RUNS,
    SCHEDULER,
    SPEED_FACTOR,
    GlobalConfig,
)
from odt_common.models import Topology
from pydantic import BaseModel, Field, field_validator

from api import hosts, twin

# OpenDC's placement schedulers (allocation policies); Mem is its default
SCHEDULERS = ("Mem", "CoreMem", "ActiveServers", "ActiveServersInv", "ProvisionedCores", "Random")
# the runtime settings, by the field that changes them
SETTINGS = {
    "scheduler": SCHEDULER,
    "speed_factor": SPEED_FACTOR,
    "parallel_simulations": PARALLEL_RUNS,
    "calibration": CALIBRATION,
    "calibration_min": CALIBRATION_MIN,
    "calibration_max": CALIBRATION_MAX,
    "calibration_points": CALIBRATION_POINTS,
    "mape_window": MAPE_WINDOW,
}


class Control(BaseModel):
    """A change from the control panel; the fields left out stay as they are."""

    hosts: int | None = Field(None, gt=0)  # of the first group; the Topology table edits them all
    carbon_zone: Literal[tuple(twin.CARBON_TRACES)] | None = None
    scheduler: Literal[SCHEDULERS] | None = None
    speed_factor: float | None = None
    parallel_simulations: int | None = Field(None, gt=0)  # of the calibrator
    calibration: bool | None = None  # on or off
    calibration_min: float | None = Field(None, gt=0)  # the range of r it tries, from
    calibration_max: float | None = Field(None, gt=0)  # to
    calibration_points: int | None = Field(None, ge=2)  # values of r in the range
    mape_window: int | None = Field(None, gt=0)  # [min] of power the MAPE is over

    @field_validator("speed_factor")
    @classmethod
    def twin_speed(cls, speed: float | None) -> float | None:
        return speed if speed is None else GlobalConfig(speed_factor=speed).speed_factor


def moves_topology(change: Control) -> bool:
    return bool(change.model_dump(exclude_none=True).keys() - SETTINGS.keys())


def topology(
    sent: dict | None, latest: dict, row: hosts.Row | None = None, zone: str | None = None
) -> dict:
    """The topology with a host group saved (a row of the Topology table) or another CO2 zone, built on the one
    sent last (a window may not have run it yet), all hosts with the r of the latest window (the calibrator may
    have changed it)."""
    topology = copy.deepcopy(sent or latest)
    cluster = topology["clusters"][0]
    if row:
        cluster["hosts"] = hosts.edit(cluster["hosts"], row)
    r = latest["clusters"][0]["hosts"][0]["cpuPowerModel"]["calibrationFactor"]
    for host in cluster["hosts"]:
        host["cpuPowerModel"]["calibrationFactor"] = r
    if zone:
        cluster["powerSource"]["carbonTracePath"] = twin.CARBON_TRACES[zone]
    return Topology(**topology).model_dump(mode="json")
