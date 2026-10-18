"""The twin's levers: a change from the control panel, as a new simulated topology (hosts, CO2 zone) and as
runtime settings, which the services follow on sys.config."""

import copy
from typing import Literal

from odt_common.config import GlobalConfig
from odt_common.models import Topology
from pydantic import BaseModel, Field, field_validator

from api import twin

# OpenDC's placement schedulers (allocation policies); Mem is its default
SCHEDULERS = Literal[
    "Mem", "CoreMem", "ActiveServers", "ActiveServersInv", "ProvisionedCores", "Random"
]
KIND = Literal["H01", "EPYC", "Xeon", "Memory", "Edge"]  # twin.SERVERS
# the runtime settings, by the field that changes them
SETTINGS = {
    "scheduler": "simulator.scheduler",
    "speed_factor": "global.speed_factor",
    "parallel_simulations": "calibrator.max_parallel_workers",
}


class Control(BaseModel):
    """A change from the control panel; the fields left out stay as they are. The hosts come in up to three
    groups, each a kind and a count; a count of 0 removes the group."""

    kind_1: KIND | None = None
    count_1: int | None = Field(None, ge=0)
    kind_2: KIND | None = None
    count_2: int | None = Field(None, ge=0)
    kind_3: KIND | None = None
    count_3: int | None = Field(None, ge=0)
    carbon_zone: Literal["NL", "PL", "DE", "RO"] | None = None
    scheduler: SCHEDULERS | None = None
    speed_factor: float | None = None
    parallel_simulations: int | None = Field(None, gt=0)  # of the calibrator

    @field_validator("speed_factor")
    @classmethod
    def twin_speed(cls, speed: float | None) -> float | None:
        return speed if speed is None else GlobalConfig(speed_factor=speed).speed_factor


def moves_topology(change: Control) -> bool:
    return bool(change.model_dump(exclude_none=True).keys() - SETTINGS.keys())


def settings(change: Control) -> dict:
    """The runtime settings the change sets, by their key on sys.config."""
    return {
        SETTINGS[f]: v
        for f, v in change.model_dump(include=set(SETTINGS), exclude_none=True).items()
    }


def topology(change: Control, sent: dict | None, latest: dict) -> dict:
    """The topology with the change of hosts or CO2 zone, built on the one sent last (a window may not have run
    it yet) with the r of the latest window (the calibrator may have changed it)."""
    topology = copy.deepcopy(sent or latest)
    cluster = topology["clusters"][0]
    r = latest["clusters"][0]["hosts"][0]["cpuPowerModel"]["calibrationFactor"]
    for host in cluster["hosts"]:
        host["cpuPowerModel"]["calibrationFactor"] = r
    cluster["hosts"] = hosts(cluster["hosts"], change)
    if not cluster["hosts"]:
        raise ValueError("The twin needs at least one host")
    if change.carbon_zone:
        cluster["powerSource"]["carbonTracePath"] = twin.CARBON_TRACES[change.carbon_zone]
    return Topology(**topology).model_dump(mode="json")


def hosts(groups: list[dict], change: Control) -> list[dict]:
    """The twin's host groups with the change applied: a new kind keeps the group's count and takes the twin's r,
    and groups of the same kind become one."""
    r = groups[0]["cpuPowerModel"]["calibrationFactor"]
    merged = {}
    for i, old in enumerate(
        (groups + [{"name": None, "count": 0}] * twin.GROUPS)[: twin.GROUPS], 1
    ):
        kind = getattr(change, f"kind_{i}") or old["name"]
        count = getattr(change, f"count_{i}")
        count = old["count"] if count is None else count
        if getattr(change, f"kind_{i}") and not count:
            raise ValueError(f"Hosts {i} need a count")
        if not kind or not count:
            continue
        host = old
        if kind != old["name"]:
            model = {**twin.SERVERS[kind]["cpuPowerModel"], "calibrationFactor": r}
            host = {**twin.SERVERS[kind], "cpuPowerModel": model}
        if kind in merged:
            merged[kind]["count"] += count
        else:
            merged[kind] = {**host, "name": kind, "count": count}
    return list(merged.values())
