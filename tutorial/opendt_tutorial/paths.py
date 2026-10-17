"""Paths to OpenDC and the SURF data, and a check that this computer can run the tutorial."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from odt_common.odc_runner.java_home import detect_java_home


def repo_root(start: Path | None = None) -> Path:
    """The OpenDT checkout: the first parent folder that contains `opendc/` and `workload/`.

    Starts from this file, not the working directory, so notebooks work wherever they are opened from.
    """
    here = (start or Path(__file__)).resolve()
    for folder in (here, *here.parents):
        if (folder / "opendc").is_dir() and (folder / "workload").is_dir():
            return folder
    raise RuntimeError(
        f"No OpenDT checkout found above {here}. Open the notebooks from your OpenDT folder."
    )


@dataclass(frozen=True)
class Paths:
    root: Path
    opendc_bin: Path
    workload: Path
    carbon: Path
    output: Path


_root = repo_root()
PATHS = Paths(
    root=_root,
    opendc_bin=_root / "opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner",
    workload=_root / "workload/SURF",
    carbon=_root / "tutorial/carbon_traces",
    output=_root / "tutorial/output",
)


def _java_version() -> str | None:
    """Version of the Java that OpenDC will use, e.g. "21.0.10"; None if there is none."""
    try:
        java = Path(detect_java_home()) / "bin" / "java"
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=30)
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "([^"]+)"', out.stderr)
    return match.group(1) if match else None


def check_setup() -> None:
    """Check Java 21, OpenDC and the SURF trace; raise RuntimeError saying what to fix."""
    version = _java_version()
    if version is None or int(re.match(r"\d+", version).group()) < 21:
        raise RuntimeError(
            f"OpenDC needs Java 21 or newer (found: {version or 'none'}). "
            "Use the Codespace, or install Java 21 (https://adoptium.net) and set JAVA_HOME."
        )
    if not os.access(PATHS.opendc_bin, os.X_OK):
        raise RuntimeError(
            f"The OpenDC launcher is missing or not executable. Run: chmod +x {PATHS.opendc_bin}"
        )
    if not (PATHS.workload / "fragments.parquet").is_file():
        raise RuntimeError(f"The SURF workload trace is missing in {PATHS.workload}.")
    print(f"Setup OK: Java {version}, OpenDC, SURF trace, {os.cpu_count()} CPU cores")
