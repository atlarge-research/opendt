"""While the twin starts: the step it is at, and facts from the OpenDT paper (ICPE Companion '26) to read
meanwhile, none of them an answer to a tutorial question."""

from pathlib import Path

from api import twin

STEPS = [
    "The services start: Kafka, the replay, the simulator, and the calibrator",
    "dc-mock replays SURF's jobs and power; the simulator collects the first 5 minutes",
    "OpenDC simulates the first 5 minutes of the trace",
]
TIPS = [
    "SURF-SARA has 277 hosts, each with 16 cores at up to 2.1 GHz and 128 GB of RAM.",
    "The jobs of SURF-22, a scientific workload trace, take 39.52 CPU-hours on average.",
    "OpenDT twins 7 days of datacenter operation within 46 minutes, on a common machine.",
    "A twin should stay within a 10% error rate (community-accepted) at 90% or more of the operational time.",
    "The simulator and the calibrator run in parallel: calibrating never blocks a simulation.",
    "OpenDT's data source, simulator, calibrator, and API talk through Apache Kafka.",
    "OpenDT builds on OpenDC, an open-source datacenter simulator.",
    "Each window of operation, OpenDT simulates the trace from its start with the topology of that moment.",
]


def progress(run: Path, now: float) -> list[dict]:
    """The step of the start, as one row, with a new tip every 10 s; no rows once a window is complete."""
    if twin.windows(run):
        return []
    simulator = run / "simulator"
    step = 3 if (simulator / "opendc" / "run_1").exists() else 2 if simulator.exists() else 1
    tip = TIPS[int(now // 10) % len(TIPS)]
    return [{"step": step, "steps": len(STEPS), "doing": STEPS[step - 1], "tip": tip}]
