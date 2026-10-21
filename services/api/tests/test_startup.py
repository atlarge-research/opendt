"""While the twin starts: the step it is at, then nothing once its first window is complete."""

from api import startup


def step(run_dir):
    [row] = startup.progress(run_dir, now=0)
    return row["step"]


def test_steps(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    assert step(run) == 1  # the services start
    (run / "simulator").mkdir()
    assert step(run) == 2  # the replay, until the first window
    (run / "simulator" / "opendc" / "run_1").mkdir(parents=True)
    assert step(run) == 3  # OpenDC runs it


def test_ready(run_dir):
    assert startup.progress(run_dir, now=0) == []


def test_all_tips(tmp_path):
    tips = {startup.progress(tmp_path, now=10 * i)[0]["tip"] for i in range(200)}
    assert tips == set(startup.TIPS)
