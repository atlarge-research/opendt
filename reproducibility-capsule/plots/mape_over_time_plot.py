"""
MAPE Over Time plot generation for Experiment 2.

Compares power prediction accuracy between calibrated and non-calibrated OpenDT runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# Use LaTeX-style fonts (Computer Modern)
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman", "DejaVu Serif", "Times New Roman"],
    "mathtext.fontset": "cm",
    "axes.formatter.use_mathtext": True,
})

from .config import (
    MAPE_CALIBRATED,
    MAPE_FOOTPRINTER,
    MAPE_NFR_THRESHOLD,
    MAPE_NON_CALIBRATED,
    METRIC_POWER,
    WORKLOAD_DIR,
)
from .data_loader import get_workload_start_time

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# --- Constants ---
ROLLING_WINDOW = 12  # Rolling average window for MAPE smoothing
FOOTPRINTER_MAPE = 7.86  # Reference MAPE for FootPrinter baseline
NFR_THRESHOLD = 10.0  # Non-functional requirement threshold

# Font size constants (aligned with sustainability_overview_plot.py)
FONT_SIZE_AXIS_LABELS = 20      # Tick labels on axes (numbers)
FONT_SIZE_AXIS_DESCRIPTIONS = 20  # Axis titles ("MAPE", "Time", etc.)
FONT_SIZE_LEGEND = 18           # Legend text

# Line styling constant
LINE_THICKNESS = 1.8            # Thickness of main plot lines


def generate_mape_over_time_plot(
    calibrated_run_path: Path,
    non_calibrated_run_path: Path,
    output_path: Path,
    workload: str = "SURF",
    include_article_markers: bool = False,
) -> tuple[float, float, int]:
    """Generate MAPE over time comparison plot.
    
    Compares calibrated vs non-calibrated OpenDT power predictions against
    real-world (ground truth) data.
    
    Args:
        calibrated_run_path: Path to calibrated experiment run directory
        non_calibrated_run_path: Path to non-calibrated experiment run directory
        output_path: Path to save the output PDF
        workload: Name of the workload (e.g., "SURF")
        include_article_markers: If True, add hardcoded date markers for article figure
    
    Returns:
        Tuple of (avg_mape_calibrated, avg_mape_non_calibrated, sample_count)
    """
    # Load power data from both runs
    df_c = _load_opendt_power(calibrated_run_path)
    df_nc = _load_opendt_power(non_calibrated_run_path)
    df_rw = _load_real_world_power(workload)
    
    if len(df_c) == 0 or len(df_nc) == 0 or len(df_rw) == 0:
        raise ValueError("One or more data sources are empty")
    
    # Downsample to align data (real-world is often at higher frequency)
    df_rw_ds = df_rw.groupby(np.arange(len(df_rw)) // 10).mean()
    df_nc_ds = df_nc.groupby(np.arange(len(df_nc)) // 2).mean()
    df_c_ds = df_c.groupby(np.arange(len(df_c)) // 2).mean()
    
    # Trim to shortest common length
    min_len = min(len(df_nc_ds), len(df_c_ds), len(df_rw_ds))
    df_nc_ds = df_nc_ds.iloc[:min_len]
    df_c_ds = df_c_ds.iloc[:min_len]
    df_rw_ds = df_rw_ds.iloc[:min_len]
    
    if min_len == 0:
        raise ValueError("No overlapping data after alignment")
    
    # Find optimal lag shift
    best_shift = _find_optimal_shift(df_c_ds, df_rw_ds)
    
    # Apply shift
    df_nc_shifted = df_nc_ds.shift(best_shift)
    df_c_shifted = df_c_ds.shift(best_shift)
    
    # Get actual workload start time from non-calibrated run (same source as sustainability plot)
    start_time = get_workload_start_time(non_calibrated_run_path)
    timestamps = pd.date_range(start=start_time, periods=min_len, freq="5min")
    
    # Create plotting DataFrame
    plot_df = pd.DataFrame({
        "Real": df_rw_ds.values,
        "NoCalib": df_nc_shifted.values,
        "Calib": df_c_shifted.values
    }, index=timestamps).dropna()
    
    # Calculate bias masks (overestimation = model > real)
    bias_nc_mask = plot_df["NoCalib"] > plot_df["Real"]
    bias_c_mask = plot_df["Calib"] > plot_df["Real"]
    
    # Calculate rolling MAPE
    ape_nc = np.abs((plot_df["Real"] - plot_df["NoCalib"]) / plot_df["Real"]) * 100
    ape_c = np.abs((plot_df["Real"] - plot_df["Calib"]) / plot_df["Real"]) * 100
    
    smooth_mape_nc = ape_nc.rolling(ROLLING_WINDOW).mean().dropna()
    smooth_mape_c = ape_c.rolling(ROLLING_WINDOW).mean().dropna()
    
    # Generate plot
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # --- Overestimation/Underestimation indicator bars at top ---
    y_top = 17.5
    strip_height = 0.7
    y_nc_bottom = y_top - strip_height  # Top strip for No Calibration
    y_c_bottom = y_nc_bottom - strip_height  # Bottom strip for Calibrated
    
    # No Calibration strip (purple) - dark = overestimating, light = underestimating
    ax.fill_between(plot_df.index, y_nc_bottom, y_top, where=bias_nc_mask,
                    color=MAPE_NON_CALIBRATED, alpha=1.0, linewidth=0, step='mid', zorder=1)
    ax.fill_between(plot_df.index, y_nc_bottom, y_top, where=~bias_nc_mask,
                    color=MAPE_NON_CALIBRATED, alpha=0.4, linewidth=0, step='mid', zorder=1)
    
    # Calibrated strip (green) - dark = overestimating, light = underestimating
    ax.fill_between(plot_df.index, y_c_bottom, y_nc_bottom, where=bias_c_mask,
                    color=MAPE_CALIBRATED, alpha=1.0, linewidth=0, step='mid', zorder=1)
    ax.fill_between(plot_df.index, y_c_bottom, y_nc_bottom, where=~bias_c_mask,
                    color=MAPE_CALIBRATED, alpha=0.4, linewidth=0, step='mid', zorder=1)
    
    # White separator between strips
    ax.axhline(y=y_nc_bottom, color='white', linewidth=1, zorder=2)
    
    # --- Optional article-style date markers ---
    if include_article_markers:
        # Grey box around 09/10 (performance is roughly equal)
        date_9_10 = pd.Timestamp("2022-10-09 00:00:00")
        ax.axvspan(date_9_10 - pd.Timedelta(hours=5), date_9_10 + pd.Timedelta(hours=3),
                   ymin=0, ymax=0.05, facecolor='darkgrey', alpha=1.0, zorder=3)
        
        # Black box around 11/10 (non-calibrated performs better)
        date_11_10 = pd.Timestamp("2022-10-11 05:00:00")
        ax.axvspan(date_11_10 - pd.Timedelta(hours=6), date_11_10 + pd.Timedelta(hours=6),
                   ymin=0, ymax=0.05, facecolor='black', alpha=0.9, zorder=3)
    
    # Grid
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Main plot lines
    ax.plot(smooth_mape_nc.index, smooth_mape_nc, 
            label="No Calibration", color=MAPE_NON_CALIBRATED, lw=LINE_THICKNESS, linestyle="--", zorder=4)
    ax.plot(smooth_mape_c.index, smooth_mape_c, 
            label="With Calibration", color=MAPE_CALIBRATED, lw=LINE_THICKNESS, zorder=4)
    
    # Threshold lines (above plot lines)
    ax.axhline(y=NFR_THRESHOLD, color=MAPE_NFR_THRESHOLD, linestyle=':', linewidth=LINE_THICKNESS, alpha=0.8, zorder=5)
    ax.axhline(y=FOOTPRINTER_MAPE, color=MAPE_FOOTPRINTER, linestyle='-.', linewidth=LINE_THICKNESS, alpha=0.8, zorder=5)
    
    # Labels on graph (above the lines)
    if len(smooth_mape_nc) > 0:
        ax.text(smooth_mape_nc.index[0], NFR_THRESHOLD + 0.5, 
                f"      NFR Threshold ({NFR_THRESHOLD:.0f}%)",
                color=MAPE_NFR_THRESHOLD, fontsize=FONT_SIZE_LEGEND, fontweight='bold', va='bottom')
        ax.text(smooth_mape_nc.index[0], FOOTPRINTER_MAPE + 0.5, 
                f"      FootPrinter ({FOOTPRINTER_MAPE}%)",
                color=MAPE_FOOTPRINTER, fontsize=FONT_SIZE_LEGEND, fontweight='bold', va='bottom')
    
    # Formatting
    ax.set_ylabel("MAPE [%]", fontsize=FONT_SIZE_AXIS_DESCRIPTIONS)
    ax.set_xlabel("Time [day/month]", fontsize=FONT_SIZE_AXIS_DESCRIPTIONS)
    ax.set_ylim(0, y_top)
    ax.set_yticks([0, 5, 10, 15])
    ax.set_xlim(plot_df.index[0], plot_df.index[-1])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 0.92), ncol=2, framealpha=0.95, fontsize=FONT_SIZE_LEGEND)
    ax.tick_params(axis='both', labelsize=FONT_SIZE_AXIS_LABELS)
    
    # Date formatting - 1 tick per day (aligned with sustainability plot)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    
    # Hide first x-axis label (keep tick but blank label)
    # Get current tick labels and blank the first one
    fig.canvas.draw()  # Force render to get tick labels
    labels = [item.get_text() for item in ax.get_xticklabels()]
    if len(labels) > 0:
        labels[0] = ""
        ax.set_xticklabels(labels)
    
    plt.subplots_adjust(top=0.95, bottom=0.15)
    plt.savefig(output_path, format="pdf", bbox_inches="tight", dpi=150)
    plt.close()
    
    # Return statistics
    avg_mape_c = float(smooth_mape_c.mean())
    avg_mape_nc = float(smooth_mape_nc.mean())
    sample_count = len(plot_df)
    
    return avg_mape_c, avg_mape_nc, sample_count


def _load_opendt_power(run_path: Path) -> pd.Series:
    """Load OpenDT power data from aggregated results."""
    results_path = run_path / "simulator" / "agg_results.parquet"
    
    if not results_path.exists():
        raise FileNotFoundError(f"OpenDT results not found: {results_path}")
    
    df = pd.read_parquet(results_path)
    
    if "timestamp_absolute" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp_absolute"], unit="ms", utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    
    return df.groupby("timestamp")[METRIC_POWER].sum()


def _load_real_world_power(workload: str) -> pd.Series:
    """Load real-world power consumption data."""
    rw_path = WORKLOAD_DIR / workload / "consumption.parquet"
    
    if not rw_path.exists():
        raise FileNotFoundError(f"Real world data not found: {rw_path}")
    
    df = pd.read_parquet(rw_path)
    
    if "timestamp_absolute" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp_absolute"], unit="ms")
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    
    return df.groupby("timestamp")[METRIC_POWER].sum()


def _find_optimal_shift(sim_data: pd.Series, real_data: pd.Series) -> int:
    """Find optimal time shift to minimize MAPE.
    
    Searches +/- 12 steps (approximately +/- 1 hour at 5-min resolution).
    """
    best_shift = 0
    best_mape = 100.0
    
    for shift in range(-12, 13):
        sim_shifted = sim_data.shift(shift).dropna()
        rw_aligned = real_data.loc[sim_shifted.index]
        
        mask = rw_aligned != 0
        if mask.sum() == 0:
            continue
            
        mape = np.mean(np.abs((rw_aligned[mask] - sim_shifted[mask]) / rw_aligned[mask])) * 100
        
        if mape < best_mape:
            best_mape = mape
            best_shift = shift
    
    return best_shift
