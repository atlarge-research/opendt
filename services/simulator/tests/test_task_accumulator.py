"""Test task accumulation and frequency-based triggering."""

from datetime import UTC, datetime, timedelta

import pytest
from odt_common.models import CPU, Cluster, CPUPowerModel, Fragment, Host, Memory, Task, Topology

# Import the TaskAccumulator from main.py
import sys
from pathlib import Path

# Add parent directory to path to import from main
sys.path.insert(0, str(Path(__file__).parent.parent))
from simulator.main import TaskAccumulator


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
    """Test that first simulation is triggered when tasks are available."""
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
    
    # First heartbeat after task should trigger simulation
    heartbeat_time = datetime(2024, 1, 1, 22, 1, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is True


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
    
    first_sim_time = datetime(2024, 1, 1, 22, 1, 0, tzinfo=UTC)
    assert accumulator.should_simulate(first_sim_time, frequency) is True
    accumulator.update_simulation_time(first_sim_time)
    
    # Heartbeat at 22:10 (9 minutes after) - should NOT trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 10, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is False
    
    # Heartbeat at 22:16 (15 minutes after) - should trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 16, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is True
    accumulator.update_simulation_time(heartbeat_time)
    
    # Heartbeat at 22:20 (4 minutes after last sim) - should NOT trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 20, 0, tzinfo=UTC)
    assert accumulator.should_simulate(heartbeat_time, frequency) is False
    
    # Heartbeat at 22:31 (15 minutes after last sim) - should trigger
    heartbeat_time = datetime(2024, 1, 1, 22, 31, 0, tzinfo=UTC)
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
    
    # First simulation
    sim_time_1 = datetime(2024, 1, 1, 22, 1, 0, tzinfo=UTC)
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
    sim_time_2 = datetime(2024, 1, 1, 22, 16, 0, tzinfo=UTC)
    assert accumulator.should_simulate(sim_time_2, frequency) is True
    accumulator.update_simulation_time(sim_time_2)
    assert len(accumulator.get_all_tasks()) == 2  # Accumulates all tasks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
