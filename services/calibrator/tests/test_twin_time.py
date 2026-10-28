"""The calibrator calibrates at the twin's time, the end of the simulator's latest complete window."""

import json
from datetime import UTC, datetime

from calibrator.main import twin_time


def window(run_dir, n, simulated_time=None):
    folder = run_dir / "simulator" / "opendc" / f"run_{n}"
    folder.mkdir(parents=True)
    if simulated_time:  # complete
        (folder / "metadata.json").write_text(json.dumps({"simulated_time": simulated_time}))


def test_twin_time(tmp_path):
    assert twin_time(tmp_path) is None
    window(tmp_path, 9, "2022-10-07T07:05:00+00:00")
    window(tmp_path, 10, "2022-10-07T07:10:00+00:00")
    window(tmp_path, 11)  # still running
    assert twin_time(tmp_path) == datetime(2022, 10, 7, 7, 10, tzinfo=UTC)
