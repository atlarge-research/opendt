#!/usr/bin/env python3
"""
Interactive plot generator for OpenDT reproducibility capsule.

This script provides an interactive CLI to generate publication-ready plots
from OpenDT experiment runs. Users can select which experiment, data source,
and which plots to generate.

Available plots:
1. Power Prediction Accuracy (Ground Truth vs FootPrinter vs OpenDT)
2. Sustainability/Performance/Efficiency Overview
3. Job Completion Efficiency

Usage:
    python generate_plot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Import from new modular structure
from plots.config import OUTPUT_DIR
from plots.data_loader import discover_runs
from plots.job_completion_plot import generate_jobs_per_kwh_plot
from plots.power_prediction_plot import generate_energy_plot
from plots.sustainability_overview_plot import generate_efficiency_plot

console = Console()

# Default plot settings (True = enabled by default)
DEFAULT_PLOTS = {
    "power_prediction": False,
    "sustainability_overview": True,
    "job_completion": False,
}


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


def select_plots() -> dict[str, bool]:
    """Interactively select which plots to generate using arrow keys and space."""
    from InquirerPy import inquirer
    from InquirerPy.separator import Separator
    
    console.print()
    console.print("[bold]Select plots to generate:[/bold]")
    console.print("[dim]Use ↑↓ to navigate, Space to toggle, Enter to confirm[/dim]")
    
    # Define plot choices with defaults
    choices = [
        {"name": "Power Prediction Accuracy", "value": "power_prediction", "enabled": DEFAULT_PLOTS["power_prediction"]},
        {"name": "Sustainability/Performance/Efficiency Overview", "value": "sustainability_overview", "enabled": DEFAULT_PLOTS["sustainability_overview"]},
        {"name": "Job Completion Efficiency", "value": "job_completion", "enabled": DEFAULT_PLOTS["job_completion"]},
    ]
    
    selected = inquirer.checkbox(
        message="",
        choices=choices,
        instruction="",
        qmark="",
        amark="",
        show_cursor=False,
        validate=lambda result: len(result) > 0,
        invalid_message="Select at least one plot",
    ).execute()
    
    # Convert to dict
    enabled = {key: key in selected for key in DEFAULT_PLOTS.keys()}
    
    # Show final selection
    console.print()
    console.print("[dim]Selected plots:[/dim]")
    for choice in choices:
        if choice["value"] in selected:
            console.print(f"  [green]✓[/green] {choice['name']}")
    
    return enabled


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

    # Select which plots to generate
    enabled_plots = select_plots()

    # Get workload name for output path
    workload = run.get("workload", "unknown")
    run_path = run["path"]

    # Create experiment-specific output directory
    experiment_output_dir = OUTPUT_DIR / f"experiment_{experiment}"
    experiment_output_dir.mkdir(parents=True, exist_ok=True)

    # --- Generate Power Prediction Accuracy Plot ---
    if enabled_plots.get("power_prediction"):
        console.print()
        console.print("[bold]Generating Power Prediction Accuracy plot...[/bold]")
        
        power_prediction_output_path = experiment_output_dir / f"{workload}_power_prediction.pdf"
        
        try:
            mape_fp, mape_odt, samples = generate_energy_plot(
                run_path=run_path,
                workload=workload,
                output_path=power_prediction_output_path,
            )
            
            console.print(
                Panel.fit(
                    Text.assemble(
                        ("Power Prediction Accuracy Results\n\n", "bold"),
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
            console.print(f"[bold green]✓[/bold green] Saved: [cyan]{power_prediction_output_path}[/cyan]")
        except FileNotFoundError as e:
            console.print(f"[red]Error generating Power Prediction Accuracy plot: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error generating Power Prediction Accuracy plot: {e}[/red]")

    # --- Generate Sustainability/Performance/Efficiency Overview Plot ---
    if enabled_plots.get("sustainability_overview"):
        console.print()
        console.print("[bold]Generating Sustainability/Performance/Efficiency Overview plot...[/bold]")
        
        sustainability_output_path = experiment_output_dir / f"{workload}_sustainability_overview.pdf"
        
        try:
            avg_eff, max_eff, sample_count = generate_efficiency_plot(
                run_path=run_path,
                output_path=sustainability_output_path,
                workload=workload,
            )
            
            console.print(
                Panel.fit(
                    Text.assemble(
                        ("Sustainability Overview Results\n\n", "bold"),
                        ("Avg Efficiency: ", ""),
                        (f"{avg_eff:.2f} TFLOPs/kWh", "bold magenta"),
                        ("\nMax Efficiency: ", ""),
                        (f"{max_eff:.2f} TFLOPs/kWh", "bold cyan"),
                        ("\n\nHourly periods: ", ""),
                        (f"{sample_count:,}", "cyan"),
                    ),
                    border_style="magenta",
                )
            )
            console.print(f"[bold green]✓[/bold green] Saved: [cyan]{sustainability_output_path}[/cyan]")
        except ValueError as e:
            console.print(f"[red]Error generating Sustainability Overview plot: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error generating Sustainability Overview plot: {e}[/red]")

    # --- Generate Job Completion Efficiency Plot ---
    if enabled_plots.get("job_completion"):
        console.print()
        console.print("[bold]Generating Job Completion Efficiency plot...[/bold]")
        
        job_completion_output_path = experiment_output_dir / f"{workload}_job_completion.pdf"
        
        try:
            avg_jpk, max_jpk, num_periods = generate_jobs_per_kwh_plot(
                run_path=run_path,
                output_path=job_completion_output_path,
                aggregation_hours=3.0,
            )
            
            console.print(
                Panel.fit(
                    Text.assemble(
                        ("Job Completion Efficiency Results\n\n", "bold"),
                        ("Avg Jobs/kWh: ", ""),
                        (f"{avg_jpk:.2f}", "bold green"),
                        ("\nMax Jobs/kWh: ", ""),
                        (f"{max_jpk:.2f}", "bold cyan"),
                        ("\n\nTime periods: ", ""),
                        (f"{num_periods}", "cyan"),
                        (" (3-hour aggregation)", "dim"),
                    ),
                    border_style="green",
                )
            )
            console.print(f"[bold green]✓[/bold green] Saved: [cyan]{job_completion_output_path}[/cyan]")
        except ValueError as e:
            console.print(f"[red]Error generating Job Completion Efficiency plot: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error generating Job Completion Efficiency plot: {e}[/red]")

    console.print()
    console.print("[bold green]Done![/bold green]")
    console.print()


if __name__ == "__main__":
    main()
