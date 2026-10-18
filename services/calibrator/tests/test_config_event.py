"""The calibrator runs as many simulations in parallel as the control panel sets."""

from types import SimpleNamespace

from calibrator.calibration_engine import CalibrationEngine
from calibrator.main import CalibrationService


def follow(setting, value):
    service = SimpleNamespace(calibration_engine=CalibrationEngine(max_workers=4))
    CalibrationService._process_config_event(service, {"setting_key": setting, "new_value": value})
    return service.calibration_engine.max_workers


def test_follows_parallel_runs():
    assert follow("calibrator.max_parallel_workers", 2) == 2


def test_ignores_other_settings():
    assert follow("simulator.scheduler", "Random") == 4
