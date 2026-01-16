"""
Data loading utilities for plot generation.

Provides functions to discover experiment runs and load data from parquet files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import yaml

from .config import DATA_DIR

if TYPE_CHECKING:
    from typing import Any


def discover_runs() -> list[dict[str, Any]]:
    """Discover all available experiment runs in the data directory.
    
    Returns:
        List of run info dictionaries with paths, timestamps, and metadata.
    """
    runs = []

    if not DATA_DIR.exists():
        return runs

    for run_dir in sorted(DATA_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue

        # Check if it looks like a valid run (has config.yaml)
        config_path = run_dir / "config.yaml"
        metadata_path = run_dir / "metadata.json"

        if not config_path.exists():
            continue

        sim_results_path = run_dir / "simulator" / "agg_results.parquet"
        run_info: dict[str, Any] = {
            "path": run_dir,
            "name": run_dir.name,
            "has_simulator": sim_results_path.exists(),
            "has_calibrator": (run_dir / "calibrator" / "agg_results.parquet").exists(),
            "sim_duration": "—",
            "workload": "Unknown",
        }

        # Parse timestamp from folder name (format: YYYY_MM_DD_HH_MM_SS)
        try:
            run_time = datetime.strptime(run_dir.name, "%Y_%m_%d_%H_%M_%S")
            run_info["timestamp"] = run_time
            run_info["time_ago"] = format_time_ago(run_time)
        except ValueError:
            run_info["timestamp"] = None
            run_info["time_ago"] = "Unknown"

        # Try to read metadata for config source
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
                run_info["config_source"] = metadata.get("config_source", "Unknown")
            except Exception:
                run_info["config_source"] = "Unknown"
        else:
            run_info["config_source"] = "Unknown"

        # Read workload and calibration_enabled from config.yaml
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            workload = config.get("services", {}).get("dc-mock", {}).get("workload", "Unknown")
            run_info["workload"] = workload
            # Read calibration_enabled (defaults to False if not present)
            calibration_enabled = config.get("global", {}).get("calibration_enabled", False)
            run_info["calibration_enabled"] = calibration_enabled
        except Exception:
            run_info["calibration_enabled"] = None  # Unknown

        # Try to read simulation duration from simulator results
        if sim_results_path.exists():
            try:
                df = pd.read_parquet(sim_results_path)
                if "timestamp" in df.columns and len(df) > 1:
                    timestamps = pd.to_datetime(df["timestamp"])
                    duration_minutes = (timestamps.max() - timestamps.min()).total_seconds() / 60
                    run_info["sim_duration"] = format_duration(duration_minutes)
            except Exception:
                pass

        runs.append(run_info)

    return runs


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as a human-readable 'time ago' string."""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def format_duration(minutes: float) -> str:
    """Format a duration in minutes as a human-readable string.

    Examples: "7 days, 3 hours", "5 hours", "45 minutes"
    """
    if minutes < 1:
        return "< 1 minute"

    total_minutes = int(minutes)
    days = total_minutes // (24 * 60)
    remaining = total_minutes % (24 * 60)
    hours = remaining // 60
    mins = remaining % 60

    parts = []

    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
        # Only show hours if there are days
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    elif hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        # Only show minutes if less than a day and there are hours
        if mins >= 30:
            parts.append(f"{mins} min")
    else:
        parts.append(f"{mins} minute{'s' if mins != 1 else ''}")

    return ", ".join(parts)


def load_run_metadata(run_path: Path, run_id: int) -> dict[str, Any] | None:
    """Load metadata.json for a specific OpenDC run.
    
    Args:
        run_path: Path to the experiment run directory (e.g., data/2025_12_06_14_01_07)
        run_id: The run number (e.g., 1, 2, ..., 167)
    
    Returns:
        Dictionary with run metadata or None if not found.
    """
    metadata_path = run_path / "simulator" / "opendc" / f"run_{run_id}" / "metadata.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path) as f:
            return json.load(f)
    except Exception:
        return None


def find_host_parquet(run_path: Path, run_id: int) -> Path | None:
    """Find the host.parquet file for a specific run.
    
    The file is located at a nested path like:
    simulator/opendc/run_<N>/output/run_1/raw-output/0/seed=0/host.parquet
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        Path to host.parquet or None if not found.
    """
    base = run_path / "simulator" / "opendc" / f"run_{run_id}" / "output"
    
    # The nested structure has run_1 inside output, then raw-output/0/seed=0
    candidate = base / "run_1" / "raw-output" / "0" / "seed=0" / "host.parquet"
    
    if candidate.exists():
        return candidate
    
    # Fallback: try to find it with glob
    matches = list(base.glob("**/host.parquet"))
    if matches:
        return matches[0]
    
    return None


def load_host_parquet(run_path: Path, run_id: int) -> pd.DataFrame | None:
    """Load host.parquet for a specific OpenDC run.
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        DataFrame with host metrics or None if not found.
    """
    parquet_path = find_host_parquet(run_path, run_id)
    
    if parquet_path is None:
        return None
    
    try:
        return pd.read_parquet(parquet_path)
    except Exception:
        return None


def find_power_source_parquet(run_path: Path, run_id: int) -> Path | None:
    """Find the powerSource.parquet file for a specific run.
    
    The file is located at a nested path like:
    simulator/opendc/run_<N>/output/run_1/raw-output/0/seed=0/powerSource.parquet
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        Path to powerSource.parquet or None if not found.
    """
    base = run_path / "simulator" / "opendc" / f"run_{run_id}" / "output"
    
    # The nested structure has run_1 inside output, then raw-output/0/seed=0
    candidate = base / "run_1" / "raw-output" / "0" / "seed=0" / "powerSource.parquet"
    
    if candidate.exists():
        return candidate
    
    # Fallback: try to find it with glob
    matches = list(base.glob("**/powerSource.parquet"))
    if matches:
        return matches[0]
    
    return None


def load_power_source_parquet(run_path: Path, run_id: int) -> pd.DataFrame | None:
    """Load powerSource.parquet for a specific OpenDC run.
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        DataFrame with power source metrics or None if not found.
    """
    parquet_path = find_power_source_parquet(run_path, run_id)
    
    if parquet_path is None:
        return None
    
    try:
        return pd.read_parquet(parquet_path)
    except Exception:
        return None


def find_task_parquet(run_path: Path, run_id: int) -> Path | None:
    """Find the task.parquet file for a specific run.
    
    The file is located at a nested path like:
    simulator/opendc/run_<N>/output/run_1/raw-output/0/seed=0/task.parquet
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        Path to task.parquet or None if not found.
    """
    base = run_path / "simulator" / "opendc" / f"run_{run_id}" / "output"
    
    candidate = base / "run_1" / "raw-output" / "0" / "seed=0" / "task.parquet"
    
    if candidate.exists():
        return candidate
    
    # Fallback: try to find it with glob
    matches = list(base.glob("**/task.parquet"))
    if matches:
        return matches[0]
    
    return None


def load_task_parquet(run_path: Path, run_id: int) -> pd.DataFrame | None:
    """Load task.parquet for a specific OpenDC run.
    
    Args:
        run_path: Path to the experiment run directory
        run_id: The run number
    
    Returns:
        DataFrame with task metrics or None if not found.
    """
    parquet_path = find_task_parquet(run_path, run_id)
    
    if parquet_path is None:
        return None
    
    try:
        return pd.read_parquet(parquet_path)
    except Exception:
        return None


def get_opendc_run_ids(run_path: Path) -> list[int]:
    """Get list of all OpenDC run IDs in an experiment.
    
    Args:
        run_path: Path to the experiment run directory
    
    Returns:
        Sorted list of run IDs (integers).
    """
    opendc_dir = run_path / "simulator" / "opendc"
    
    if not opendc_dir.exists():
        return []
    
    run_ids = []
    for folder in opendc_dir.iterdir():
        if folder.is_dir() and folder.name.startswith("run_"):
            try:
                run_id = int(folder.name.split("_")[-1])
                run_ids.append(run_id)
            except ValueError:
                continue
    
    return sorted(run_ids)


def get_workload_start_time(run_path: Path) -> pd.Timestamp:
    """Get the workload start time from the first run's metadata.
    
    The start time is derived from run_1's 'last_task_time' field in metadata.json,
    which represents the earliest task timestamp in the workload.
    
    Args:
        run_path: Path to the experiment run directory
    
    Returns:
        Timestamp representing the workload start time.
    
    Raises:
        ValueError: If metadata cannot be read or parsed.
    """
    metadata = load_run_metadata(run_path, run_id=1)
    
    if metadata is None:
        raise ValueError(f"Could not load metadata for run_1 in {run_path}")
    
    # The 'last_task_time' in run_1 is actually the earliest task time
    # (it's the last task submitted before this run's window closed)
    last_task_time = metadata.get("last_task_time")
    
    if last_task_time is None:
        raise ValueError("No 'last_task_time' found in run_1 metadata")
    
    try:
        start_time = pd.to_datetime(last_task_time)
        # Remove timezone info for consistency
        if start_time.tz is not None:
            start_time = start_time.tz_localize(None)
        return start_time
    except Exception as e:
        raise ValueError(f"Could not parse last_task_time '{last_task_time}': {e}")
