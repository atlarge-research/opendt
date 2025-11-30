#!/usr/bin/env python3
"""OpenDT CLI - Initialization and management tool."""

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="opendt",
    help="OpenDT - Open Digital Twin CLI for datacenter simulation",
    add_completion=False,
)
console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    # Script is in scripts/, so parent is project root
    return Path(__file__).parent.parent


def get_run_id_file() -> Path:
    """Get the path to the run ID file."""
    return get_project_root() / ".run_id"


@app.command()
def init(
    config: str = typer.Option(
        "./config/default.yaml",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Initialize a new OpenDT run.

    This command:
    - Generates a unique run ID timestamp
    - Creates required directory structure
    - Saves run ID for docker-compose to use
    """
    console.print("\n[bold cyan]Initializing OpenDT...[/bold cyan]\n")

    # Validate config file exists
    project_root = get_project_root()
    config_path = project_root / config

    if not config_path.exists():
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config_path}")
        raise typer.Exit(code=1)

    console.print(f"[green]✓[/green] Config file found: {config_path}")

    # Generate timestamp ID
    timestamp = datetime.now(UTC).strftime("%Y_%m_%d_%H_%M_%S")
    console.print(f"[green]✓[/green] Generated run ID (UTC): {timestamp}")

    # Create directory structure
    data_dir = project_root / "data" / timestamp
    opendc_dir = data_dir / "opendc"

    try:
        opendc_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created directory: {opendc_dir.relative_to(project_root)}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to create directories: {e}")
        raise typer.Exit(code=1) from e

    # Save run ID to file for docker-compose
    run_id_file = get_run_id_file()
    try:
        run_id_file.write_text(timestamp)
        console.print(f"[green]✓[/green] Saved run ID to: {run_id_file.name}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to save run ID: {e}")
        raise typer.Exit(code=1) from e

    console.print("\n[bold green]Initialization complete![/bold green]")
    console.print(f"\nRun ID: [bold]{timestamp}[/bold]")
    console.print(f"Data directory: [bold]{data_dir.relative_to(project_root)}[/bold]")
    console.print("\nTo start services, run: [bold cyan]make up[/bold cyan]\n")


@app.command()
def status() -> None:
    """Show current run information."""
    console.print("\n[bold cyan]OpenDT Run Status[/bold cyan]\n")

    run_id_file = get_run_id_file()

    if not run_id_file.exists():
        console.print("[yellow]No active run found.[/yellow]")
        console.print(
            "Initialize a new run with: [bold cyan]python scripts/opendt_cli.py init[/bold cyan]\n"
        )
        return

    try:
        run_id = run_id_file.read_text().strip()
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to read run ID: {e}")
        raise typer.Exit(code=1) from e

    project_root = get_project_root()
    data_dir = project_root / "data" / run_id
    opendc_dir = data_dir / "opendc"

    # Create status table
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Run ID", run_id)
    table.add_row("Data Directory", str(data_dir.relative_to(project_root)))
    table.add_row("OpenDC Directory", str(opendc_dir.relative_to(project_root)))
    table.add_row("Directory Exists", "Yes" if opendc_dir.exists() else "No")

    # Count simulation runs
    if opendc_dir.exists():
        run_dirs = sorted(
            [d for d in opendc_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
        )
        table.add_row("Simulation Runs", str(len(run_dirs)))

        if run_dirs:
            last_run = run_dirs[-1]
            table.add_row("Latest Run", last_run.name)

            # Check for metadata
            metadata_file = last_run / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    table.add_row("Last Task Count", str(metadata.get("task_count", "N/A")))
                    table.add_row("Last Sim Time", str(metadata.get("simulated_time", "N/A")))
                except Exception:
                    pass

    console.print(table)
    console.print()


@app.command()
def clean() -> None:
    """Remove run ID file (does not delete data directories)."""
    run_id_file = get_run_id_file()

    if not run_id_file.exists():
        console.print("[yellow]No run ID file found.[/yellow]\n")
        return

    try:
        run_id = run_id_file.read_text().strip()
        run_id_file.unlink()
        console.print(f"[green]✓[/green] Removed run ID file (run: {run_id})")
        console.print("[dim]Note: Data directories were not deleted.[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to remove run ID file: {e}")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()
