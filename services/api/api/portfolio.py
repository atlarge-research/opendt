"""The portfolio of the Topology screen: CPUs, GPUs, and racks to build the datacenter from. It starts preconfigured
(SURF's, OpenDC's), then is the user's: each part edited, added, or removed, kept in the data folder (portfolio.json)
across runs of the twin; without that file, it is preconfigured again."""

import copy
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

PRESETS = {
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
FIELDS = {kind: list(next(iter(presets.values()))) for kind, presets in PRESETS.items()}


class Part(BaseModel):
    """A row of a portfolio table as the table sends it: its table (`kind`), `id`, the part's name before the
    change (none: a new part), and its cells; `remove`, a row deleted."""

    kind: Literal["CPU", "GPU", "Rack"]
    id: str | None = None
    name: str | None = None
    cores: int | None = None
    ghz: float | None = None
    memory_gb: float | None = None
    idle_w: float | None = None
    max_w: float | None = None
    cpu: str | None = None
    gpu: str | None = None
    gpus: int | None = None
    hosts: int | None = None
    remove: bool = False

    @field_validator("*", mode="before")
    @classmethod
    def empty(cls, value):
        return None if value == "" else value


def file() -> Path:
    return Path(os.getenv("DATA_DIR", "/app/data")) / "portfolio.json"


def load() -> dict:
    return json.loads(file().read_text()) if file().exists() else copy.deepcopy(PRESETS)


def parts(kind: str) -> dict:
    return load()[kind]


def save(kind: str, old: str | None, cells: dict) -> None:
    """A part saved from its table: a new one (no `old`) starts as a copy of the first one, a changed one as it was;
    the cells the table leaves empty or at 0 keep their values."""
    portfolio = load()
    first = next(iter(portfolio[kind].values()), next(iter(PRESETS[kind].values())))
    base = portfolio[kind].get(old, first)
    part = base | {f: v for f, v in cells.items() if f in FIELDS[kind] and v not in (None, 0)}
    if part.get("gpu", "None") != "None":
        part["gpus"] = part["gpus"] or 1  # one per host, until a count is given
    check(kind, part, portfolio)
    portfolio[kind].pop(old, None)
    portfolio[kind][cells.get("name") or old or f"New {kind}"] = part
    file().write_text(json.dumps(portfolio, indent=2))


def check(kind: str, part: dict, portfolio: dict) -> None:
    """A part the twin can run: positive numbers, and a rack of the portfolio's CPUs and GPUs."""
    if any(part[f] <= 0 for f in FIELDS[kind] if f not in ("cpu", "gpu", "gpus")):
        raise ValueError(f"{kind}: every number must be positive")
    if kind == "Rack" and (
        part["cpu"] not in portfolio["CPU"] or part["gpu"] not in ["None", *portfolio["GPU"]]
    ):
        raise ValueError(f"Rack: no CPU {part['cpu']!r} or GPU {part['gpu']!r} in the portfolio")


def remove(kind: str, name: str) -> None:
    portfolio = load()
    portfolio[kind].pop(name, None)
    file().write_text(json.dumps(portfolio, indent=2))
