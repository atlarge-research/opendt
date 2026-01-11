"""
Shared configuration and constants for plot generation.
"""

from __future__ import annotations

from pathlib import Path

# --- Directory Paths ---
CAPSULE_DIR = Path(__file__).parent.parent
REPO_ROOT = CAPSULE_DIR.parent
DATA_DIR = REPO_ROOT / "data"
WORKLOAD_DIR = REPO_ROOT / "workload"
CAPSULE_DATA_DIR = CAPSULE_DIR / "data"
OUTPUT_DIR = CAPSULE_DIR / "output"

# --- Color Palette ---
COLOR_PALETTE = [
    "#0072B2",  # Blue (Ground Truth / CPU Utilization)
    "#E69F00",  # Orange (FootPrinter / Latency)
    "#009E73",  # Green (OpenDT)
    "#D55E00",  # Red-orange (MAPE rolling)
    "#CC79A7",  # Pink (MAPE cumulative)
]

# --- Reference Time ---
REFERENCE_START_TIME_STR = "2022-10-06 22:00:00"

# --- Metrics ---
METRIC_POWER = "power_draw"
