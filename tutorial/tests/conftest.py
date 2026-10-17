"""Test configuration for the OpenDT tutorial helper package."""

import sys
from pathlib import Path

import pytest

TUTORIAL_DIR = Path(__file__).resolve().parents[1]
REPO = TUTORIAL_DIR.parent

if str(TUTORIAL_DIR) not in sys.path:
    sys.path.insert(0, str(TUTORIAL_DIR))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "opendc: runs the bundled OpenDC simulator (needs Java 21+)")
    config.addinivalue_line("markers", "notebooks: executes tutorial notebooks (needs nbclient)")
    config.addinivalue_line("markers", "network: needs internet access")
