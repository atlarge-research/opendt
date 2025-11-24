"""Time window manager for aggregating tasks into simulation windows."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from opendt_common.models import Task, Topology, TopologySnapshot

logger = logging.getLogger(__name__)


@dataclass
class TimeWindow:
    """Represents a fixed time window for task aggregation.

    Windows are closed when:
    - A task arrives with submission_time >= window_end
    - The window is explicitly closed
    """

    window_id: int
    window_start: datetime
    window_end: datetime
    tasks: list[Task] = field(default_factory=list)
    topology: Topology | None = None
    is_closed: bool = False

    def add_task(self, task: Task) -> bool:
        """Add a task to this window.

        Args:
            task: Task to add

        Returns:
            True if task was added, False if task is outside window bounds
        """
        if self.is_closed:
            logger.warning(f"Attempted to add task to closed window {self.window_id}")
            return False

        if task.submission_time < self.window_start:
            logger.warning(
                f"Task {task.id} submission time {task.submission_time} "
                f"is before window start {self.window_start}"
            )
            return False

        if task.submission_time >= self.window_end:
            return False

        self.tasks.append(task)
        return True

    def update_topology(self, topology: Topology) -> None:
        """Update the topology for this window.

        Args:
            topology: New topology to use
        """
        self.topology = topology
        logger.debug(f"Updated topology for window {self.window_id}")

    def close(self) -> None:
        """Mark this window as closed and ready for processing."""
        if not self.is_closed:
            self.is_closed = True
            logger.info(
                f"🔒 Closed window {self.window_id} "
                f"[{self.window_start} - {self.window_end}] "
                f"with {len(self.tasks)} tasks"
            )

    def __repr__(self) -> str:
        return (
            f"TimeWindow(id={self.window_id}, "
            f"start={self.window_start}, end={self.window_end}, "
            f"tasks={len(self.tasks)}, closed={self.is_closed})"
        )


class WindowManager:
    """Manages time-based windowing of tasks for simulation.

    The manager:
    - Creates windows based on event time (task submission_time)
    - Aggregates tasks into appropriate windows
    - Tracks topology updates per window
    - Closes windows when new tasks arrive after window boundary
    - Maintains history of all windows for cumulative simulation
    """

    def __init__(self, window_size_minutes: int = 5) -> None:
        """Initialize the window manager.

        Args:
            window_size_minutes: Size of each window in minutes
        """
        self.window_size_minutes = window_size_minutes
        self.window_size = timedelta(minutes=window_size_minutes)

        # State
        self.windows: dict[int, TimeWindow] = {}
        self.first_task_time: datetime | None = None
        self.latest_topology: Topology | None = None

        logger.info(f"Initialized WindowManager with {window_size_minutes}-minute windows")

    def _round_down_to_minute(self, dt: datetime) -> datetime:
        """Round datetime down to the start of the minute.

        Args:
            dt: Datetime to round

        Returns:
            Datetime rounded down to start of minute (seconds/microseconds = 0)
        """
        return dt.replace(second=0, microsecond=0)

    def _create_window(self, window_id: int, start_time: datetime) -> TimeWindow:
        """Create a new time window.

        Args:
            window_id: ID for the window
            start_time: Start time of the window (should be rounded to minute)

        Returns:
            New TimeWindow instance
        """
        window_start = start_time
        window_end = window_start + self.window_size

        window = TimeWindow(
            window_id=window_id,
            window_start=window_start,
            window_end=window_end,
            topology=self.latest_topology,
        )

        self.windows[window_id] = window
        logger.info(f"📦 Created window {window_id}: [{window_start} - {window_end})")

        return window

    def _get_or_create_window_for_time(self, timestamp: datetime) -> TimeWindow:
        """Get or create the appropriate window for a given timestamp.

        Args:
            timestamp: Timestamp to find window for

        Returns:
            TimeWindow that should contain this timestamp
        """
        # Round down to minute
        rounded_time = self._round_down_to_minute(timestamp)

        # If this is the first task, initialize the first window
        if self.first_task_time is None:
            self.first_task_time = rounded_time
            return self._create_window(window_id=0, start_time=rounded_time)

        # Check if timestamp belongs to an existing window
        for window in self.windows.values():
            if window.window_start <= timestamp < window.window_end:
                return window

        # Calculate which window this timestamp belongs to
        time_since_first = timestamp - self.first_task_time
        window_index = int(time_since_first.total_seconds() // (self.window_size_minutes * 60))
        window_start = self.first_task_time + timedelta(
            minutes=window_index * self.window_size_minutes
        )

        # Create the window if it doesn't exist
        return self._create_window(window_id=window_index, start_time=window_start)

    def add_task(self, task: Task) -> None:
        """Add a task to the appropriate window.

        Does NOT close windows - that's done via heartbeat messages.

        Args:
            task: Task to add
        """
        # Get or create the appropriate window
        window = self._get_or_create_window_for_time(task.submission_time)

        # Add task to the target window
        if window.add_task(task):
            logger.debug(
                f"Added task {task.id} (submitted {task.submission_time}) "
                f"to window {window.window_id}"
            )
        else:
            logger.warning(
                f"Failed to add task {task.id} to window {window.window_id}. "
                f"Task time: {task.submission_time}, "
                f"Window: [{window.window_start} - {window.window_end})"
            )

    def update_topology(self, topology_snapshot: TopologySnapshot) -> None:
        """Update the current topology.

        This topology will be used for all new windows and updated in any open windows.

        Args:
            topology_snapshot: New topology snapshot from Kafka
        """
        self.latest_topology = topology_snapshot.topology
        logger.debug(f"📡 Updated topology (snapshot time: {topology_snapshot.timestamp})")

        # Update topology in all open windows
        for window in self.windows.values():
            if not window.is_closed:
                window.update_topology(self.latest_topology)

    def close_windows_before(self, timestamp: datetime) -> list[TimeWindow]:
        """Close all open windows that end before the given timestamp.

        Returns closed windows in chronological order (window_id 0, 1, 2, ...).

        Args:
            timestamp: Timestamp to check against

        Returns:
            List of closed windows in chronological order
        """
        closed_windows = []

        # Find all open windows that should be closed
        for window_id in sorted(self.windows.keys()):
            window = self.windows[window_id]

            if not window.is_closed and window.window_end <= timestamp:
                window.close()
                closed_windows.append(window)
                logger.info(
                    f"Closed window {window_id} "
                    f"[{window.window_start} - {window.window_end}] "
                    f"with {len(window.tasks)} tasks"
                )

        return closed_windows

    def get_all_tasks_up_to_window(self, window_id: int) -> list[Task]:
        """Get all tasks from window 0 up to and including the specified window.

        This is used for cumulative simulation runs.

        Args:
            window_id: Window ID to aggregate up to

        Returns:
            List of all tasks from windows 0..window_id
        """
        all_tasks = []
        for wid in range(window_id + 1):
            if wid in self.windows:
                all_tasks.extend(self.windows[wid].tasks)

        logger.debug(f"Aggregated {len(all_tasks)} tasks from windows 0..{window_id}")
        return all_tasks

    def get_window(self, window_id: int) -> TimeWindow | None:
        """Get a specific window by ID.

        Args:
            window_id: Window ID

        Returns:
            TimeWindow or None if not found
        """
        return self.windows.get(window_id)

    def get_closed_windows(self) -> list[TimeWindow]:
        """Get all closed windows.

        Returns:
            List of closed windows, sorted by window_id
        """
        closed = [w for w in self.windows.values() if w.is_closed]
        return sorted(closed, key=lambda w: w.window_id)

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the window manager state.

        Returns:
            Dictionary with statistics
        """
        open_windows = [w for w in self.windows.values() if not w.is_closed]
        closed_windows = [w for w in self.windows.values() if w.is_closed]

        return {
            "total_windows": len(self.windows),
            "open_windows": len(open_windows),
            "closed_windows": len(closed_windows),
            "total_tasks": sum(len(w.tasks) for w in self.windows.values()),
        }
