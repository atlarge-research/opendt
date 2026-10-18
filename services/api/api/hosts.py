"""The host groups as the Topology screen's table shows them: one row per group, edited in place, with CPUs and GPUs
from prefabs or custom. OpenDT's units: MHz, and memory in SURF's unit (128 GB is 128,000,000)."""

import copy

from pydantic import BaseModel, field_validator

# SURF's node (H01) and the CPUs of OpenDC web's host templates (Daniel Halasz, branch feat/refactor-web), with the
# idle and maximum power of the template's server
CPUS = {
    "SURF-SARA": {"cores": 16, "ghz": 2.1, "idle_w": 25, "max_w": 174},
    "2x EPYC 7502": {"cores": 64, "ghz": 3.2, "idle_w": 120, "max_w": 400},
    "2x Xeon Gold 6248": {"cores": 40, "ghz": 2.5, "idle_w": 90, "max_w": 300},
    "2x Xeon Gold 6248R": {"cores": 48, "ghz": 2.9, "idle_w": 140, "max_w": 350},
    "2x EPYC 7742": {"cores": 128, "ghz": 2.6, "idle_w": 150, "max_w": 500},
    "Xeon E-2288G": {"cores": 8, "ghz": 3.7, "idle_w": 25, "max_w": 95},
}
# the GPU of OpenDC web's GPU template, with its cubic power model
GPUS = {"A100 40 GiB": {"cores": 6912, "ghz": 1.4, "memory_gb": 40, "idle_w": 100, "max_w": 400}}
# what the table's lists offer: a host can also have no GPU
PARTS = {"CPU": CPUS, "GPU": {"None": {}, **GPUS}}


class Row(BaseModel):
    """A row as the table sends it: the group's number (none for a new group) and its cells. The topology the row
    makes checks the values."""

    id: int | None = None
    kind: str | None = None
    count: int | None = None  # 0 removes the group
    cpu: str | None = None
    cores: int | None = None
    ghz: float | None = None
    memory_gb: float | None = None
    idle_w: float | None = None
    max_w: float | None = None
    gpu: str | None = None
    gpus: int | None = None  # per host

    @field_validator("*", mode="before")
    @classmethod
    def empty(cls, value):
        return None if value == "" else value  # a list left as it was


def label(host: dict) -> str:
    # SURF is the datacenter, SURF-SARA its cluster
    return "SURF-SARA" if host["name"] == "H01" else host["name"]


def summary(host: dict) -> str:
    """The group as the decisions name it, e.g., 2,770 SURF-SARA with 4 GPUs each."""
    gpus = f" with {host['gpu']['count']} GPUs each" if host.get("gpu") else ""
    return f"{host['count']:,} {label(host)}{gpus}"


def cpu(host: dict) -> dict:
    """The host's CPU and its power, in the table's units."""
    model = host["cpuPowerModel"]
    return {
        "cores": host["cpu"]["coreCount"],
        "ghz": host["cpu"]["coreSpeed"] / 1000,
        "idle_w": model["idlePower"],
        "max_w": model["maxPower"],
    }


def gpus(name: str, count: int) -> dict:
    """`count` GPUs of a prefab per host, with their power model, in OpenDT's format."""
    spec = GPUS[name]
    return {
        "gpu": {
            "count": count,
            "coreCount": spec["cores"],
            "coreSpeed": spec["ghz"] * 1000,
            "memorySize": round(spec["memory_gb"] * 1e6),
        },
        "gpuPowerModel": {
            "modelType": "cubic",
            "power": spec["max_w"],
            "idlePower": spec["idle_w"],
            "maxPower": spec["max_w"],
        },
    }


def row(i: int, host: dict) -> dict:
    """Group i as the table shows it; a CPU or GPU named after the prefab it matches."""
    gpu = host.get("gpu")
    has = {"gpu": gpu, "gpuPowerModel": host.get("gpuPowerModel")}
    return {
        "id": i,
        "kind": label(host),
        "count": host["count"],
        "cpu": next((name for name, specs in CPUS.items() if specs == cpu(host)), "Custom"),
        **cpu(host),
        "memory_gb": host["memory"]["memorySize"] / 1e6,
        "gpu": next((n for n in GPUS if gpus(n, gpu["count"]) == has), "Custom") if gpu else "None",
        "gpus": gpu["count"] if gpu else 0,
    }


def rows(topology: dict) -> list[dict]:
    return [row(i, host) for i, host in enumerate(topology["clusters"][0]["hosts"], 1)]


def edit(groups: list[dict], change: Row) -> list[dict]:
    """The groups with the row saved; a count of 0 removes one. A row without a number is a new group: a copy of
    the first one, without its GPUs, with what the row gives (the table starts a new row's numbers at 0)."""
    groups = list(groups)
    if change.id is None:
        given = Row(**{k: v for k, v in change if v})
        first = {k: v for k, v in groups[0].items() if k not in ("gpu", "gpuPowerModel")}
        groups.append(host(given, {**first, "name": given.kind or "New", "count": 1}))
    elif change.count == 0:
        del groups[change.id - 1]
    else:
        groups[change.id - 1] = host(change, groups[change.id - 1])
    return groups


def host(change: Row, old: dict) -> dict:
    """The group with the row's cells: a CPU or GPU picked from the lists brings its numbers, the other cells are
    as typed."""
    was = row(0, old)
    cells = {**was, **change.model_dump(exclude_none=True)}
    if cells["cpu"] != was["cpu"] and cells["cpu"] in CPUS:
        cells |= CPUS[cells["cpu"]]
    new = copy.deepcopy(old)
    new["name"] = old["name"] if cells["kind"] == was["kind"] else cells["kind"]
    new["count"] = cells["count"]
    new["cpu"] = {"coreCount": cells["cores"], "coreSpeed": cells["ghz"] * 1000}
    new["memory"] = {"memorySize": round(cells["memory_gb"] * 1e6)}
    new["cpuPowerModel"] |= {"idlePower": cells["idle_w"], "maxPower": cells["max_w"]}
    gpu, count = cells["gpu"], cells["gpus"]
    if gpu in GPUS and (count or gpu != was["gpu"]):
        new |= gpus(gpu, count or 1)  # picked: one per host, until a count is given
    elif gpu == "Custom" and count:
        new["gpu"]["count"] = count
    else:  # None, or 0 GPUs
        new.pop("gpu", None)
        new.pop("gpuPowerModel", None)
    return new
