"""
Efficiency plot generation.

Creates a dense 3-panel plot:
1. Top: Power draw comparison (Ground Truth vs FootPrinter vs OpenDT)
2. Middle: Performance in FLOPs (integrated over 1-hour periods, 1 Hz = 1 FLOP)
3. Bottom: Efficiency in FLOPs/kWh

All panels share the x-axis with no vertical padding.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Use LaTeX-style fonts (Computer Modern)
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman", "DejaVu Serif", "Times New Roman"],
    "mathtext.fontset": "cm",
    "axes.formatter.use_mathtext": True,
})

from .config import CAPSULE_DATA_DIR, COLOR_PALETTE, METRIC_POWER, WORKLOAD_DIR
from .data_loader import get_workload_start_time
from .processors import process_flops_data

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# Font size constants
FONT_SIZE_AXIS_LABELS = 20      # Tick labels on axes (numbers)
FONT_SIZE_AXIS_DESCRIPTIONS = 20  # Axis titles ("Power", "Performance", etc.)
FONT_SIZE_LEGEND = 18           # Legend text

# Line styling constants
LINE_THICKNESS = 1.8            # Thickness of lines in subplot A

# Signal smoothing constant (running average window size in samples)
# Set to 1 to disable smoothing, higher values = more smoothing
SMOOTHING_WINDOW = 15


def generate_efficiency_plot(
    run_path: Path,
    output_path: Path,
    workload: str = "SURF",
) -> tuple[float, float, int]:
    """Generate efficiency plot with 3 panels: power, FLOPs, FLOPs/kWh.
    
    Args:
        run_path: Path to the experiment run directory
        output_path: Path to save the output PDF
        workload: Name of the workload (e.g., "SURF")
    
    Returns:
        Tuple of (avg_efficiency, max_efficiency, sample_count)
    """
    # Get base datetime for timestamp conversion
    base_dt = get_workload_start_time(run_path)
    
    # Load power data for all three sources (keep at raw resolution)
    fp_power, rw_power = _load_baseline_power(workload, base_dt)
    odt_power = _load_opendt_power(run_path)
    
    # Align power data at raw resolution (1-minute interpolation)
    raw_power_data = _align_power_data(fp_power, rw_power, odt_power)
    
    if len(raw_power_data) == 0:
        raise ValueError("No overlapping power data found")
    
    # Create hourly aggregates for FLOPs and efficiency
    hourly_data = _create_hourly_data(fp_power, rw_power, odt_power, base_dt)
    
    # Load and integrate MHz to FLOPs (1 Hz = 1 FLOP, so MHz * 1e6 * seconds = FLOPs)
    flops_data = _calculate_hourly_flops(run_path)
    
    # Merge hourly power and FLOPs data for efficiency calculation
    merged = pd.merge(
        hourly_data,
        flops_data,
        on="period_start",
        how="inner",
    )
    
    if len(merged) == 0:
        raise ValueError("No overlapping data after merge")
    
    # Calculate energy in kWh for each hour (power in W * 1 hour / 1000)
    merged["energy_kwh"] = merged["odt_power"] / 1000
    
    # Calculate efficiency: FLOPs / kWh
    merged["efficiency"] = merged["flops"] / merged["energy_kwh"]
    
    # Create dense 3-panel figure (NOT shared x-axis since different resolutions)
    # Height ratios: A=2, B=1, C=1 (B and C are 50% of A's height)
    fig, axes = plt.subplots(
        3, 1,
        figsize=(10, 8),
        gridspec_kw={"hspace": 0.2, "height_ratios": [2, 1, 1]},
    )
    
    # Panel 1: Power comparison at RAW resolution
    ax1 = axes[0]
    ax1.grid(True, alpha=0.3, zorder=0)
    x_power = np.arange(len(raw_power_data))
    
    # Apply running average smoothing if enabled
    def smooth(series):
        if SMOOTHING_WINDOW > 1:
            return series.rolling(window=SMOOTHING_WINDOW, center=True, min_periods=1).mean()
        return series
    
    rw_smoothed = smooth(raw_power_data["rw_power"] / 1000)
    fp_smoothed = smooth(raw_power_data["fp_power"] / 1000)
    odt_smoothed = smooth(raw_power_data["odt_power"] / 1000)
    
    ax1.plot(x_power, rw_smoothed, label="Ground Truth", color="#666666", lw=LINE_THICKNESS)  # Gray
    ax1.plot(x_power, fp_smoothed, label="FootPrinter", color=COLOR_PALETTE[1], lw=LINE_THICKNESS)
    ax1.plot(x_power, odt_smoothed, label="OpenDT", color=COLOR_PALETTE[2], lw=LINE_THICKNESS)
    ax1.set_ylabel("Power\ndraw\n[kW]", fontsize=FONT_SIZE_AXIS_DESCRIPTIONS, labelpad=10)
    ax1.tick_params(axis="y", labelsize=FONT_SIZE_AXIS_LABELS)
    ax1.tick_params(axis="x", labelbottom=False)
    ax1.legend(loc="lower right", fontsize=FONT_SIZE_LEGEND, framealpha=0.9, ncol=3)
    ax1.set_xlim(0, len(raw_power_data) - 1)
    ax1.set_ylim(0, 30)
    ax1.set_yticks([0, 16, 32])  # 3 ticks: min, mid, max
    
    # Panel 2: Performance (FLOPs) - bar chart at hourly resolution
    ax2 = axes[1]
    ax2.grid(True, alpha=0.3, zorder=0)
    x_hourly = np.arange(len(merged))
    flops_tera = merged["flops"] / 1e12
    ax2.bar(x_hourly, flops_tera, color="#7B2D8E", alpha=0.8, width=0.8)  # Purple
    ax2.set_ylabel("Perfor-\nmance\n[TFLOPs]", fontsize=FONT_SIZE_AXIS_DESCRIPTIONS, labelpad=10)
    ax2.tick_params(axis="y", labelsize=FONT_SIZE_AXIS_LABELS)
    ax2.tick_params(axis="x", labelbottom=False)
    ax2.set_xlim(-0.5, len(merged) - 0.5)
    ax2.set_ylim(0, 15000)
    ax2.set_yticks([0, 7500, 15000])  # 3 ticks: min, mid, max
    
    # Panel 3: Efficiency (FLOPs/kWh) - bar chart at hourly resolution
    ax3 = axes[2]
    ax3.grid(True, alpha=0.3, zorder=0)
    efficiency_tera = merged["efficiency"] / 1e12
    ax3.bar(x_hourly, efficiency_tera, color="#0072B2", alpha=0.8, width=0.8)  # Blue
    ax3.set_ylabel("Efficiency\n[TFLOPs\n/kWh]", fontsize=FONT_SIZE_AXIS_DESCRIPTIONS, labelpad=10)
    ax3.set_xlabel("Time [day/month]", fontsize=FONT_SIZE_AXIS_DESCRIPTIONS, labelpad=10)
    ax3.tick_params(axis="both", labelsize=FONT_SIZE_AXIS_LABELS)
    ax3.set_xlim(-0.5, len(merged) - 0.5)
    ax3.set_ylim(0, 600)
    ax3.set_yticks([0, 300, 600])  # 3 ticks: min, mid, max\n    
    # Format x-axis with date labels (on bottom panel only)
    _format_time_axis(ax3, merged["period_start"], len(merged))
    
    # Add panel labels (A, B, C) in white circles
    # A is positioned higher to avoid legend overlap
    label_positions = [(0.03, 0.27), (0.03, 0.15), (0.03, 0.15)]  # (x, y) for A, B, C
    for ax, label, (lx, ly) in zip(axes, ["A", "B", "C"], label_positions):
        ax.text(
            lx, ly,
            label,
            transform=ax.transAxes,
            fontsize=20,
            fontweight="bold",
            va="bottom",
            ha="left",
            bbox=dict(
                boxstyle="circle,pad=0.3",
                facecolor="white",
                edgecolor="black",
                linewidth=1.5,
            ),
        )
    
    # Align y-axis labels horizontally
    fig.align_ylabels(axes)
    
    plt.savefig(output_path, format="pdf", bbox_inches="tight", dpi=150)
    plt.close()
    
    # Return summary statistics (in TFLOPs/kWh)
    avg_efficiency = float(efficiency_tera.mean())
    max_efficiency = float(efficiency_tera.max())
    sample_count = len(merged)
    
    return avg_efficiency, max_efficiency, sample_count


def _load_baseline_power(
    workload: str,
    base_dt: pd.Timestamp,
) -> tuple[pd.Series, pd.Series]:
    """Load FootPrinter and real-world power data."""
    fp_path = CAPSULE_DATA_DIR / workload / "footprinter.parquet"
    rw_path = WORKLOAD_DIR / workload / "consumption.parquet"
    
    if not fp_path.exists():
        raise FileNotFoundError(f"FootPrinter data not found: {fp_path}")
    if not rw_path.exists():
        raise FileNotFoundError(f"Real world data not found: {rw_path}")
    
    # Load FootPrinter
    fp_df = pd.read_parquet(fp_path)
    if "timestamp_absolute" in fp_df.columns:
        fp_df["timestamp"] = pd.to_datetime(fp_df["timestamp_absolute"], unit="ms")
    else:
        fp_df["timestamp"] = base_dt + pd.to_timedelta(fp_df["timestamp"].values, unit="ms")
    fp_series = fp_df.groupby("timestamp")[METRIC_POWER].sum()
    
    # Load real world
    rw_df = pd.read_parquet(rw_path)
    if "timestamp_absolute" in rw_df.columns:
        rw_df["timestamp"] = pd.to_datetime(rw_df["timestamp_absolute"], unit="ms")
    else:
        rw_df["timestamp"] = base_dt + pd.to_timedelta(rw_df["timestamp"].values, unit="ms")
    rw_series = rw_df.groupby("timestamp")[METRIC_POWER].sum()
    
    return fp_series, rw_series


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


def _align_power_data(
    fp_power: pd.Series,
    rw_power: pd.Series,
    odt_power: pd.Series,
) -> pd.DataFrame:
    """Align power data at 1-minute resolution without aggregation.
    
    Interpolates all series to 1-minute intervals and aligns them.
    """
    # Resample to 1-minute and interpolate
    fp_1min = fp_power.resample("1min").mean().interpolate(method="linear")
    rw_1min = rw_power.resample("1min").mean().interpolate(method="linear")
    odt_1min = odt_power.resample("1min").mean().interpolate(method="linear")
    
    # Create combined dataframe and drop any NaN
    combined = pd.DataFrame({
        "fp_power": fp_1min,
        "rw_power": rw_1min,
        "odt_power": odt_1min,
    }).dropna()
    
    combined = combined.reset_index()
    combined = combined.rename(columns={"timestamp": "datetime"})
    
    return combined


def _create_hourly_data(
    fp_power: pd.Series,
    rw_power: pd.Series,
    odt_power: pd.Series,
    base_dt: pd.Timestamp,
) -> pd.DataFrame:
    """Resample all power series to 1-hour averages and align."""
    # Resample to hourly
    fp_hourly = fp_power.resample("1h").mean()
    rw_hourly = rw_power.resample("1h").mean()
    odt_hourly = odt_power.resample("1h").mean()
    
    # Create combined dataframe
    combined = pd.DataFrame({
        "fp_power": fp_hourly,
        "rw_power": rw_hourly,
        "odt_power": odt_hourly,
    }).dropna()
    
    combined = combined.reset_index()
    combined = combined.rename(columns={"timestamp": "period_start"})
    
    return combined


def _calculate_hourly_flops(run_path: Path) -> pd.DataFrame:
    """Calculate FLOPs per hour from MHz data.
    
    Since 1 Hz = 1 FLOP, we integrate MHz over each hour:
    FLOPs = MHz * 1e6 * seconds_in_hour = MHz * 1e6 * 3600
    """
    # Get fine-grained MHz data
    mhz_df = process_flops_data(run_path)
    
    if len(mhz_df) == 0:
        return pd.DataFrame(columns=["period_start", "flops"])
    
    # Set datetime as index for resampling
    mhz_df = mhz_df.set_index("datetime")
    
    # Resample to hourly and calculate average MHz
    hourly_mhz = mhz_df["total_mhz"].resample("1h").mean()
    
    # Convert average MHz to FLOPs for the hour
    # FLOPs = avg_MHz * 1e6 (to Hz) * 3600 (seconds per hour)
    hourly_flops = hourly_mhz * 1e6 * 3600
    
    result = pd.DataFrame({
        "period_start": hourly_flops.index,
        "flops": hourly_flops.values,
    })
    
    return result


def _format_time_axis(ax: Axes, timestamps: pd.Series, plot_len: int) -> None:
    """Format the x-axis with date labels, excluding first and last."""
    timestamps = pd.to_datetime(timestamps)
    
    if plot_len <= 24:
        step = max(1, plot_len // 8)
    else:
        step = max(1, plot_len // 7)
    
    tick_positions = list(range(0, plot_len, step))
    tick_labels = [timestamps.iloc[i].strftime("%d/%m") for i in tick_positions]
    
    # Hide first label (keep ticks but blank labels)
    if len(tick_labels) >= 1:
        tick_labels[0] = ""
    
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=FONT_SIZE_AXIS_LABELS)
