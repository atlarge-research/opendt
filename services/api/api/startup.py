"""While the twin starts: the step it is at, and facts to read meanwhile, from SURF's week (workload/SURF) and the
OpenDT paper (ICPE Companion '26), none of them an answer to a tutorial question."""

import random
from pathlib import Path

from api import twin

STEPS = [
    "The services start: Kafka, the replay, the simulator, and the calibrator",
    "dc-mock replays SURF's jobs and power; the simulator collects the first 5 minutes",
    "OpenDC simulates the first 5 minutes of the trace",
]
TIPS = [
    "In one week, SURF's datacenter runs 7,850 jobs.",
    "Half of the jobs end within 48 seconds; the longest one runs for 5 days.",
    "82% of the jobs end within an hour.",
    "Thursday is the busiest day: 2,259 jobs, more than a quarter of the week.",
    "At 15:00 on Thursday, 902 jobs arrive within a single hour.",
    "Together, the jobs take 310,238 CPU-hours: a single core would need 35 years.",
    "Over the week, the datacenter uses 3,644 kWh of electricity.",
    "OpenDT twins 7 days of datacenter operation within 46 minutes, on a common machine.",
    "OpenDT builds on OpenDC, an open-source datacenter simulator.",
    "OpenDT's data source, simulator, calibrator, and API talk through Apache Kafka.",
    "Every 5 minutes of operation, OpenDT simulates the trace again, from its start.",
]


def progress(run: Path, now: float) -> list[dict]:
    """The step of the start, as one row, with a tip picked at random every 15 s, time to read it; no rows once a
    window is complete."""
    if twin.windows(run):
        return []
    simulator = run / "simulator"
    step = 3 if (simulator / "opendc" / "run_1").exists() else 2 if simulator.exists() else 1
    tip = random.Random(int(now // 15)).choice(TIPS)
    return [{"step": step, "steps": len(STEPS), "doing": STEPS[step - 1], "tip": tip}]
