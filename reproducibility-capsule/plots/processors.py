"""
Data processing functions for plot generation.

Provides functions to process raw host data into aggregated metrics for plotting.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .data_loader import (
    get_opendc_run_ids,
    load_host_parquet,
    load_power_source_parquet,
    load_run_metadata,
    load_task_parquet,
)

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


def process_flops_data(run_path: Path) -> pd.DataFrame:
    """Process all OpenDC runs to extract fine-grained FLOPS (MHz) metrics.
    
    For each timestamp within each run's window:
    - Sums CPU usage (MHz) across all hosts
    - Returns this as a separate data point
    
    The window for run N is derived from:
    - Start: simulated_time of run N-1 (or workload start for run 1)
    - End: simulated_time of run N
    
    Args:
        run_path: Path to the experiment run directory
    
    Returns:
        DataFrame with columns:
        - datetime: Absolute timestamp
        - total_mhz: Total cluster MHz at that timestamp
    """
    run_ids = get_opendc_run_ids(run_path)
    
    if not run_ids:
        return pd.DataFrame(columns=["datetime", "total_mhz"])
    
    # First, collect all simulated_times to build window ranges
    run_times: dict[int, pd.Timestamp] = {}
    for run_id in run_ids:
        metadata = load_run_metadata(run_path, run_id)
        if metadata and "simulated_time" in metadata:
            try:
                ts = pd.to_datetime(metadata["simulated_time"])
                if ts.tz is not None:
                    ts = ts.tz_localize(None)
                run_times[run_id] = ts
            except Exception:
                pass
    
    if not run_times:
        return pd.DataFrame(columns=["datetime", "total_mhz"])
    
    # Get workload start time
    from .data_loader import get_workload_start_time
    try:
        workload_start = get_workload_start_time(run_path)
    except ValueError:
        workload_start = min(run_times.values()) - pd.Timedelta(hours=1)
    
    all_results = []
    sorted_run_ids = sorted(run_times.keys())
    
    for i, run_id in enumerate(sorted_run_ids):
        # Determine window range
        if i == 0:
            window_start = workload_start
        else:
            prev_run_id = sorted_run_ids[i - 1]
            window_start = run_times[prev_run_id]
        
        window_end = run_times[run_id]
        
        run_df = _process_single_run_flops_detailed(
            run_path, run_id, workload_start, window_start, window_end
        )
        if run_df is not None and len(run_df) > 0:
            all_results.append(run_df)
    
    if not all_results:
        return pd.DataFrame(columns=["datetime", "total_mhz"])
    
    # Concatenate all runs into one timeseries
    df = pd.concat(all_results, ignore_index=True)
    df = df.sort_values("datetime").reset_index(drop=True)
    
    return df


def _process_single_run_flops_detailed(
    run_path: Path,
    run_id: int,
    workload_start: pd.Timestamp,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.DataFrame | None:
    """Process a single OpenDC run to extract per-timestamp FLOPS (MHz).
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
        workload_start: Absolute start time of the workload
        window_start: Start of this run's window (absolute)
        window_end: End of this run's window (absolute)
    
    Returns:
        DataFrame with datetime and total_mhz columns, or None if failed.
    """
    # Load host data
    df = load_host_parquet(run_path, run_id)
    if df is None or len(df) == 0:
        return None
    
    # Check for required columns
    if "cpu_usage" not in df.columns:
        return None
    
    time_col = _find_time_column(df)
    if time_col is None:
        return None
    
    # Convert relative timestamps (ms) to absolute timestamps
    df["absolute_time"] = workload_start + pd.to_timedelta(df[time_col], unit="ms")
    
    # Filter to only timestamps within this run's window
    mask = (df["absolute_time"] > window_start) & (df["absolute_time"] <= window_end)
    df_window = df[mask]
    
    if len(df_window) == 0:
        return None
    
    # Sum cpu_usage across all hosts for each timestamp
    total_per_timestamp = df_window.groupby("absolute_time")["cpu_usage"].sum().reset_index()
    total_per_timestamp.columns = ["datetime", "total_mhz"]
    
    return total_per_timestamp


def process_efficiency_data(run_path: Path) -> pd.DataFrame:
    """Process all OpenDC runs to extract efficiency (MHz per power) metrics.
    
    For each timestamp within each run's window:
    - Sums CPU usage (MHz) across all hosts
    - Gets power draw from powerSource.parquet
    - Calculates efficiency as MHz / Watts
    
    Args:
        run_path: Path to the experiment run directory
    
    Returns:
        DataFrame with columns:
        - datetime: Absolute timestamp
        - total_mhz: Total cluster MHz at that timestamp
        - power_draw: Total power draw at that timestamp
        - efficiency: MHz per Watt
    """
    run_ids = get_opendc_run_ids(run_path)
    
    if not run_ids:
        return pd.DataFrame(columns=["datetime", "total_mhz", "power_draw", "efficiency"])
    
    # Collect all simulated_times to build window ranges
    run_times: dict[int, pd.Timestamp] = {}
    for run_id in run_ids:
        metadata = load_run_metadata(run_path, run_id)
        if metadata and "simulated_time" in metadata:
            try:
                ts = pd.to_datetime(metadata["simulated_time"])
                if ts.tz is not None:
                    ts = ts.tz_localize(None)
                run_times[run_id] = ts
            except Exception:
                pass
    
    if not run_times:
        return pd.DataFrame(columns=["datetime", "total_mhz", "power_draw", "efficiency"])
    
    # Get workload start time
    from .data_loader import get_workload_start_time
    try:
        workload_start = get_workload_start_time(run_path)
    except ValueError:
        workload_start = min(run_times.values()) - pd.Timedelta(hours=1)
    
    all_results = []
    sorted_run_ids = sorted(run_times.keys())
    
    for i, run_id in enumerate(sorted_run_ids):
        if i == 0:
            window_start = workload_start
        else:
            prev_run_id = sorted_run_ids[i - 1]
            window_start = run_times[prev_run_id]
        
        window_end = run_times[run_id]
        
        run_df = _process_single_run_efficiency(
            run_path, run_id, workload_start, window_start, window_end
        )
        if run_df is not None and len(run_df) > 0:
            all_results.append(run_df)
    
    if not all_results:
        return pd.DataFrame(columns=["datetime", "total_mhz", "power_draw", "efficiency"])
    
    df = pd.concat(all_results, ignore_index=True)
    df = df.sort_values("datetime").reset_index(drop=True)
    
    return df


def _process_single_run_efficiency(
    run_path: Path,
    run_id: int,
    workload_start: pd.Timestamp,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.DataFrame | None:
    """Process a single run to extract efficiency metrics.
    
    Combines host.parquet (cpu_usage) and powerSource.parquet (power_draw).
    """
    # Load host data for CPU usage
    host_df = load_host_parquet(run_path, run_id)
    if host_df is None or len(host_df) == 0:
        return None
    
    # Load power source data
    power_df = load_power_source_parquet(run_path, run_id)
    if power_df is None or len(power_df) == 0:
        return None
    
    # Check for required columns
    if "cpu_usage" not in host_df.columns or "power_draw" not in power_df.columns:
        return None
    
    time_col = _find_time_column(host_df)
    if time_col is None:
        return None
    
    # Convert relative timestamps to absolute for host data
    host_df["absolute_time"] = workload_start + pd.to_timedelta(host_df[time_col], unit="ms")
    
    # Filter host data to window
    mask = (host_df["absolute_time"] > window_start) & (host_df["absolute_time"] <= window_end)
    host_window = host_df[mask]
    
    if len(host_window) == 0:
        return None
    
    # Sum cpu_usage across all hosts for each timestamp
    mhz_per_timestamp = host_window.groupby("absolute_time")["cpu_usage"].sum().reset_index()
    mhz_per_timestamp.columns = ["datetime", "total_mhz"]
    
    # Process power data - convert timestamps
    power_time_col = _find_time_column(power_df)
    if power_time_col is None:
        return None
    
    power_df["absolute_time"] = workload_start + pd.to_timedelta(power_df[power_time_col], unit="ms")
    
    # Filter power data to window
    mask = (power_df["absolute_time"] > window_start) & (power_df["absolute_time"] <= window_end)
    power_window = power_df[mask]
    
    if len(power_window) == 0:
        return None
    
    # Sum power_draw (in case of multiple sources)
    power_per_timestamp = power_window.groupby("absolute_time")["power_draw"].sum().reset_index()
    power_per_timestamp.columns = ["datetime", "power_draw"]
    
    # Merge on datetime
    merged = pd.merge(mhz_per_timestamp, power_per_timestamp, on="datetime", how="inner")
    
    if len(merged) == 0:
        return None
    
    # Calculate efficiency: MHz per kW
    merged["efficiency"] = merged["total_mhz"] / (merged["power_draw"] / 1000)
    
    return merged


def process_jobs_per_kwh_data(
    run_path: Path,
    aggregation_hours: float = 3.0,
) -> pd.DataFrame:
    """Process all OpenDC runs to extract jobs per kWh metrics.
    
    Aggregates data into time periods of specified length, calculating:
    - Number of jobs completed in each period
    - Energy usage (kWh) in each period
    - Efficiency: jobs per kWh
    
    Args:
        run_path: Path to the experiment run directory
        aggregation_hours: Length of each aggregation period in hours
    
    Returns:
        DataFrame with columns:
        - period_start: Start datetime of the period
        - jobs_completed: Number of jobs completed in the period
        - energy_kwh: Energy used in kWh during the period
        - jobs_per_kwh: Jobs completed per kWh
    """
    run_ids = get_opendc_run_ids(run_path)
    
    if not run_ids:
        return pd.DataFrame(columns=["period_start", "jobs_completed", "energy_kwh", "jobs_per_kwh"])
    
    # Collect all simulated_times to build window ranges
    run_times: dict[int, pd.Timestamp] = {}
    for run_id in run_ids:
        metadata = load_run_metadata(run_path, run_id)
        if metadata and "simulated_time" in metadata:
            try:
                ts = pd.to_datetime(metadata["simulated_time"])
                if ts.tz is not None:
                    ts = ts.tz_localize(None)
                run_times[run_id] = ts
            except Exception:
                pass
    
    if not run_times:
        return pd.DataFrame(columns=["period_start", "jobs_completed", "energy_kwh", "jobs_per_kwh"])
    
    # Get workload start time
    from .data_loader import get_workload_start_time
    try:
        workload_start = get_workload_start_time(run_path)
    except ValueError:
        workload_start = min(run_times.values()) - pd.Timedelta(hours=1)
    
    # Collect all job completions and power data across runs
    all_job_completions = []  # List of (datetime,) tuples
    all_power_data = []  # List of (datetime, power_draw, duration_hours) tuples
    
    sorted_run_ids = sorted(run_times.keys())
    
    for i, run_id in enumerate(sorted_run_ids):
        if i == 0:
            window_start = workload_start
        else:
            prev_run_id = sorted_run_ids[i - 1]
            window_start = run_times[prev_run_id]
        
        window_end = run_times[run_id]
        
        # Get job completions for this run's window
        job_times = _get_jobs_completed_in_window(
            run_path, run_id, workload_start, window_start, window_end
        )
        all_job_completions.extend(job_times)
        
        # Get power data for this run's window
        power_data = _get_power_in_window(
            run_path, run_id, workload_start, window_start, window_end
        )
        all_power_data.extend(power_data)
    
    if not all_job_completions and not all_power_data:
        return pd.DataFrame(columns=["period_start", "jobs_completed", "energy_kwh", "jobs_per_kwh"])
    
    # Aggregate into time periods
    aggregation_ms = aggregation_hours * 3600 * 1000
    
    # Find min and max times
    all_times = [t for t in all_job_completions] + [t for t, _, _ in all_power_data]
    if not all_times:
        return pd.DataFrame(columns=["period_start", "jobs_completed", "energy_kwh", "jobs_per_kwh"])
    
    min_time = min(all_times)
    max_time = max(all_times)
    
    # Create time buckets
    results = []
    period_start = workload_start
    period_delta = pd.Timedelta(hours=aggregation_hours)
    
    while period_start < max_time:
        period_end = period_start + period_delta
        
        # Count jobs completed in this period
        jobs = sum(1 for t in all_job_completions if period_start <= t < period_end)
        
        # Calculate energy (power * time) in kWh for this period
        energy_wh = 0.0
        for dt, power_w, duration_h in all_power_data:
            if period_start <= dt < period_end:
                energy_wh += power_w * duration_h
        energy_kwh = energy_wh / 1000
        
        # Calculate jobs per kWh
        jobs_per_kwh = jobs / energy_kwh if energy_kwh > 0 else 0.0
        
        results.append({
            "period_start": period_start,
            "jobs_completed": jobs,
            "energy_kwh": energy_kwh,
            "jobs_per_kwh": jobs_per_kwh,
        })
        
        period_start = period_end
    
    df = pd.DataFrame(results)
    return df


def _get_jobs_completed_in_window(
    run_path: Path,
    run_id: int,
    workload_start: pd.Timestamp,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> list[pd.Timestamp]:
    """Get list of job completion times within a run's window.
    
    Returns list of absolute timestamps when jobs completed.
    """
    task_df = load_task_parquet(run_path, run_id)
    if task_df is None or len(task_df) == 0:
        return []
    
    # Filter to completed tasks
    completed = task_df[task_df["task_state"] == "COMPLETED"].copy()
    if len(completed) == 0:
        return []
    
    # Convert finish_time (ms) to absolute timestamp
    completed["finish_datetime"] = workload_start + pd.to_timedelta(completed["finish_time"], unit="ms")
    
    # Filter to jobs that finished within this window
    # (using finish_datetime, not the snapshot timestamp)
    mask = (completed["finish_datetime"] > window_start) & (completed["finish_datetime"] <= window_end)
    window_completions = completed[mask]
    
    # Get unique task completions (avoid counting same task multiple times)
    unique_completions = window_completions.drop_duplicates(subset=["task_id"])
    
    return unique_completions["finish_datetime"].tolist()


def _get_power_in_window(
    run_path: Path,
    run_id: int,
    workload_start: pd.Timestamp,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> list[tuple[pd.Timestamp, float, float]]:
    """Get power measurements within a run's window.
    
    Returns list of (datetime, power_watts, duration_hours) tuples.
    """
    power_df = load_power_source_parquet(run_path, run_id)
    if power_df is None or len(power_df) == 0:
        return []
    
    if "power_draw" not in power_df.columns:
        return []
    
    time_col = _find_time_column(power_df)
    if time_col is None:
        return []
    
    # Convert timestamps
    power_df["absolute_time"] = workload_start + pd.to_timedelta(power_df[time_col], unit="ms")
    
    # Filter to window
    mask = (power_df["absolute_time"] > window_start) & (power_df["absolute_time"] <= window_end)
    window_power = power_df[mask]
    
    if len(window_power) == 0:
        return []
    
    # Sum power across sources per timestamp
    power_per_ts = window_power.groupby("absolute_time")["power_draw"].sum().reset_index()
    
    # Calculate duration between measurements (assuming regular intervals)
    power_per_ts = power_per_ts.sort_values("absolute_time")
    if len(power_per_ts) >= 2:
        typical_delta = (power_per_ts["absolute_time"].iloc[1] - power_per_ts["absolute_time"].iloc[0]).total_seconds() / 3600
    else:
        typical_delta = 0.0417  # ~2.5 minutes in hours as fallback
    
    result = []
    for _, row in power_per_ts.iterrows():
        result.append((row["absolute_time"], row["power_draw"], typical_delta))
    
    return result
