"""Test contiguous window behavior."""

from datetime import UTC, datetime

import pytest
from opendt_common.models import CPU, Cluster, CPUPowerModel, Fragment, Host, Memory, Task, Topology
from sim_worker.window_manager import WindowManager


@pytest.fixture
def sample_topology() -> Topology:
    """Create a sample topology for testing."""
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


def test_contiguous_windows_basic(sample_topology):
    """Test that windows are created contiguously.

    If first task at 22:00:03, window should be 22:00-22:05.
    If next task at 22:31, windows should be created for:
    - 22:00-22:05 (has task)
    - 22:05-22:10 (empty, closed)
    - 22:10-22:15 (empty, closed)
    - 22:15-22:20 (empty, closed)
    - 22:20-22:25 (empty, closed)
    - 22:25-22:30 (empty, closed)
    - 22:30-22:35 (has task, open)
    """
    wm = WindowManager(window_size_minutes=5)
    closed_windows = []

    def on_window_closed(window):
        closed_windows.append(window)

    wm.register_window_closed_callback(on_window_closed)

    # First task at 22:00:03
    task1 = Task(
        id=1,
        submission_time=datetime(2024, 1, 1, 22, 0, 3, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=1, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )

    wm.add_task(task1)

    # Should have created window 0 (22:00-22:05)
    assert 0 in wm.windows
    assert wm.windows[0].window_start == datetime(2024, 1, 1, 22, 0, tzinfo=UTC)
    assert wm.windows[0].window_end == datetime(2024, 1, 1, 22, 5, tzinfo=UTC)
    assert len(wm.windows[0].tasks) == 1
    assert not wm.windows[0].is_closed

    # Second task at 22:31 - should create and close windows 0-5, create window 6
    task2 = Task(
        id=2,
        submission_time=datetime(2024, 1, 1, 22, 31, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=2, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )

    wm.add_task(task2)

    # Should have created windows 0-6
    assert len(wm.windows) == 7, f"Expected 7 windows, got {len(wm.windows)}"

    # Window 0 (22:00-22:05) - closed, has 1 task
    assert wm.windows[0].is_closed
    assert len(wm.windows[0].tasks) == 1

    # Windows 1-5 (22:05-22:30) - closed, empty
    for i in range(1, 6):
        assert i in wm.windows, f"Window {i} should exist"
        assert wm.windows[i].is_closed, f"Window {i} should be closed"
        assert len(wm.windows[i].tasks) == 0, f"Window {i} should be empty"

    # Window 6 (22:30-22:35) - open, has 1 task
    assert 6 in wm.windows
    assert not wm.windows[6].is_closed
    assert len(wm.windows[6].tasks) == 1

    # Check window time ranges
    for i in range(7):
        expected_start = datetime(2024, 1, 1, 22, 0, tzinfo=UTC).replace(minute=i * 5)
        expected_end = expected_start.replace(minute=(i + 1) * 5)
        assert wm.windows[i].window_start == expected_start
        assert wm.windows[i].window_end == expected_end

    # Check that 6 windows were closed via callback (windows 0-5)
    # Note: order might vary (intermediate windows closed during creation, window 0 closed by add_task)
    assert len(closed_windows) == 6
    closed_window_ids = sorted([w.window_id for w in closed_windows])
    assert closed_window_ids == [0, 1, 2, 3, 4, 5]

    print("✅ Contiguous windows test passed!")
    print(f"   Created {len(wm.windows)} windows total")
    print(f"   Closed {len(closed_windows)} windows")
    print("   Windows 0-5 closed, window 6 open")


def test_empty_windows_are_simulated(sample_topology):
    """Test that empty windows still trigger simulation callbacks."""
    wm = WindowManager(window_size_minutes=5)
    closed_windows = []

    def on_window_closed(window):
        closed_windows.append(window)

    wm.register_window_closed_callback(on_window_closed)

    # Task at 22:00
    task1 = Task(
        id=1,
        submission_time=datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=1, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )
    wm.add_task(task1)

    # Task at 22:15 - should close windows 0, 1, 2 and create window 3
    task2 = Task(
        id=2,
        submission_time=datetime(2024, 1, 1, 22, 15, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=2, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )
    wm.add_task(task2)

    # Should have windows 0-3
    assert len(wm.windows) == 4

    # Window 0 has task, windows 1-2 are empty
    assert len(wm.windows[0].tasks) == 1
    assert len(wm.windows[1].tasks) == 0
    assert len(wm.windows[2].tasks) == 0
    assert len(wm.windows[3].tasks) == 1

    # All except window 3 should be closed
    assert wm.windows[0].is_closed
    assert wm.windows[1].is_closed
    assert wm.windows[2].is_closed
    assert not wm.windows[3].is_closed

    # Callbacks should have been triggered for windows 0, 1, 2
    assert len(closed_windows) == 3

    print("✅ Empty windows simulation test passed!")
    print(f"   Window 0: {len(wm.windows[0].tasks)} task(s)")
    print(f"   Window 1: {len(wm.windows[1].tasks)} task(s) (empty)")
    print(f"   Window 2: {len(wm.windows[2].tasks)} task(s) (empty)")
    print(f"   Window 3: {len(wm.windows[3].tasks)} task(s)")
