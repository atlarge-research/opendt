"""The twin's levers: a change from the control panel, as a new simulated topology (hosts, CO2 zone) and as
runtime settings, which the services follow on sys.config."""

import copy
from typing import Literal

from odt_common.config import PARALLEL_RUNS, SCHEDULER, SPEED_FACTOR, GlobalConfig
from odt_common.models import Topology
from pydantic import BaseModel, Field, field_validator

from api import twin

# OpenDC's placement schedulers (allocation policies); Mem is its default
SCHEDULERS = ("Mem", "CoreMem", "ActiveServers", "ActiveServersInv", "ProvisionedCores", "Random")
# the runtime settings, by the field that changes them
SETTINGS = {
    "scheduler": SCHEDULER,
    "speed_factor": SPEED_FACTOR,
    "parallel_simulations": PARALLEL_RUNS,
}


class Control(BaseModel):
    """A change from the control panel; the fields left out stay as they are. The hosts come in up to three
    groups, each a kind and a count; a count of 0 removes the group."""

    kind_1: Literal[tuple(twin.SERVERS)] | None = None
    count_1: int | None = Field(None, ge=0)
    kind_2: Literal[tuple(twin.SERVERS)] | None = None
    count_2: int | None = Field(None, ge=0)
    kind_3: Literal[tuple(twin.SERVERS)] | None = None
    count_3: int | None = Field(None, ge=0)
    carbon_zone: Literal[tuple(twin.CARBON_TRACES)] | None = None
    scheduler: Literal[SCHEDULERS] | None = None
    speed_factor: float | None = None
    parallel_simulations: int | None = Field(None, gt=0)  # of the calibrator

    @field_validator("speed_factor")
    @classmethod
    def twin_speed(cls, speed: float | None) -> float | None:
        return speed if speed is None else GlobalConfig(speed_factor=speed).speed_factor


def moves_topology(change: Control) -> bool:
    return bool(change.model_dump(exclude_none=True).keys() - SETTINGS.keys())


def topology(change: Control, sent: dict | None, latest: dict) -> dict:
    """The topology with the change of hosts or CO2 zone, built on the one sent last (a window may not have run
    it yet) with the r of the latest window (the calibrator may have changed it)."""
    topology = copy.deepcopy(sent or latest)
    cluster = topology["clusters"][0]
    r = latest["clusters"][0]["hosts"][0]["cpuPowerModel"]["calibrationFactor"]
    cluster["hosts"] = hosts(cluster["hosts"], change, r)
    if not cluster["hosts"]:
        raise ValueError("The twin needs at least one host")
    if change.carbon_zone:
        cluster["powerSource"]["carbonTracePath"] = twin.CARBON_TRACES[change.carbon_zone]
    return Topology(**topology).model_dump(mode="json")


def hosts(groups: list[dict], change: Control, r: float) -> list[dict]:
    """The host groups with the change applied, all with the twin's r: a new kind keeps its group's count, and
    groups of the same kind become one."""
    merged = {}
    for i, old in enumerate(twin.groups(groups), 1):
        new_kind, new_count = getattr(change, f"kind_{i}"), getattr(change, f"count_{i}")
        kind = new_kind or old["name"]
        count = old["count"] if new_count is None else new_count
        if new_kind and not count:
            raise ValueError(f"Hosts {i} need a count")
        if kind and count:
            base = old if kind == old["name"] else twin.SERVERS[kind]
            model = {**base["cpuPowerModel"], "calibrationFactor": r}
            host = {**base, "name": kind, "count": 0, "cpuPowerModel": model}
            merged.setdefault(kind, host)["count"] += count
    return list(merged.values())
