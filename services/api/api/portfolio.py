"""The portfolio of the Topology screen: CPUs, GPUs, and racks to build the datacenter from, preconfigured or the
user's own. The user's own are kept in the data folder (portfolio.json), across runs of the twin."""

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

WEB = "OpenDC web"  # its host templates (Daniel Halasz, branch feat/refactor-web)
RADICE = "OpenDC, RADiCe"  # the Dell servers of OpenDC's RADiCe experiments: their power idle and at full load
PRESETS = {
    # with the idle and maximum power of the server
    "CPU": {
        "SURF-SARA": {"cores": 16, "ghz": 2.1, "idle_w": 25, "max_w": 174, "from": "SURF"},
        "2x EPYC 7502": {"cores": 64, "ghz": 3.2, "idle_w": 120, "max_w": 400, "from": WEB},
        "2x Xeon Gold 6248": {"cores": 40, "ghz": 2.5, "idle_w": 90, "max_w": 300, "from": WEB},
        "2x Xeon Gold 6248R": {"cores": 48, "ghz": 2.9, "idle_w": 140, "max_w": 350, "from": WEB},
        "2x EPYC 7742": {"cores": 128, "ghz": 2.6, "idle_w": 150, "max_w": 500, "from": WEB},
        "Xeon E-2288G": {"cores": 8, "ghz": 3.7, "idle_w": 25, "max_w": 95, "from": WEB},
        "Xeon E5-2670": {"cores": 16, "ghz": 2.6, "idle_w": 54.1, "max_w": 243, "from": RADICE},
        "Xeon X5670": {"cores": 12, "ghz": 2.93, "idle_w": 64, "max_w": 232, "from": RADICE},
        "Xeon, 32 cores": {"cores": 32, "ghz": 2.7, "idle_w": 110, "max_w": 446, "from": RADICE},
    },
    # with its cubic power model
    "GPU": {
        "A100 40 GiB": {
            "cores": 6912,
            "ghz": 1.4,
            "memory_gb": 40,
            "idle_w": 100,
            "max_w": 400,
            "from": WEB,
        },
    },
    # a kind of host and how many: SURF's 277, so that racks compare like with like
    "Rack": {
        "SURF-SARA": {
            "cpu": "SURF-SARA",
            "memory_gb": 128,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
            "from": "SURF",
        },
        "SURF-SARA, 4 A100": {
            "cpu": "SURF-SARA",
            "memory_gb": 128,
            "gpu": "A100 40 GiB",
            "gpus": 4,
            "hosts": 277,
            "from": f"SURF, {WEB}",
        },
        "PowerEdge R620": {
            "cpu": "Xeon E5-2670",
            "memory_gb": 128,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
            "from": RADICE,
        },
        "PowerEdge R710": {
            "cpu": "Xeon X5670",
            "memory_gb": 96,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
            "from": RADICE,
        },
        "PowerEdge R820": {
            "cpu": "Xeon, 32 cores",
            "memory_gb": 756,
            "gpu": "None",
            "gpus": 0,
            "hosts": 277,
            "from": RADICE,
        },
    },
}
FIELDS = {
    kind: [f for f in next(iter(presets.values())) if f != "from"]
    for kind, presets in PRESETS.items()
}


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


def own() -> dict:
    return json.loads(file().read_text()) if file().exists() else {kind: {} for kind in PRESETS}


def parts(kind: str) -> dict:
    """The parts of a kind, preconfigured first, each with where it comes from."""
    return PRESETS[kind] | {name: spec | {"from": "Yours"} for name, spec in own()[kind].items()}


def save(kind: str, old: str | None, cells: dict) -> None:
    """A part saved from its table, as the user's own: a new one (no `old`) a copy of the first preset, a
    preconfigured one left as it is (its change saved under `<name> (yours)` unless renamed); the cells the table
    leaves empty or at 0 keep their values."""
    base = parts(kind)[old] if old else next(iter(PRESETS[kind].values()))
    spec = {f: base[f] for f in FIELDS[kind]} | {
        f: v for f, v in cells.items() if f in FIELDS[kind] and v not in (None, 0)
    }
    if spec.get("gpu", "None") != "None":
        spec["gpus"] = spec["gpus"] or 1  # one per host, until a count is given
    check(kind, spec)
    mine = own()
    name = cells.get("name") or old or f"Your {kind} {len(mine[kind]) + 1}"
    if name in PRESETS[kind]:
        name = f"{name} (yours)"
    mine[kind].pop(old, None)
    mine[kind][name] = spec
    file().write_text(json.dumps(mine, indent=2))


def check(kind: str, spec: dict) -> None:
    """A part the twin can run: positive numbers, and a rack of known CPUs and GPUs."""
    if any(spec[f] <= 0 for f in FIELDS[kind] if f not in ("cpu", "gpu", "gpus")):
        raise ValueError(f"{kind}: every number must be positive")
    if kind == "Rack" and (
        spec["cpu"] not in parts("CPU") or spec["gpu"] not in ["None", *parts("GPU")]
    ):
        raise ValueError(f"Rack: no CPU {spec['cpu']!r} or GPU {spec['gpu']!r} in the portfolio")


def remove(kind: str, name: str) -> None:
    """The user's own part removed; a preconfigured one stays."""
    mine = own()
    if mine[kind].pop(name, None) is not None:
        file().write_text(json.dumps(mine, indent=2))
