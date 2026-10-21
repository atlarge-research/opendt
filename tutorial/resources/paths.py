"""Paths to OpenDC, the SURF data, and the simulations' results, and a check that this computer
can run the tutorial."""

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
    results: Path  # the notebooks' simulations, precomputed (resources/precompute.py)
    output: Path  # any other simulation, once run


_root = repo_root()
PATHS = Paths(
    root=_root,
    opendc_bin=_root / "opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner",
    workload=_root / "workload/SURF",
    carbon=_root / "workload/SURF/carbon_zones",
    results=_root / "tutorial/resources/results",
    output=_root / "tutorial/resources/output",
)


def java_version() -> str | None:
    """Version of the Java that OpenDC will use, e.g. "21.0.10"; None if there is none."""
    try:
        java = Path(detect_java_home()) / "bin" / "java"
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=30)
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "([^"]+)"', out.stderr)
    return match.group(1) if match else None


def java_21(version: str | None) -> bool:
    return version is not None and int(re.match(r"\d+", version).group()) >= 21


def check_setup() -> None:
    """Check the SURF trace and the precomputed simulations; Java 21 and OpenDC run any other."""
    if not (PATHS.workload / "fragments.parquet").is_file():
        raise RuntimeError(f"The SURF workload trace is missing in {PATHS.workload}.")
    runs = len(list(PATHS.results.glob("*/DONE")))
    version = java_version()
    if java_21(version) and os.access(PATHS.opendc_bin, os.X_OK):
        others = f"Java {version} and OpenDC run any other"
    else:
        others = "any other would need Java 21 (https://adoptium.net)"
    print(f"Setup OK: SURF trace, {runs} simulations of OpenDT precomputed; {others}")
