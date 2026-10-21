"""The calibrator follows its settings from the control panel: on or off, and how it calibrates."""

from types import SimpleNamespace

import pytest
from calibrator.calibration_engine import CalibrationEngine
from calibrator.main import CalibrationService
from calibrator.mape_comparator import MapeComparator


def follow(setting, value):
    service = SimpleNamespace(
        enabled=True,
        min_value=3.0,
        max_value=9.0,
        linspace_points=7,
        calibration_engine=CalibrationEngine(max_workers=4),
        mape_comparator=MapeComparator(mape_window_minutes=60),
    )
    CalibrationService._process_config_event(service, {"setting_key": setting, "new_value": value})
    return service


@pytest.mark.parametrize(
    "setting, value, read",
    [
        ("calibrator.enabled", False, lambda s: s.enabled),
        ("calibrator.max_parallel_workers", 2, lambda s: s.calibration_engine.max_workers),
        ("calibrator.min_value", 4.0, lambda s: s.min_value),
        ("calibrator.max_value", 12.0, lambda s: s.max_value),
        ("calibrator.linspace_points", 10, lambda s: s.linspace_points),
        (
            "calibrator.mape_window_minutes",
            1440,
            lambda s: s.mape_comparator.mape_window.total_seconds() / 60,
        ),
    ],
)
def test_follows(setting, value, read):
    assert read(follow(setting, value)) == value


def test_ignores_other_settings():
    assert follow("simulator.scheduler", "Random").calibration_engine.max_workers == 4
