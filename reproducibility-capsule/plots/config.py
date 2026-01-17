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

# =============================================================================
# COLOR CONSTANTS (grouped by plot)
# =============================================================================

# -----------------------------------------------------------------------------
# Power Prediction Plot (power_prediction_plot.py)
# -----------------------------------------------------------------------------
POWER_GROUND_TRUTH =    "#999999"     # Light Gray (real-world power)
POWER_FOOTPRINTER =     "#E69F00"     # Orange (FootPrinter baseline)
POWER_OPENDT =          "#009E73"     # Green (OpenDT prediction)
POWER_MAPE =            "#D55E00"     # Red-orange (MAPE cumulative line)

# -----------------------------------------------------------------------------
# Sustainability Overview Plot (sustainability_overview_plot.py)
# -----------------------------------------------------------------------------
SUST_GROUND_TRUTH =     "#999999"     # Light Gray (real-world power)
SUST_FOOTPRINTER =      "#E69F00"     # Orange (FootPrinter baseline)
SUST_OPENDT =           "#009E73"     # Green (OpenDT prediction)
SUST_PERFORMANCE =      "#9557a5"     # Purple (performance bars)
SUST_EFFICIENCY =       "#338ec1"     # Blue (efficiency bars)

# -----------------------------------------------------------------------------
# MAPE Over Time Plot (mape_over_time_plot.py)
# -----------------------------------------------------------------------------
MAPE_CALIBRATED =       "#009E73"     # Green (OpenDT with calibration)
MAPE_NON_CALIBRATED =   "#E69F00"     # Orange (OpenDT without calibration)
MAPE_FOOTPRINTER =      "#338ec1"     # Blue (FootPrinter baseline threshold)
MAPE_NFR_THRESHOLD =    "red"         # Red (NFR threshold line)

# --- Metrics ---
METRIC_POWER =          "power_draw"
