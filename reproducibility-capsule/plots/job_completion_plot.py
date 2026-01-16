"""
Jobs per kWh plot generation.

Creates a plot showing job completion efficiency: jobs per kWh over time.
Shows 3 subplots: jobs completed, energy usage (kWh), and efficiency.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .processors import process_jobs_per_kwh_data

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# Colors for the plot
COLOR_JOBS = "#56B4E9"      # Light blue
COLOR_ENERGY = "#E69F00"    # Orange
COLOR_EFFICIENCY = "#009E73"  # Green


def generate_jobs_per_kwh_plot(
    run_path: Path,
    output_path: Path,
    aggregation_hours: float = 3.0,
) -> tuple[float, float, int]:
    """Generate jobs per kWh plot with 3 subplots.
    
    Shows:
    1. Jobs completed per period
    2. Energy used (kWh) per period
    3. Jobs per kWh efficiency
    
    Args:
        run_path: Path to the experiment run directory
        output_path: Path to save the output PDF
        aggregation_hours: Length of each aggregation period in hours
    
    Returns:
        Tuple of (avg_jobs_per_kwh, max_jobs_per_kwh, num_periods)
    """
    # Process data
    df = process_jobs_per_kwh_data(run_path, aggregation_hours=aggregation_hours)
    
    if len(df) == 0:
        raise ValueError("No jobs/kWh data found to plot")
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    
    x = np.arange(len(df))
    
    # Subplot 1: Jobs completed
    axes[0].grid(True, alpha=0.3)
    axes[0].bar(x, df["jobs_completed"].values, color=COLOR_JOBS, alpha=0.8)
    axes[0].set_ylabel("Jobs Completed", fontsize=18, labelpad=10)
    axes[0].tick_params(axis="y", labelsize=16)
    
    # Subplot 2: Energy usage (kWh)
    axes[1].grid(True, alpha=0.3)
    axes[1].bar(x, df["energy_kwh"].values, color=COLOR_ENERGY, alpha=0.8)
    axes[1].set_ylabel("Energy [kWh]", fontsize=18, labelpad=10)
    axes[1].tick_params(axis="y", labelsize=16)
    
    # Subplot 3: Jobs per kWh efficiency
    axes[2].grid(True, alpha=0.3)
    axes[2].plot(x, df["jobs_per_kwh"].values, color=COLOR_EFFICIENCY, lw=2, marker='o', markersize=4)
    axes[2].set_ylabel("Jobs per kWh", fontsize=18, labelpad=10)
    axes[2].tick_params(axis="y", labelsize=16)
    axes[2].set_xlabel("Time [day/month]", fontsize=18, labelpad=10)
    max_eff = df["jobs_per_kwh"].max()
    axes[2].set_ylim(0, max_eff * 1.1 if max_eff > 0 else 1)
    
    # Format X-axis with date labels (only on bottom subplot)
    _format_time_axis(axes[2], df["period_start"], len(df), aggregation_hours)
    
    plt.tight_layout()
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close()
    
    # Calculate summary statistics
    # Only consider periods with jobs for average
    periods_with_jobs = df[df["jobs_completed"] > 0]
    if len(periods_with_jobs) > 0:
        avg_jobs_per_kwh = float(periods_with_jobs["jobs_per_kwh"].mean())
    else:
        avg_jobs_per_kwh = 0.0
    max_jobs_per_kwh = float(df["jobs_per_kwh"].max())
    num_periods = len(df)
    
    return avg_jobs_per_kwh, max_jobs_per_kwh, num_periods


def _format_time_axis(ax: Axes, timestamps: pd.Series, plot_len: int, aggregation_hours: float) -> None:
    """Format the x-axis with date labels."""
    timestamps = pd.to_datetime(timestamps)
    
    # Show fewer labels for aggregated data
    if plot_len <= 10:
        tick_positions = list(range(plot_len))
        tick_labels = [ts.strftime("%d/%m %H:%M") for ts in timestamps]
    else:
        # Show about 6-8 labels
        step = max(1, plot_len // 6)
        tick_positions = list(range(0, plot_len, step))
        tick_labels = [timestamps.iloc[i].strftime("%d/%m") for i in tick_positions]
    
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=14, rotation=45, ha='right')
    ax.set_xlim(-0.5, plot_len - 0.5)
