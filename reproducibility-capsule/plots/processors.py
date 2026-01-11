"""
Data processing functions for plot generation.

Provides functions to process raw host data into aggregated metrics for plotting.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .data_loader import get_opendc_run_ids, load_host_parquet, load_run_metadata

if TYPE_CHECKING:
    pass


def process_cpu_latency_data(run_path: Path) -> pd.DataFrame:
    """Process all OpenDC runs to extract CPU utilization and latency metrics.
    
    For each run, calculates:
    - Average CPU utilization across all hosts
    - Estimated completion duration (latency) in hours
    - Maps to the simulated time from metadata
    
    Args:
        run_path: Path to the experiment run directory
    
    Returns:
        DataFrame with columns:
        - run_id: Run number
        - datetime: Simulated time for this run
        - avg_cpu_utilization: Mean CPU utilization [%]
        - latency_hours: Estimated completion duration [hours]
    """
    run_ids = get_opendc_run_ids(run_path)
    
    if not run_ids:
        return pd.DataFrame(columns=["run_id", "datetime", "avg_cpu_utilization", "latency_hours"])
    
    results = []
    
    for run_id in run_ids:
        result = process_single_run(run_path, run_id)
        if result is not None:
            results.append(result)
    
    if not results:
        return pd.DataFrame(columns=["run_id", "datetime", "avg_cpu_utilization", "latency_hours"])
    
    df = pd.DataFrame(results)
    df = df.sort_values("run_id").reset_index(drop=True)
    
    return df


def process_single_run(run_path: Path, run_id: int) -> dict | None:
    """Process a single OpenDC run to extract metrics.
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        Dictionary with run metrics or None if processing failed.
    """
    # Load metadata for simulated time
    metadata = load_run_metadata(run_path, run_id)
    if metadata is None:
        return None
    
    simulated_time_str = metadata.get("simulated_time")
    if not simulated_time_str:
        return None
    
    # Parse simulated time
    try:
        simulated_time = pd.to_datetime(simulated_time_str)
    except Exception:
        return None
    
    # Load host data
    df = load_host_parquet(run_path, run_id)
    if df is None or len(df) == 0:
        return None
    
    # Find CPU utilization column
    cpu_col = _find_cpu_column(df)
    if cpu_col is None:
        return None
    
    # Calculate average CPU utilization across all hosts and timestamps
    # Note: cpu_utilization is stored as a fraction (0-1), multiply by 100 for percentage
    avg_cpu = df[cpu_col].mean() * 100
    
    # Calculate latency (duration of this simulation in hours)
    # Using timestamp column (in milliseconds from simulation start)
    time_col = _find_time_column(df)
    if time_col is not None:
        min_time = df[time_col].min()
        max_time = df[time_col].max()
        duration_ms = max_time - min_time
        latency_hours = duration_ms / (1000 * 60 * 60)  # Convert ms to hours
    else:
        latency_hours = 0.0
    
    return {
        "run_id": run_id,
        "datetime": simulated_time,
        "avg_cpu_utilization": avg_cpu,
        "latency_hours": latency_hours,
    }


def _find_cpu_column(df: pd.DataFrame) -> str | None:
    """Find the CPU utilization column in the dataframe."""
    cols = df.columns.tolist()
    
    # Direct match
    if "cpu_utilization" in cols:
        return "cpu_utilization"
    
    # Fuzzy match
    for col in cols:
        col_lower = col.lower()
        if "cpu" in col_lower and "util" in col_lower:
            return col
        if "cpu" in col_lower and "usage" in col_lower:
            return col
    
    return None


def _find_time_column(df: pd.DataFrame) -> str | None:
    """Find the timestamp column in the dataframe."""
    cols = df.columns.tolist()
    
    if "timestamp" in cols:
        return "timestamp"
    if "time" in cols:
        return "time"
    if "timestamp_absolute" in cols:
        return "timestamp_absolute"
    
    return None
