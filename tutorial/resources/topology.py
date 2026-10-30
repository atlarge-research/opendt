"""The simulated datacenter: OpenDT's SURF topology with the knobs the notebooks turn."""

from __future__ import annotations

import json

from odt_common.models import Topology

from .data import carbon_trace_path
from .paths import PATHS


def make_topology(
    hosts: int = 277,
    r: float = 4.0,
    idle_power: float = 25.0,
    max_power: float = 174.0,
    carbon: str | None = None,
) -> Topology:
    """SURF's cluster (`workload/SURF/topology.json`) with a chosen size, power model and grid.

    hosts       number of identical hosts (16 cores at 2.1 GHz each)
    r           exponent of OpenDC's power model P(u) = P_idle + (P_max - P_idle)(2u - u^r)
    idle_power  watts a host draws when idle; max_power: watts at full load
    carbon      None = workload/SURF/carbon.parquet (the live twin starts on NL), or a zone from CARBON_ZONES
    """
    # pydantic would also reject these, but with less readable messages
    if hosts < 1:
        raise ValueError(f"hosts must be at least 1 (got {hosts}).")
    if not 0 <= r <= 50:
        raise ValueError(f"r (calibrationFactor) must be between 0 and 50 (got {r}).")
    if not 0 <= idle_power < max_power:
        raise ValueError(
            f"Need 0 <= idle_power < max_power (got idle_power={idle_power}, max_power={max_power})."
        )

    spec = json.loads((PATHS.workload / "topology.json").read_text())
    cluster = spec["clusters"][0]
    host = cluster["hosts"][0]
    host["count"] = hosts
    host["cpuPowerModel"].update(calibrationFactor=r, idlePower=idle_power, maxPower=max_power)
    cluster["powerSource"] = {"carbonTracePath": str(carbon_trace_path(carbon))}
    return Topology(**spec)
