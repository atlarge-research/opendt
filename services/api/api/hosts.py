"""The host groups as the Topology screen's table shows them: one row per group, edited in place, from a rack of the
portfolio, with its CPU and GPUs, or custom. OpenDT's units: MHz, and memory in SURF's unit (128 GB is 128,000,000)."""

import copy

from pydantic import BaseModel, field_validator

from api import portfolio


def specs(kind: str) -> dict:
    """The portfolio's CPUs or GPUs by name, their numbers only."""
    return {
        name: {f: part[f] for f in portfolio.FIELDS[kind]}
        for name, part in portfolio.parts(kind).items()
    }


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
    spec = specs("GPU")[name]
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
        "cpu": next((name for name, spec in specs("CPU").items() if spec == cpu(host)), "Custom"),
        **cpu(host),
        "memory_gb": host["memory"]["memorySize"] / 1e6,
        "gpu": next((n for n in specs("GPU") if gpus(n, gpu["count"]) == has), "Custom")
        if gpu
        else "None",
        "gpus": gpu["count"] if gpu else 0,
    }


def rows(topology: dict) -> list[dict]:
    return [row(i, host) for i, host in enumerate(topology["clusters"][0]["hosts"], 1)]


def edit(groups: list[dict], change: Row) -> list[dict]:
    """The groups with the row saved; a count of 0 removes one. A row without a number is a new group: its rack's
    hosts, or a copy of the first group without its GPUs, with what the row gives (the table starts a new row's
    numbers at 0). A rack picked for a group brings its CPU, memory, and GPUs."""
    groups = list(groups)
    racks = portfolio.parts("Rack")
    first = {k: v for k, v in groups[0].items() if k not in ("gpu", "gpuPowerModel")}
    if change.id is None:
        given = Row(**{k: v for k, v in change if v})
        new = {**first, "name": given.kind or "New", "count": 1}
        if given.kind in racks:
            new = host(rack(given.kind), new) | {"count": given.count or racks[given.kind]["hosts"]}
        groups.append(host(given, new))
    elif change.count == 0:
        del groups[change.id - 1]
    else:
        old = groups[change.id - 1]
        if change.kind in racks and change.kind != label(old):
            old = host(rack(change.kind), {**first, "name": change.kind, "count": old["count"]})
        groups[change.id - 1] = host(change, old)
    return groups


def rack(name: str) -> Row:
    """A rack of the portfolio as the cells of a row."""
    spec = portfolio.parts("Rack")[name]
    return Row(
        kind=name, cpu=spec["cpu"], memory_gb=spec["memory_gb"], gpu=spec["gpu"], gpus=spec["gpus"]
    )


def host(change: Row, old: dict) -> dict:
    """The group with the row's cells: a CPU or GPU picked from the lists brings its numbers, the other cells are
    as typed."""
    was = row(0, old)
    cells = {**was, **change.model_dump(exclude_none=True)}
    if cells["cpu"] != was["cpu"] and cells["cpu"] in specs("CPU"):
        cells |= specs("CPU")[cells["cpu"]]
    new = copy.deepcopy(old)
    new["name"] = old["name"] if cells["kind"] == was["kind"] else cells["kind"]
    new["count"] = cells["count"]
    new["cpu"] = {"coreCount": cells["cores"], "coreSpeed": cells["ghz"] * 1000}
    new["memory"] = {"memorySize": round(cells["memory_gb"] * 1e6)}
    new["cpuPowerModel"] |= {"idlePower": cells["idle_w"], "maxPower": cells["max_w"]}
    gpu, count = cells["gpu"], cells["gpus"]
    if gpu in specs("GPU") and (count or gpu != was["gpu"]):
        new |= gpus(gpu, count or 1)  # picked: one per host, until a count is given
    elif gpu == "Custom" and count:
        new["gpu"]["count"] = count
    else:  # None, or 0 GPUs
        new.pop("gpu", None)
        new.pop("gpuPowerModel", None)
    return new
