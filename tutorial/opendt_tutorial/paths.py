"""Where things live, and a one-call check that this machine can run the tutorial."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MIN_JAVA = 21


class SetupError(RuntimeError):
    """The tutorial cannot run on this machine; the message says what to do."""


def repo_root(start: Path | None = None) -> Path:
    """Return the OpenDT repository root: the first parent containing `opendc/` and `workload/`.

    Notebooks run with their own folder as working directory, so this starts from
    this file (or `start`), never from the current working directory.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "opendc").is_dir() and (candidate / "workload").is_dir():
            return candidate
    raise SetupError(
        f"Could not find the OpenDT repository above {here}. "
        "Open the notebooks from inside your OpenDT checkout (the tutorial/ folder)."
    )


@dataclass(frozen=True)
class Paths:
    root: Path
    opendc_bin: Path
    workload: Path
    carbon: Path
    output: Path


def _paths() -> Paths:
    root = repo_root()
    return Paths(
        root=root,
        opendc_bin=root / "opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner",
        workload=root / "workload/SURF",
        carbon=root / "tutorial/carbon_traces",
        output=root / "tutorial/output",
    )


PATHS = _paths()


def _java_version() -> str | None:
    """Version string of the Java that OpenDC will use (e.g. "21.0.10"), or None if none is found."""
    from odt_common.odc_runner.java_home import detect_java_home

    try:
        java = Path(detect_java_home()) / "bin" / "java"
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=30)
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "([^"]+)"', out.stderr + out.stdout)
    return match.group(1) if match else None


def _java_major(version: str) -> int:
    parts = version.split(".")
    return int(parts[1]) if parts[0] == "1" else int(re.match(r"\d+", parts[0]).group())


def check_setup(verbose: bool = True) -> None:
    """Check Java, the OpenDC binary and the data; print one line per check.

    Raises SetupError with an actionable message for the first problem found.
    """
    checks: list[tuple[bool, str, str]] = []

    version = _java_version()
    java_ok = version is not None and _java_major(version) >= MIN_JAVA
    checks.append(
        (
            java_ok,
            f"Java {version}" if version else "Java",
            f"Java {MIN_JAVA} or newer is required (found: {version or 'none'}). "
            "Use the Codespace, or install Java 21 (e.g. https://adoptium.net) and set JAVA_HOME.",
        )
    )

    bin_ok = PATHS.opendc_bin.is_file() and os.access(PATHS.opendc_bin, os.X_OK)
    checks.append(
        (
            bin_ok,
            "OpenDC simulator",
            f"The OpenDC launcher is missing or not executable: {PATHS.opendc_bin}. "
            f"Run: chmod +x {PATHS.opendc_bin}",
        )
    )

    needed = ("tasks.parquet", "fragments.parquet", "consumption.parquet", "topology.json")
    data_ok = all((PATHS.workload / name).is_file() for name in needed)
    checks.append(
        (data_ok, "SURF workload trace", f"SURF workload files are missing in {PATHS.workload}.")
    )

    carbon_ok = PATHS.carbon.is_dir() and any(PATHS.carbon.glob("*.parquet"))
    checks.append((carbon_ok, "Carbon-intensity traces", f"Carbon traces are missing in {PATHS.carbon}."))

    if verbose:
        for ok, label, _ in checks:
            print(f"{'✅' if ok else '❌'} {label}")
        print(f"ℹ️  CPU cores available: {os.cpu_count()}")

    for ok, _, message in checks:
        if not ok:
            raise SetupError(message)
