"""Test task accumulation and frequency-based triggering."""

from datetime import UTC, datetime, timedelta

from odt_common.models import Fragment, Task
from odt_common.task_accumulator import TaskAccumulator


def test_task_accumulator_basic():
    """Test basic task accumulation."""
    accumulator = TaskAccumulator()

    # Create test tasks
    task1 = Task(
        id=1,
        submission_time=datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=1, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )

    task2 = Task(
        id=2,
        submission_time=datetime(2024, 1, 1, 22, 5, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=2, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )

    # Add tasks
    accumulator.add_task(task1)
    accumulator.add_task(task2)

    # Verify tasks are stored
    assert len(accumulator.get_all_tasks()) == 2
    assert accumulator.get_all_tasks()[0].id == 1
    assert accumulator.get_all_tasks()[1].id == 2


def test_should_simulate_first_run():
    """The first simulation runs once a window (the frequency) has passed since the first task."""
    accumulator = TaskAccumulator()
    frequency = timedelta(minutes=15)

    # Add a task
    task = Task(
        id=1,
        submission_time=datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=1, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )
    accumulator.add_task(task)

    # a heartbeat within the first window does not trigger it; the one at its end does
    assert (
        accumulator.should_simulate(datetime(2024, 1, 1, 22, 1, 0, tzinfo=UTC), frequency) is False
    )
    assert (
        accumulator.should_simulate(datetime(2024, 1, 1, 22, 15, 0, tzinfo=UTC), frequency) is True
    )


def test_should_simulate_frequency_based():
    """Test frequency-based simulation triggering."""
    accumulator = TaskAccumulator()
    frequency = timedelta(minutes=15)

    # Add task and simulate first time
    task = Task(
        id=1,
        submission_time=datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=1, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )
    accumulator.add_task(task)

    first_sim_time = datetime(2024, 1, 1, 22, 15, 0, tzinfo=UTC)
    assert accumulator.should_simulate(first_sim_time, frequency) is True
    accumulator.update_simulation_time(first_sim_time)

    # Heartbeat at 22:24 (9 minutes after) - should NOT trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 24, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is False

    # Heartbeat at 22:30 (15 minutes after) - should trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 30, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is True
    accumulator.update_simulation_time(heartbeat_time)

    # Heartbeat at 22:34 (4 minutes after last sim) - should NOT trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 34, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is False

    # Heartbeat at 22:45 (15 minutes after last sim) - should trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 45, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is True


def test_no_simulation_without_tasks():
    """Test that simulation is not triggered without tasks."""
    accumulator = TaskAccumulator()
    frequency = timedelta(minutes=15)

    # No tasks added
    heartbeat_time = datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is False


def test_task_accumulation_ordering():
    """Test that tasks maintain chronological order."""
    accumulator = TaskAccumulator()

    times = [
        datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
        datetime(2024, 1, 1, 22, 5, 0, tzinfo=UTC),
        datetime(2024, 1, 1, 22, 10, 0, tzinfo=UTC),
    ]

    for i, time in enumerate(times):
        task = Task(
            id=i + 1,
            submission_time=time,
            duration=5000,
            cpu_count=4,
            cpu_capacity=2400.0,
            mem_capacity=8000,
            fragments=[Fragment(id=i + 1, duration=5000, cpu_count=4, cpu_usage=50.0)],
        )
        accumulator.add_task(task)

    tasks = accumulator.get_all_tasks()
    assert len(tasks) == 3
    assert tasks[0].submission_time == times[0]
    assert tasks[1].submission_time == times[1]
    assert tasks[2].submission_time == times[2]


def test_multiple_simulations():
    """Test multiple simulation cycles."""
    accumulator = TaskAccumulator()
    frequency = timedelta(minutes=15)

    # Add initial task
    task1 = Task(
        id=1,
        submission_time=datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=1, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )
    accumulator.add_task(task1)

    # First simulation, at the end of the first window
    sim_time_1 = datetime(2024, 1, 1, 22, 15, 0, tzinfo=UTC)
    assert accumulator.should_simulate(sim_time_1, frequency) is True
    accumulator.update_simulation_time(sim_time_1)
    assert len(accumulator.get_all_tasks()) == 1

    # Add more tasks
    task2 = Task(
        id=2,
        submission_time=datetime(2024, 1, 1, 22, 10, 0, tzinfo=UTC),
        duration=5000,
        cpu_count=4,
        cpu_capacity=2400.0,
        mem_capacity=8000,
        fragments=[Fragment(id=2, duration=5000, cpu_count=4, cpu_usage=50.0)],
    )
    accumulator.add_task(task2)

    # Second simulation (after 15 minutes)
    sim_time_2 = datetime(2024, 1, 1, 22, 30, 0, tzinfo=UTC)
    assert accumulator.should_simulate(sim_time_2, frequency) is True
    accumulator.update_simulation_time(sim_time_2)
    assert len(accumulator.get_all_tasks()) == 2  # Accumulates all tasks
