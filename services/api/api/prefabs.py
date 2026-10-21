"""The prefabs of the Topology screen: CPUs, GPUs, and racks to build the datacenter from. They start as OpenDT ships
them (prefabs.yaml: SURF's, OpenDC's), then are the user's: each edited, added, or removed, kept in the data folder
(prefabs.json) across runs of the twin; without that file, as shipped again."""

import copy
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator

from api import data_dir

SHIPPED = yaml.safe_load((Path(__file__).parent / "prefabs.yaml").read_text())
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
