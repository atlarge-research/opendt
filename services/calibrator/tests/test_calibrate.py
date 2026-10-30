"""A sweep publishes the r whose run is closest to the measured power, and keeps r if no run could be compared."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
from calibrator import main
from calibrator.main import CalibrationService

T0 = datetime(2022, 10, 7, tzinfo=UTC)
HOUR = T0 + timedelta(hours=1)
MEASURED = pd.DataFrame({"timestamp": pd.date_range(T0, HOUR, freq="60s"), "power_draw": 20000.0})


def calibrate(tmp_path, monkeypatch, simulate):
    """One sweep over r = 3, 4, 5, where `simulate(r)` is the power of r's run (None: it failed)."""

    def sweep(topologies, tasks, run_dir, simulated_time, workers):
        run_dir.mkdir(parents=True)
        return {r: simulate(r) for r in topologies}

    monkeypatch.setattr(main, "twin_time", lambda _: HOUR)
    monkeypatch.setattr(main, "sweep", sweep)
    published = []
    service = SimpleNamespace(
        output_base_dir=tmp_path,
        run_number=0,
        last_best=None,
        calibrated_property="cpuPowerModel.calibrationFactor",
        min_value=3.0,
        max_value=5.0,
        linspace_points=3,
        workers=1,
        window_minutes=60,
        topology_manager=SimpleNamespace(
            get_current_topology=lambda: "topology",
            create_variant=lambda _, r: r,
            publish_topology=published.append,
        ),
        power_tracker=SimpleNamespace(
            get_latest_timestamp=lambda: HOUR, get_power_in_window=lambda *_: MEASURED
        ),
        task_accumulator=SimpleNamespace(
            get_all_tasks=lambda: [SimpleNamespace(submission_time=t) for t in (T0, HOUR)]
        ),
    )
    CalibrationService._calibrate(service)
    return published


def test_best(tmp_path, monkeypatch):
    off = lambda r: MEASURED.assign(power_draw=20000.0 * (1 + abs(r - 4) / 10))  # noqa: E731
    assert calibrate(tmp_path, monkeypatch, off) == [4.0]


def test_no_run(tmp_path, monkeypatch):
    assert calibrate(tmp_path, monkeypatch, lambda r: None) == []
