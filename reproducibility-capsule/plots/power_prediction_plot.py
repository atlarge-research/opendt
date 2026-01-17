"""
Energy/power consumption plot generation.

Refactored from the original generate_plot.py to be a reusable module.
Generates plots comparing Ground Truth, FootPrinter, and OpenDT power predictions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from .config import (
    CAPSULE_DATA_DIR,
    METRIC_POWER,
    POWER_FOOTPRINTER,
    POWER_GROUND_TRUTH,
    POWER_MAPE,
    POWER_OPENDT,
    WORKLOAD_DIR,
)
from .data_loader import get_workload_start_time

if TYPE_CHECKING:
    from matplotlib.axes import Axes


def load_baseline_data(
    workload: str,
    base_dt: pd.Timestamp,
) -> tuple[pd.Series, pd.Series]:  # type: ignore[type-arg]
    """Load FootPrinter and real world consumption data.

    FootPrinter data is loaded from reproducibility-capsule/data/<workload>/.
    Real world data is loaded from workload/<workload>/consumption.parquet.

    Args:
        workload: Name of the workload (e.g., "SURF")
        base_dt: Base datetime for converting relative timestamps to absolute

    Returns:
        Tuple of (footprinter_series, real_world_series)
    
    Raises:
        FileNotFoundError: If required data files are not found.
    """
    fp_data_dir = CAPSULE_DATA_DIR / workload
    fp_path = fp_data_dir / "footprinter.parquet"
    rw_path = WORKLOAD_DIR / workload / "consumption.parquet"

    if not fp_path.exists():
        raise FileNotFoundError(f"FootPrinter data not found: {fp_path}")

    if not rw_path.exists():
        raise FileNotFoundError(f"Real world consumption data not found: {rw_path}")

    # Load FootPrinter data
    fp_df = pd.read_parquet(fp_path)

    # Handle timestamp conversion for footprinter
    if "timestamp_absolute" in fp_df.columns:
        fp_df["timestamp"] = pd.to_datetime(fp_df["timestamp_absolute"], unit="ms")
    else:
        fp_df["timestamp"] = base_dt + pd.to_timedelta(fp_df["timestamp"].values, unit="ms")

    fp_series: pd.Series = fp_df.groupby("timestamp")[METRIC_POWER].sum()  # type: ignore[type-arg, assignment]

    # Load real world consumption data
    rw_df = pd.read_parquet(rw_path)

    # Handle timestamp conversion for real world
    if "timestamp_absolute" in rw_df.columns:
        rw_df["timestamp"] = pd.to_datetime(rw_df["timestamp_absolute"], unit="ms")
    else:
        rw_df["timestamp"] = base_dt + pd.to_timedelta(rw_df["timestamp"].values, unit="ms")

    rw_series: pd.Series = rw_df.groupby("timestamp")[METRIC_POWER].sum()  # type: ignore[type-arg, assignment]

    return fp_series, rw_series


def load_opendt_results(run_path: Path) -> pd.Series:  # type: ignore[type-arg]
    """Load OpenDT simulation results.

    For both experiments, we use the simulator's aggregated results.
    The difference is:
    - Experiment 1: Simulator runs without calibration
    - Experiment 2: Simulator runs with calibration (receives calibrated topology)
    
    Args:
        run_path: Path to the experiment run directory
    
    Returns:
        Series of power draw values indexed by timestamp
    
    Raises:
        FileNotFoundError: If results file not found.
    """
    results_path = run_path / "simulator" / "agg_results.parquet"

    if not results_path.exists():
        raise FileNotFoundError(f"OpenDT results not found: {results_path}")

    df = pd.read_parquet(results_path)

    # Handle timestamp conversion
    if "timestamp_absolute" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp_absolute"], unit="ms", utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

    result: pd.Series = df.groupby("timestamp")[METRIC_POWER].sum()  # type: ignore[type-arg, assignment]
    return result


def interpolate_to_1min(series: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    """Interpolate power data to 1-minute intervals."""
    if len(series) < 2:
        return series

    series = series.sort_index()
    result: pd.Series = series.resample("1min").mean().interpolate(method="linear")  # type: ignore[type-arg, assignment]
    return result


def average_to_5min(series: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    """Average 1-min data to 5-min intervals."""
    result: pd.Series = series.groupby(np.arange(len(series)) // 5).mean()  # type: ignore[type-arg, assignment]
    return result


def calculate_mape(ground_truth: pd.Series, simulation: pd.Series) -> float:  # type: ignore[type-arg]
    """Calculate Mean Absolute Percentage Error (MAPE)."""
    r: np.ndarray = np.asarray(ground_truth.values)  # type: ignore[type-arg]
    s: np.ndarray = np.asarray(simulation.values)  # type: ignore[type-arg]
    # Avoid division by zero
    mask = r != 0
    return float(np.mean(np.abs((r[mask] - s[mask]) / r[mask])) * 100)


def calculate_pointwise_mape(ground_truth: np.ndarray, simulation: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
    """Calculate point-wise absolute percentage error."""
    # Avoid division by zero
    with np.errstate(divide="ignore", invalid="ignore"):
        ape = np.abs((ground_truth - simulation) / ground_truth) * 100
        ape = np.nan_to_num(ape, nan=0.0, posinf=0.0, neginf=0.0)
    return ape


def generate_energy_plot(
    run_path: Path,
    workload: str,
    output_path: Path,
) -> tuple[float, float, int]:
    """Generate experiment plot with Ground Truth, FootPrinter, OpenDT, and MAPE.

    Args:
        run_path: Path to the experiment run directory
        workload: Name of the workload (e.g., "SURF")
        output_path: Path to save the output PDF

    Returns:
        Tuple of (footprinter_mape, opendt_mape, sample_count)
    """
    # Get base datetime from run metadata (not hardcoded)
    base_dt = get_workload_start_time(run_path)
    
    # Load baseline data (FootPrinter and Real World)
    fp, rw = load_baseline_data(workload, base_dt)
    odt = load_opendt_results(run_path)

    # Interpolate to 1-minute
    rw_1min = interpolate_to_1min(rw)
    fp_1min = interpolate_to_1min(fp)
    odt_1min = interpolate_to_1min(odt)

    # Find common time range across all three
    common_start = max(rw_1min.index[0], fp_1min.index[0], odt_1min.index[0])
    common_end = min(rw_1min.index[-1], fp_1min.index[-1], odt_1min.index[-1])

    # Slice to common range
    rw_1min = rw_1min[common_start:common_end]
    fp_1min = fp_1min[common_start:common_end]
    odt_1min = odt_1min[common_start:common_end]

    # Calculate MAPE on 1-minute data
    mape_fp = calculate_mape(rw_1min, fp_1min)  # type: ignore[arg-type]
    mape_odt = calculate_mape(rw_1min, odt_1min)  # type: ignore[arg-type]

    # Calculate point-wise MAPE for OpenDT (for the MAPE line)
    rw_vals = np.asarray(rw_1min.values)  # type: ignore[union-attr]
    odt_vals = np.asarray(odt_1min.values)  # type: ignore[union-attr]
    pointwise_mape = calculate_pointwise_mape(rw_vals, odt_vals)

    # Calculate cumulative MAPE
    cumulative_mape = pd.Series(pointwise_mape).expanding().mean()

    # Average to 5-minute for plotting
    rw_5min = average_to_5min(rw_1min)  # type: ignore[arg-type]
    fp_5min = average_to_5min(fp_1min)  # type: ignore[arg-type]
    odt_5min = average_to_5min(odt_1min)  # type: ignore[arg-type]

    # Downsample MAPE to 5-minute
    plot_len = len(rw_5min)
    cumulative_mape_arr = np.asarray(cumulative_mape.values)  # type: ignore[union-attr]
    cumulative_mape_5min = cumulative_mape_arr[::5][:plot_len]

    # Create timestamps for plot
    timestamps = pd.date_range(start=common_start, periods=plot_len, freq="5min")
    rw_5min.index = timestamps
    fp_5min.index = timestamps
    odt_5min.index = timestamps

    # Generate plot
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.grid(True, alpha=0.3)

    x = np.arange(plot_len)

    # Plot power lines on primary y-axis (thinner lines: lw=1.5)
    rw_values = np.asarray(rw_5min.values) / 1000
    fp_values = np.asarray(fp_5min.values) / 1000
    odt_values = np.asarray(odt_5min.values) / 1000

    line1 = ax1.plot(x, rw_values, label="Ground Truth", color=POWER_GROUND_TRUTH, lw=1.5)
    line2 = ax1.plot(x, fp_values, label="FootPrinter", color=POWER_FOOTPRINTER, lw=1.5)
    line3 = ax1.plot(x, odt_values, label="OpenDT", color=POWER_OPENDT, lw=1.5)

    # Create secondary y-axis for MAPE
    ax2 = ax1.twinx()

    # Plot MAPE line (cumulative average)
    line4 = ax2.plot(
        x,
        cumulative_mape_5min,
        label="MAPE (OpenDT)",
        color=POWER_MAPE,
        lw=1.5,
        linestyle="--",
        alpha=0.8,
    )

    # Format X-axis
    _format_time_axis(ax1, timestamps, plot_len)

    # Format primary Y-axis (Power)
    y_formatter = FuncFormatter(lambda val, _: f"{int(val):,}")
    ax1.yaxis.set_major_formatter(y_formatter)
    ax1.tick_params(axis="y", labelsize=20)
    ax1.set_ylabel("Power Draw [kW]", fontsize=22, labelpad=10)
    ax1.set_xlabel("Time [day/month]", fontsize=22, labelpad=10)
    ax1.set_ylim(0, 32)

    # Format secondary Y-axis (MAPE)
    ax2.set_ylabel("MAPE [%]", fontsize=22, labelpad=10)
    ax2.set_ylim(0, 10)
    ax2.tick_params(axis="y", labelsize=20)

    # Combined legend - position it with more space from the plot
    lines = line1 + line2 + line3 + line4
    labels = [str(line.get_label()) for line in lines]
    ax1.legend(
        lines,
        labels,
        fontsize=20,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.24),
        ncol=4,
        framealpha=1,
    )

    plt.tight_layout()
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close()

    return mape_fp, mape_odt, len(rw_1min)


def _format_time_axis(ax: Axes, timestamps: pd.DatetimeIndex, plot_len: int) -> None:
    """Format the x-axis with date labels."""
    target_dates = ["2022-10-08", "2022-10-10", "2022-10-12", "2022-10-14"]
    tick_dates = pd.to_datetime(target_dates)

    tick_positions = []
    tick_labels = []

    for d in tick_dates:
        seconds_diff = (d - timestamps[0]).total_seconds()
        idx = int(seconds_diff / 300)  # 300 seconds = 5 minutes

        if 0 <= idx < plot_len:
            tick_positions.append(idx)
            tick_labels.append(d.strftime("%d/%m"))

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=20)

    # Extend limit slightly to show last tick
    if tick_positions:
        max_tick = max(tick_positions)
        if ax.get_xlim()[1] < max_tick:
            ax.set_xlim(right=max_tick + (plot_len * 0.02))
