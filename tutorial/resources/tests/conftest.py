"""Test configuration for the OpenDT tutorial helper package."""

import dataclasses
import sys
from pathlib import Path

import pytest

TUTORIAL_DIR = Path(__file__).resolve().parents[2]
REPO = TUTORIAL_DIR.parent

if str(TUTORIAL_DIR) not in sys.path:
    sys.path.insert(0, str(TUTORIAL_DIR))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "opendc: runs the bundled OpenDC simulator (needs Java 21+)")
    config.addinivalue_line("markers", "notebooks: executes tutorial notebooks (needs nbclient)")
    config.addinivalue_line("markers", "network: needs internet access")


@pytest.fixture(autouse=True, scope="session")
def fresh_simulation_cache(tmp_path_factory):
    """Run OpenDC for real instead of reusing the shipped results (resources/results/) or the local
    cache (resources/output/)."""
    from resources import sim

    empty = dataclasses.replace(
        sim.PATHS,
        output=tmp_path_factory.mktemp("output"),
        results=tmp_path_factory.mktemp("results"),
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sim, "PATHS", empty)
        yield
