"""Task accumulation for simulation services.

Accumulates tasks chronologically and determines when simulations should be triggered
based on frequency intervals.
"""

import logging
from datetime import datetime, timedelta

from odt_common.models import Task

logger = logging.getLogger(__name__)


class TaskAccumulator:
    """Accumulates tasks chronologically for simulation."""

    def __init__(self) -> None:
        """Initialize the task accumulator."""
        self.tasks: list[Task] = []
        self.last_simulation_time: datetime | None = None
        self.first_task_time: datetime | None = None

    def add_task(self, task: Task) -> None:
        """Add a task to the accumulator.

        Args:
            task: Task to add
        """
        self.tasks.append(task)

        # Track the first task's submission time (rounded down to whole minutes)
        if self.first_task_time is None:
            # Round down to whole minutes
            rounded_time = task.submission_time.replace(second=0, microsecond=0)
            self.first_task_time = rounded_time
            logger.info(f"First task received at {task.submission_time}, rounded to {rounded_time}")

        logger.debug(f"Added task {task.id}, total tasks: {len(self.tasks)}")

    def should_simulate(self, heartbeat_time: datetime, frequency: timedelta) -> bool:
        """Check if simulation should be triggered.

        Args:
            heartbeat_time: Current heartbeat timestamp
            frequency: Simulation frequency

        Returns:
            True if enough time has elapsed since last simulation
        """
        if len(self.tasks) == 0:
            return False

        if self.last_simulation_time is None:
            # First simulation: trigger after frequency interval from first task
            if self.first_task_time is None:
                return False

            next_simulation_time = self.first_task_time + frequency
            should_run = heartbeat_time >= next_simulation_time

            if should_run:
                logger.info(
                    f"First simulation triggered: heartbeat={heartbeat_time}, "
                    f"first_task={self.first_task_time}, frequency={frequency}"
                )

            return should_run

        time_since_last = heartbeat_time - self.last_simulation_time
        return time_since_last >= frequency

    def get_next_simulation_time(self, frequency: timedelta) -> datetime | None:
        """Calculate the next aligned simulation time.

        This returns the exact time when the simulation should be considered to have run,
        aligned to the frequency intervals.

        Args:
            frequency: Simulation frequency

        Returns:
            Next aligned simulation time, or None if not ready
        """
        if self.last_simulation_time is None:
            # First simulation: first_task_time + frequency
            if self.first_task_time is None:
                return None
            return self.first_task_time + frequency
        else:
            # Subsequent simulations: last_simulation_time + frequency
            return self.last_simulation_time + frequency

    def get_all_tasks(self) -> list[Task]:
        """Get all accumulated tasks.

        Returns:
            List of all tasks
        """
        return self.tasks.copy()

    def update_simulation_time(self, simulation_time: datetime) -> None:
        """Update the last simulation time.

        Args:
            simulation_time: Timestamp of the simulation
        """
        self.last_simulation_time = simulation_time
