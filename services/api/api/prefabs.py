"""The prefabs of the Topology screen: CPUs, GPUs, and racks to build the datacenter from. They start as OpenDT ships
them (SURF's, OpenDC's), then are the user's: each edited, added, or removed, kept in the data folder (prefabs.json)
across runs of the twin; without that file, as shipped again."""

import copy
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

from api import data_dir

SHIPPED = {
    # with the idle and maximum power of the server: SURF's node; the CPUs of OpenDC web's host templates (Daniel
    # Halasz, branch feat/refactor-web); and of the Dell servers of OpenDC's RADiCe experiments (MachineSpecs.kt)
    "CPU": {
        "SURF-SARA": {"cores": 16, "ghz": 2.1, "idle_w": 25, "max_w": 174},
        "2x EPYC 7502": {"cores": 64, "ghz": 3.2, "idle_w": 120, "max_w": 400},
        "2x Xeon Gold 6248": {"cores": 40, "ghz": 2.5, "idle_w": 90, "max_w": 300},
        "2x Xeon Gold 6248R": {"cores": 48, "ghz": 2.9, "idle_w": 140, "max_w": 350},
        "2x EPYC 7742": {"cores": 128, "ghz": 2.6, "idle_w": 150, "max_w": 500},
        "Xeon E-2288G": {"cores": 8, "ghz": 3.7, "idle_w": 25, "max_w": 95},
        "Xeon E5-2670": {"cores": 16, "ghz": 2.6, "idle_w": 54.1, "max_w": 243},
        "Xeon X5670": {"cores": 12, "ghz": 2.93, "idle_w": 64, "max_w": 232},
        "Xeon, 32 cores": {"cores": 32, "ghz": 2.7, "idle_w": 110, "max_w": 446},
    },
    # of OpenDC web's GPU template, with its cubic power model
    "GPU": {
        "A100 40 GiB": {
            "cores": 6912,
            "ghz": 1.4,
            "memory_gb": 40,
            "idle_w": 100,
            "max_w": 400,
        },
    },
    # a kind of host and how many: SURF's 277, so that racks compare like with like; the RADiCe servers' memory
    "Rack": {
        "SURF-SARA": {
            "cpu": "SURF-SARA",
            "memory_gb": 128,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
        },
        "SURF-SARA, 4 A100": {
            "cpu": "SURF-SARA",
            "memory_gb": 128,
            "gpu": "A100 40 GiB",
            "gpus": 4,
            "hosts": 277,
        },
        "PowerEdge R620": {
            "cpu": "Xeon E5-2670",
            "memory_gb": 128,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
        },
        "PowerEdge R710": {
            "cpu": "Xeon X5670",
            "memory_gb": 96,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
        },
        "PowerEdge R820": {
            "cpu": "Xeon, 32 cores",
            "memory_gb": 756,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
        },
    },
}
FIELDS = {kind: list(next(iter(shipped.values()))) for kind, shipped in SHIPPED.items()}


class Cells(BaseModel):
    """The cells of a Topology table's row as the table sends them; an empty one, a list left as it was."""

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
        return None if value == "" else value


class Part(Cells):
    """A row of a prefabs table: its table (`kind`), `id`, the prefab's name before the change (none: a new one),
    and its cells; `remove`, a row deleted."""

    kind: Literal[tuple(SHIPPED)]
    id: str | None = None
    name: str | None = None
    hosts: int | None = None
    remove: bool = False


def file() -> Path:
    return data_dir() / "prefabs.json"


def load() -> dict:
    return json.loads(file().read_text()) if file().exists() else copy.deepcopy(SHIPPED)


def parts(kind: str) -> dict:
    return load()[kind]


def save(kind: str, old: str | None, cells: dict) -> None:
    """A part saved from its table: a new one (no `old`) starts as a copy of the first one, a changed one as it was;
    the cells the table leaves empty or at 0 keep their values."""
    prefabs = load()
    first = next(iter(prefabs[kind].values()), next(iter(SHIPPED[kind].values())))
    base = prefabs[kind].get(old, first)
    part = base | {f: v for f, v in cells.items() if f in FIELDS[kind] and v not in (None, 0)}
    if part.get("gpu", "None") != "None":
        part["gpus"] = part["gpus"] or 1  # one per host, until a count is given
    check(kind, part, prefabs)
    prefabs[kind].pop(old, None)
    prefabs[kind][cells.get("name") or old or f"New {kind}"] = part
    file().write_text(json.dumps(prefabs, indent=2))


def check(kind: str, part: dict, prefabs: dict) -> None:
    """A part the twin can run: positive numbers, and a rack of the prefabs' CPUs and GPUs."""
    if any(part[f] <= 0 for f in FIELDS[kind] if f not in ("cpu", "gpu", "gpus")):
        raise ValueError(f"{kind}: every number must be positive")
    if kind == "Rack" and (
        part["cpu"] not in prefabs["CPU"] or part["gpu"] not in ["None", *prefabs["GPU"]]
    ):
        raise ValueError(f"Rack: no CPU {part['cpu']!r} or GPU {part['gpu']!r} in the prefabs")


def remove(kind: str, name: str) -> None:
    prefabs = load()
    prefabs[kind].pop(name, None)
    file().write_text(json.dumps(prefabs, indent=2))
