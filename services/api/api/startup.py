"""While the twin starts: the step it is at, and tips to read meanwhile, on the screens and on OpenDT (from its
paper, ICPE Companion '26), none tied to a workload and none an answer to a tutorial question."""

import random
from pathlib import Path

from api import twin

STEPS = [
    "The services start: Kafka, the replay, the simulator, and the calibrator",
    "The replay sends SURF's jobs and the datacenter's telemetry on power draw (ground truth); the simulator "
    "collects the first 5 minutes",
    "OpenDC simulates the first 5 minutes of the trace",
]
TIPS = [
    "Click a box on top (Datacenter, Grid, Twin, Self-calibrator) to change the twin; nothing changes before Apply.",
    "A change pulses, old → new, until the twin follows it.",
    "Hover the triangle under a dashed line, on a plot, to see the decision it marks.",
    "Week, Day, and 6 h set how much of the trace the plots show.",
    "☰ Plots picks the plots the Dashboard shows.",
    "☀ and ☾, next to the twin's time, switch between the light and the dark theme.",
    "In the Decisions log, Automatic changes come from the self-calibrator, Manual ones from the operator.",
    "Infrastructure →, in the Datacenter box, opens the Topology screen, with the hardware of the hosts.",
    "Stuck on a Tutorial question? Each one has a Hint and a Solution.",
    "OpenDT builds on OpenDC, an open-source datacenter simulator.",
    "OpenDT's data source, simulator, calibrator, and API talk through Apache Kafka.",
    "Every 5 minutes of operation, OpenDT simulates the trace again, from its start.",
    "OpenDT recalibrates its predictions in real time, from the difference between prediction and measurement.",
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
