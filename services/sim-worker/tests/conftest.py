"""Pytest configuration and fixtures for sim-worker tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from opendt_common.models import CPU, Cluster, CPUPowerModel, Fragment, Host, Memory, Task, Topology


@pytest.fixture
def opendc_bin_path() -> Path:
    """Get the path to the OpenDC binary.

    Returns:
        Path to OpenDCExperimentRunner binary

    Raises:
        pytest.skip: If OpenDC binary is not found
    """
    # Try to find OpenDC binary in the service directory
    possible_paths = [
        Path(__file__).parent.parent
        / "opendc"
        / "bin"
        / "OpenDCExperimentRunner"
        / "bin"
        / "OpenDCExperimentRunner",
        Path("/app/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner"),
    ]

    for path in possible_paths:
        if path.exists():
            return path

    pytest.skip("OpenDC binary not found. Please ensure OpenDC binaries are available for testing.")


@pytest.fixture
def simple_task() -> Task:
    """Create a single simple task for testing."""
    base_time = datetime(2022, 10, 7, 0, 0, 0, tzinfo=UTC)

    return Task(
        id=1,
        submission_time=base_time,
        duration=5000,  # 5 seconds
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[
            Fragment(
                id=1,
                duration=5000,
                cpu_count=4,
                cpu_usage=50.0,
            )
        ],
    )


@pytest.fixture
def simple_topology() -> Topology:
    """Create a minimal topology for testing."""
    return Topology(
        clusters=[
            Cluster(
                name="test-cluster",
                hosts=[
                    Host(
                        count=1,
                        name="test-host",
                        memory=Memory(memorySize=32000),
                        cpu=CPU(coreCount=8, coreSpeed=2400),
                        cpuPowerModel=CPUPowerModel(
                            modelType="asymptotic",
                            power=200.0,
                            idlePower=50.0,
                            maxPower=250.0,
                            asymUtil=0.5,
                        ),
                    )
                ],
            )
        ]
    )


@pytest.fixture
def base_time() -> datetime:
    """Get a base timestamp for testing.

    Returns:
        A fixed datetime for reproducible tests
    """
    return datetime(2024, 1, 1, 0, 0, 0)
