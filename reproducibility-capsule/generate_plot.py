#!/usr/bin/env python3
"""
Interactive plot generator for OpenDT reproducibility capsule.

This script provides an interactive CLI to generate publication-ready plots
from OpenDT experiment runs. Users can select which experiment and data source
to use for generating the plots.

Generates:
1. Energy consumption plot (Ground Truth vs FootPrinter vs OpenDT)
2. CPU utilization and latency plot (dual-axis)

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
from plots.cpu_latency_plot import generate_cpu_latency_plot
from plots.data_loader import discover_runs
from plots.energy_plot import generate_energy_plot

console = Console()


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
    run_path = run["path"]

    # Create experiment-specific output directory
    experiment_output_dir = OUTPUT_DIR / f"experiment_{experiment}"
    experiment_output_dir.mkdir(parents=True, exist_ok=True)

    # --- Generate Energy Plot ---
    console.print()
    console.print("[bold]Generating energy consumption plot...[/bold]")
    
    energy_output_path = experiment_output_dir / f"{workload}_energy.pdf"
    
    try:
        mape_fp, mape_odt, samples = generate_energy_plot(
            run_path=run_path,
            workload=workload,
            output_path=energy_output_path,
        )
        
        console.print(
            Panel.fit(
                Text.assemble(
                    ("Energy Plot Results\n\n", "bold"),
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
        console.print(f"[bold green]✓[/bold green] Saved: [cyan]{energy_output_path}[/cyan]")
    except FileNotFoundError as e:
        console.print(f"[red]Error generating energy plot: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error generating energy plot: {e}[/red]")

    # --- Generate CPU/Latency Plot ---
    console.print()
    console.print("[bold]Generating CPU utilization & latency plot...[/bold]")
    
    cpu_latency_output_path = experiment_output_dir / f"{workload}_cpu_latency.pdf"
    
    try:
        avg_cpu, avg_latency, run_count = generate_cpu_latency_plot(
            run_path=run_path,
            output_path=cpu_latency_output_path,
        )
        
        console.print(
            Panel.fit(
                Text.assemble(
                    ("CPU/Latency Plot Results\n\n", "bold"),
                    ("Avg CPU Utilization: ", ""),
                    (f"{avg_cpu:.2f}%", "bold cyan"),
                    ("\nAvg Latency:         ", ""),
                    (f"{avg_latency:.2f}h", "bold yellow"),
                    ("\n\nRuns processed: ", ""),
                    (f"{run_count}", "cyan"),
                ),
                border_style="blue",
            )
        )
        console.print(f"[bold green]✓[/bold green] Saved: [cyan]{cpu_latency_output_path}[/cyan]")
    except ValueError as e:
        console.print(f"[red]Error generating CPU/latency plot: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error generating CPU/latency plot: {e}[/red]")

    console.print()
    console.print("[bold green]Done![/bold green]")
    console.print()


if __name__ == "__main__":
    main()
