"""The simulator's results: the power of each window of operation, appended to agg_results.parquet."""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# what the API reads, from OpenDC's powerSource.parquet and the window's run
COLUMNS = [
    "timestamp",
    "run_number",
    "power_draw",
    "energy_usage",
    "carbon_intensity",
    "carbon_emission",
    "cached",
]


def save(df: pd.DataFrame, path: Path) -> None:
    """Whole or not at all: the API reads the file while the simulator writes it."""
    part = path.with_suffix(".part")
    df.to_parquet(part, index=False)
    part.replace(path)


class SimulationResultProcessor:
    """Appends the power rows of each window to agg_results.parquet."""

    def __init__(self, simulator_output_dir: Path):
        self.agg_results_file = Path(simulator_output_dir) / "agg_results.parquet"
        self.last_processed_time: datetime | None = None
        if self.agg_results_file.exists():  # a restarted simulator goes on after the rows it wrote
            stored = pd.read_parquet(self.agg_results_file, columns=["timestamp"])
            self.last_processed_time = stored["timestamp"].max().to_pydatetime()

    def process_simulation_results(
        self,
        run_number: int,
        output_dir: Path,
        aligned_simulated_time: datetime,
        cached: bool = False,
    ) -> None:
        """Append the rows of the window that ends at `aligned_simulated_time` and come after those
        appended before, as each window's OpenDC run simulates from the trace's start."""
        df = pd.read_parquet(next(output_dir.rglob("powerSource.parquet")))
        df["timestamp"] = pd.to_datetime(df["timestamp_absolute"], unit="ms", utc=True)
        new = df["timestamp"] <= aligned_simulated_time
        if self.last_processed_time is not None:
            new &= df["timestamp"] > self.last_processed_time
        df = df[new].assign(run_number=run_number, cached=cached)[COLUMNS]
        if df.empty:
            return
        self.last_processed_time = df["timestamp"].max().to_pydatetime()
        if self.agg_results_file.exists():
            df = pd.concat([pd.read_parquet(self.agg_results_file), df], ignore_index=True)
        save(df, self.agg_results_file)
        logger.info(f"Run {run_number}: {new.sum()} rows appended, {len(df)} in all")
