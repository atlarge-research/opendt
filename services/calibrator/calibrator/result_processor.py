"""What the calibrator writes per sweep, next to its OpenDC runs: the sweep's metadata.json, and one row of
agg_results.parquet."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def last_best(output_dir: Path) -> float | None:
    """The best value of the last sweep, so a restarted calibrator does not publish it again."""
    path = output_dir / "agg_results.parquet"
    return float(pd.read_parquet(path)["best_value"].iloc[-1]) if path.exists() else None


def record(
    output_dir: Path,
    run_dir: Path,
    run_number: int,
    end: datetime,
    start: datetime | None,
    task_count: int,
    mapes: dict[float, float],
    calibrated_property: str,
    best: float,
    changed: bool,
) -> None:
    """The sweep `run_number`: its MAPE [%] per value, over the window from `start` to `end`, and the best
    value, `changed` if it was published."""
    metadata = {
        "run_number": run_number,
        "task_count": task_count,
        "wall_clock_time": datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat(),
        "window": {"start": start.isoformat() if start else None, "end": end.isoformat()},
        "mape_values": {f"{value:.2f}": round(m, 2) for value, m in mapes.items()},
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    row = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([end], utc=True),
            "run_number": [run_number],
            "calibrated_property": [calibrated_property],
            "best_value": [round(best, 2)],
            "best_mape": [round(mapes[best], 2)],
            "topology_changed": [changed],
            "task_count": [task_count],
        }
    )
    path = output_dir / "agg_results.parquet"
    if path.exists():
        row = pd.concat([pd.read_parquet(path), row], ignore_index=True)
    row.to_parquet(path, index=False)
