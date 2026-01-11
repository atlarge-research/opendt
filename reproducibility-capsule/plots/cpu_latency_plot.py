"""
CPU utilization and latency dual-axis plot generation.

Creates a plot matching the reference style with:
- Blue line: Average CPU Utilization [%] (left y-axis)
- Orange dashed line: Latency [h] (right y-axis)
- X-axis: Time [day/month]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from .processors import process_cpu_latency_data

# Dedicated colors for this plot (high contrast)
COLOR_CPU = "#0072B2"      # Deep blue for CPU utilization
COLOR_LATENCY = "#D55E00"  # Dark orange/red for Latency (more visible than yellow)

if TYPE_CHECKING:
    from matplotlib.axes import Axes


def generate_cpu_latency_plot(
    run_path: Path,
    output_path: Path,
) -> tuple[float, float, int]:
    """Generate CPU utilization and latency dual-axis plot.
    
    Args:
        run_path: Path to the experiment run directory
        output_path: Path to save the output PDF
    
    Returns:
        Tuple of (avg_cpu, avg_latency, sample_count)
    """
    # Process data from all runs
    df = process_cpu_latency_data(run_path)
    
    if len(df) == 0:
        raise ValueError("No data found to plot")
    
    # Sort by datetime for proper plotting
    df = df.sort_values("datetime")
    
    # Create figure with dual y-axes
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.grid(True, alpha=0.3)
    
    x = np.arange(len(df))
    
    # Plot CPU utilization on primary y-axis (blue solid line)
    line1 = ax1.plot(
        x,
        df["avg_cpu_utilization"].values,
        label="Avg CPU Utilization",
        color=COLOR_CPU,
        lw=1.5,
    )
    
    # Create secondary y-axis for latency
    ax2 = ax1.twinx()
    
    # Plot latency on secondary y-axis (orange dashed line)
    line2 = ax2.plot(
        x,
        df["latency_hours"].values,
        label="Latency [h]",
        color=COLOR_LATENCY,
        lw=1.5,
        linestyle="--",
        alpha=0.8,
    )
    
    # Format X-axis with date labels
    _format_time_axis(ax1, df["datetime"], len(df))
    
    # Format primary Y-axis (CPU Utilization)
    ax1.set_ylabel("Average CPU Utilization [%]", fontsize=22, color=COLOR_CPU, labelpad=10)
    ax1.tick_params(axis="y", labelsize=20, colors=COLOR_CPU)
    ax1.set_ylim(0, 100)
    ax1.set_xlabel("Time [day/month]", fontsize=22, labelpad=10)
    
    # Format secondary Y-axis (Latency)
    ax2.set_ylabel("Latency [h]", fontsize=22, color=COLOR_LATENCY, labelpad=10)
    ax2.tick_params(axis="y", labelsize=20, colors=COLOR_LATENCY)
    
    # Set latency y-axis limits based on data
    max_latency = df["latency_hours"].max()
    ax2.set_ylim(0, max(max_latency * 1.1, 200))
    
    # Combined legend
    lines = line1 + line2
    labels = [str(line.get_label()) for line in lines]
    ax1.legend(
        lines,
        labels,
        fontsize=20,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.20),
        ncol=2,
        framealpha=1,
    )
    
    plt.tight_layout()
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close()
    
    # Calculate summary statistics
    avg_cpu = float(df["avg_cpu_utilization"].mean())
    avg_latency = float(df["latency_hours"].mean())
    sample_count = len(df)
    
    return avg_cpu, avg_latency, sample_count


def _format_time_axis(ax: Axes, timestamps: pd.Series, plot_len: int) -> None:
    """Format the x-axis with date labels.
    
    Args:
        ax: The matplotlib axes to format
        timestamps: Series of datetime values
        plot_len: Number of data points
    """
    timestamps = pd.to_datetime(timestamps)
    
    # Get unique dates for tick labels
    # We want to show approximately 4-6 date labels
    if plot_len <= 6:
        # Show all dates if few points
        tick_positions = list(range(plot_len))
        tick_labels = [ts.strftime("%d/%m") for ts in timestamps]
    else:
        # Sample dates evenly
        step = max(1, plot_len // 5)
        tick_positions = list(range(0, plot_len, step))
        tick_labels = [timestamps.iloc[i].strftime("%d/%m") for i in tick_positions]
    
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=20)
    
    # Ensure x-axis covers all data
    ax.set_xlim(-0.5, plot_len - 0.5)
