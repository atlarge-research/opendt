"""Helpers for the OpenDT tutorial notebooks.

They run OpenDT's own simulation engine (the bundled OpenDC simulator, driven through
OpenDT's `odt_common` models) on the SURF workload trace, so every number in the
notebooks comes from the same machinery as the live digital twin.
"""

from .data import (
    CARBON_ZONES,
    TRACE_END,
    TRACE_START,
    Surf,
    carbon_intensity,
    carbon_trace_path,
    load_surf,
    measured_power,
)
from .paths import PATHS, SetupError, check_setup, repo_root
from .sim import SimResult, simulate, write_inputs
from .topology import make_topology

__all__ = [
    "CARBON_ZONES",
    "PATHS",
    "TRACE_END",
    "TRACE_START",
    "SetupError",
    "SimResult",
    "Surf",
    "carbon_intensity",
    "carbon_trace_path",
    "check_setup",
    "load_surf",
    "make_topology",
    "measured_power",
    "repo_root",
    "simulate",
    "write_inputs",
]
