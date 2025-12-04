#!/usr/bin/env python3
"""
Interactive plot generator for OpenDT reproducibility capsule.

This script provides an interactive CLI to generate publication-ready plots
from OpenDT experiment runs. Users can select which experiment and data source
to use for generating the plots.

Usage:
    python generate_plot.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import yaml
from matplotlib.ticker import FuncFormatter
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# Try to import matplotlib with a nice error message
try:
    import matplotlib.pyplot as plt
except ImportError:
    Console().print(
        "[red]Error:[/red] matplotlib is required. Install with: pip install matplotlib"
    )
    sys.exit(1)

# --- Constants ---
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
WORKLOAD_DIR = REPO_ROOT / "workload"
CAPSULE_DIR = Path(__file__).parent
CAPSULE_DATA_DIR = CAPSULE_DIR / "data"
OUTPUT_DIR = CAPSULE_DIR / "output"

COLOR_PALETTE = [
    "#0072B2",  # Blue (Ground Truth)
    "#E69F00",  # Orange (FootPrinter)
    "#009E73",  # Green (OpenDT)
    "#D55E00",  # Red-orange (MAPE rolling)
    "#CC79A7",  # Pink (MAPE cumulative)
]

METRIC = "power_draw"

console = Console()


# --- Data Discovery ---


def discover_runs() -> list[dict]:
    """Discover all available experiment runs in the data directory."""
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
        run_info: dict = {
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
                import json

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


# --- Interactive Selection ---


def select_experiment() -> int:
    """Interactively select which experiment to generate a plot for."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]OpenDT Reproducibility Plot Generator[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    experiments = [
        ("1", "Experiment 1: Predict power usage", "Without active calibration"),
        ("2", "Experiment 2: Predict power usage with calibration", "With active calibration"),
    ]

    console.print("[bold]Select an experiment:[/bold]")
    console.print()

    for num, title, desc in experiments:
        console.print(f"  [cyan]{num}[/cyan]) [bold]{title}[/bold]")
        console.print(f"      [dim]{desc}[/dim]")
        console.print()

    while True:
        choice = console.input("[bold]Enter choice (1 or 2): [/bold]").strip()
        if choice in ("1", "2"):
            return int(choice)
        console.print("[red]Invalid choice. Please enter 1 or 2.[/red]")


def select_data_source(runs: list[dict], experiment: int) -> dict | None:
    """Interactively select which data source to use."""
    console.print()
    console.print("[bold]Available data sources:[/bold]")
    console.print()

    # Filter runs based on experiment requirements
    if experiment == 1:
        # Experiment 1: needs simulator data AND calibration_enabled=False
        valid_runs = [
            r for r in runs if r["has_simulator"] and r.get("calibration_enabled") is False
        ]
        required = "simulator data with calibration disabled"
        config_file = "experiment_1.yaml"
    else:
        # Experiment 2: needs simulator + calibrator data AND calibration_enabled=True
        valid_runs = [
            r
            for r in runs
            if r["has_simulator"] and r["has_calibrator"] and r.get("calibration_enabled") is True
        ]
        required = "simulator + calibrator data with calibration enabled"
        config_file = "experiment_2.yaml"

    if not valid_runs:
        console.print(f"[red]No valid runs found with {required}.[/red]")
        console.print()
        console.print("[dim]To generate data for this experiment, run:[/dim]")
        cmd = f"make up config=config/experiments/{config_file}"
        console.print(f"  [cyan]{cmd}[/cyan]")
        console.print()
        console.print("[dim]Then wait for the simulation to complete.[/dim]")
        return None

    # Build table
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Run ID", style="bold")
    table.add_column("Time", style="green")
    table.add_column("Sim Duration", style="cyan")
    table.add_column("Workload", style="yellow")
    table.add_column("Data", style="dim")

    for i, run in enumerate(valid_runs, 1):
        data_status = []
        if run["has_simulator"]:
            data_status.append("sim")
        if run["has_calibrator"]:
            data_status.append("calib")

        table.add_row(
            str(i),
            run["name"],
            run["time_ago"],
            run.get("sim_duration", "—"),
            run.get("workload", "—"),
            " + ".join(data_status),
        )

    console.print(table)
    console.print()

    while True:
        choice = console.input(
            f"[bold]Select data source (1-{len(valid_runs)}) or 'q' to quit: [/bold]"
        ).strip()

        if choice.lower() == "q":
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(valid_runs):
                return valid_runs[idx]
        except ValueError:
            pass

        console.print(f"[red]Invalid choice. Enter a number 1-{len(valid_runs)}.[/red]")


# --- Data Loading & Processing ---


def load_baseline_data(
    workload: str,
) -> tuple[pd.Series, pd.Series]:  # type: ignore[type-arg]
    """Load FootPrinter and real world consumption data.

    FootPrinter data is loaded from reproducibility-capsule/data/<workload>/.
    Real world data is loaded from workload/<workload>/consumption.parquet.

    Returns:
        Tuple of (footprinter_series, real_world_series)
    """
    fp_data_dir = CAPSULE_DATA_DIR / workload
    fp_path = fp_data_dir / "footprinter.parquet"
    rw_path = WORKLOAD_DIR / workload / "consumption.parquet"

    if not fp_path.exists():
        console.print()
        console.print(f"[red]Error: FootPrinter data not found: {fp_path}[/red]")
        console.print(f"[dim]Expected file: {fp_path}[/dim]")
        sys.exit(1)

    if not rw_path.exists():
        console.print()
        console.print(f"[red]Error: Real world consumption data not found: {rw_path}[/red]")
        console.print(f"[dim]Expected file: {rw_path}[/dim]")
        sys.exit(1)

    # Load FootPrinter data
    fp_df = pd.read_parquet(fp_path)
    base_dt = pd.Timestamp("2022-10-06 22:00:00")

    # Handle timestamp conversion for footprinter
    if "timestamp_absolute" in fp_df.columns:
        fp_df["timestamp"] = pd.to_datetime(fp_df["timestamp_absolute"], unit="ms")
    else:
        fp_df["timestamp"] = base_dt + pd.to_timedelta(fp_df["timestamp"].values, unit="ms")

    fp_series: pd.Series = fp_df.groupby("timestamp")[METRIC].sum()  # type: ignore[type-arg, assignment]

    # Load real world consumption data
    rw_df = pd.read_parquet(rw_path)

    # Handle timestamp conversion for real world
    if "timestamp_absolute" in rw_df.columns:
        rw_df["timestamp"] = pd.to_datetime(rw_df["timestamp_absolute"], unit="ms")
    else:
        rw_df["timestamp"] = base_dt + pd.to_timedelta(rw_df["timestamp"].values, unit="ms")

    rw_series: pd.Series = rw_df.groupby("timestamp")[METRIC].sum()  # type: ignore[type-arg, assignment]

    return fp_series, rw_series


def load_opendt_results(run_path: Path) -> pd.Series:  # type: ignore[type-arg]
    """Load OpenDT simulation results.

    For both experiments, we use the simulator's aggregated results.
    The difference is:
    - Experiment 1: Simulator runs without calibration
    - Experiment 2: Simulator runs with calibration (receives calibrated topology)
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

    result: pd.Series = df.groupby("timestamp")[METRIC].sum()  # type: ignore[type-arg, assignment]
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


# --- Plot Generation ---


def generate_plot(
    run: dict,
    experiment: int,
    output_path: Path,
) -> tuple[float, float, int]:
    """Generate experiment plot with Ground Truth, FootPrinter, OpenDT, and MAPE.

    Returns:
        Tuple of (footprinter_mape, opendt_mape, sample_count)
    """
    workload = run.get("workload", "SURF")

    console.print()
    console.print("[bold]Loading data...[/bold]")

    # Load baseline data (FootPrinter and Real World)
    fp, rw = load_baseline_data(workload)
    odt = load_opendt_results(run["path"])

    console.print(f"  Ground Truth (real world): [green]{len(rw)}[/green] samples")
    console.print(f"  FootPrinter:               [green]{len(fp)}[/green] samples")
    console.print(f"  OpenDT:                    [green]{len(odt)}[/green] samples")

    # Interpolate to 1-minute
    console.print("[bold]Interpolating to 1-minute intervals...[/bold]")
    rw_1min = interpolate_to_1min(rw)
    fp_1min = interpolate_to_1min(fp)
    odt_1min = interpolate_to_1min(odt)

    # Find common time range across all three
    common_start = max(rw_1min.index[0], fp_1min.index[0], odt_1min.index[0])
    common_end = min(rw_1min.index[-1], fp_1min.index[-1], odt_1min.index[-1])

    console.print(f"  Common range: [cyan]{common_start}[/cyan] to [cyan]{common_end}[/cyan]")

    # Slice to common range
    rw_1min = rw_1min[common_start:common_end]
    fp_1min = fp_1min[common_start:common_end]
    odt_1min = odt_1min[common_start:common_end]

    console.print(f"  Aligned samples: [green]{len(rw_1min)}[/green]")

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
    console.print("[bold]Generating plot...[/bold]")

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.grid(True, alpha=0.3)

    x = np.arange(plot_len)

    # Plot power lines on primary y-axis (thinner lines: lw=1.5)
    rw_values = np.asarray(rw_5min.values) / 1000
    fp_values = np.asarray(fp_5min.values) / 1000
    odt_values = np.asarray(odt_5min.values) / 1000

    line1 = ax1.plot(x, rw_values, label="Ground Truth", color=COLOR_PALETTE[0], lw=1.5)
    line2 = ax1.plot(x, fp_values, label="FootPrinter", color=COLOR_PALETTE[1], lw=1.5)
    line3 = ax1.plot(x, odt_values, label="OpenDT", color=COLOR_PALETTE[2], lw=1.5)

    # Create secondary y-axis for MAPE
    ax2 = ax1.twinx()

    # Plot MAPE line (cumulative average)
    line4 = ax2.plot(
        x,
        cumulative_mape_5min,
        label="MAPE (OpenDT)",
        color=COLOR_PALETTE[3],
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


# --- Main ---


def main() -> None:
    """Main entry point for the plot generator."""
    # Select experiment
    experiment = select_experiment()

    # Discover available runs
    runs = discover_runs()

    if not runs:
        console.print()
        console.print("[red]No experiment runs found in ./data directory.[/red]")
        console.print("[dim]Run an experiment first with:[/dim]")
        cmd = f"make up config=config/experiments/experiment_{experiment}.yaml"
        console.print(f"  [cyan]{cmd}[/cyan]")
        return

    # Select data source
    run = select_data_source(runs, experiment)

    if run is None:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    console.print()
    console.print(f"[bold green]✓[/bold green] Selected: [cyan]{run['name']}[/cyan]")

    # Get workload name for output path
    workload = run.get("workload", "unknown")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate output path: ./reproducibility-capsule/output/experiment_<number>_<workload>.pdf
    output_path = OUTPUT_DIR / f"experiment_{experiment}_{workload}.pdf"

    # Generate plot
    mape_fp, mape_odt, samples = generate_plot(run, experiment, output_path)

    # Print results
    console.print()
    console.print(
        Panel.fit(
            Text.assemble(
                ("Results\n\n", "bold"),
                ("FootPrinter MAPE: ", ""),
                (f"{mape_fp:.2f}%", "bold yellow"),
                ("\nOpenDT MAPE:      ", ""),
                (f"{mape_odt:.2f}%", "bold green"),
                ("\n\nSamples: ", ""),
                (f"{samples:,}", "cyan"),
                (" (1-minute resolution)", "dim"),
            ),
            border_style="green",
        )
    )

    console.print()
    console.print(f"[bold green]✓[/bold green] Plot saved to: [cyan]{output_path}[/cyan]")
    console.print()


if __name__ == "__main__":
    main()
