"""The calibration's sweep: one OpenDC run per value of the calibrated property, in threads (each run is a
JVM of its own, so they share one copy of the tasks)."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
from odt_common.models import Task, Topology
from odt_common.odc_runner import OpenDCRunner

logger = logging.getLogger(__name__)


def power(
    topology: Topology, tasks: list[Task], sim_dir: Path, number: int, simulated_time: datetime
) -> pd.DataFrame | None:
    """The power OpenDC simulates for `topology` (timestamp, power_draw); None if the run fails."""
    try:
        ok, output_dir = OpenDCRunner().run_simulation(
            tasks=tasks,
            topology=topology,
            run_dir=sim_dir,
            run_number=number,
            simulated_time=simulated_time,
            timeout_seconds=120,
        )
        if not ok:
            return None
        df = pd.read_parquet(next(output_dir.rglob("powerSource.parquet")))
        df["timestamp"] = pd.to_datetime(df["timestamp_absolute"], unit="ms", utc=True)
        return df[["timestamp", "power_draw"]]
    except Exception as e:
        logger.error(f"Simulation {number} failed: {e}", exc_info=True)
        return None


def sweep(
    topologies: dict[float, Topology],
    tasks: list[Task],
    run_dir: Path,
    simulated_time: datetime,
    workers: int,
) -> dict[float, pd.DataFrame | None]:
    """The power of each topology, by its value of the calibrated property, from `workers` OpenDC runs at
    a time, each in run_dir/sim_<i>."""
    values = list(topologies)
    with ThreadPoolExecutor(workers) as pool:
        powers = pool.map(
            lambda i: power(topologies[values[i]], tasks, run_dir / f"sim_{i}", i, simulated_time),
            range(len(values)),
        )
        return dict(zip(values, powers, strict=True))
