"""OpenDT Dashboard Service."""

__version__ = "0.1.0"

import os
from pathlib import Path


def data_dir() -> Path:
    """The data folder: each run's folder, and the prefabs."""
    return Path(os.getenv("DATA_DIR", "/app/data"))
