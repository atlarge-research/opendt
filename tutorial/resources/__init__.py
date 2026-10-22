"""Helpers for the OpenDT tutorial notebooks.

They run OpenDT's own simulation engine (the bundled OpenDC simulator, driven through
OpenDT's `odt_common` models) on the SURF workload trace, so every number in the
notebooks comes from the same machinery as the live digital twin.
"""

from .calibration import compare_frequencies, compare_grids
from .data import (
    CARBON_ZONES,
    GREENEST_ZONE,
    TRACE_END,
    TRACE_START,
    carbon_intensity,
    carbon_trace_path,
    load_surf,
    measured_power,
)
from .metrics import align, mape
from .paths import PATHS, check_setup, repo_root
from .plots import legend_above, plot_electricity_mix, plot_power
from .questions import ask_question
from .sim import SimResult, default_workers, simulate, simulate_many, write_inputs
from .topology import make_topology

__all__ = [
    "CARBON_ZONES",
    "GREENEST_ZONE",
    "PATHS",
    "TRACE_END",
    "TRACE_START",
    "SimResult",
    "align",
    "ask_question",
    "carbon_intensity",
    "carbon_trace_path",
    "check_setup",
    "compare_frequencies",
    "compare_grids",
    "legend_above",
    "default_workers",
    "load_surf",
    "make_topology",
    "mape",
    "measured_power",
    "plot_electricity_mix",
    "plot_power",
    "repo_root",
    "simulate",
    "simulate_many",
    "write_inputs",
]
