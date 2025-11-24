"""Workload producer for DC-Mock service.

Streams task/workload events to Kafka with proper timing.
"""

import logging
import time
from datetime import datetime

import pandas as pd
from opendt_common import Fragment, Task, WorkloadContext

from dc_mock.producers.base import BaseProducer

logger = logging.getLogger(__name__)


class WorkloadProducer(BaseProducer):
    """Streams workload (task) events to Kafka in time order.

    Pre-aggregates fragments into their parent tasks before streaming.
    """

    def __init__(
        self,
        workload_context: WorkloadContext,
        kafka_bootstrap_servers: str,
        speed_factor: float,
        topic: str,
    ):
        """Initialize the workload producer.

        Args:
            workload_context: Workload context with resolved file paths
            kafka_bootstrap_servers: Kafka broker addresses
            speed_factor: Simulation speed multiplier
            topic: Kafka topic name for workload events
        """
        super().__init__(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            speed_factor=speed_factor,
            topic=topic,
            name="WorkloadProducer",
        )
        self.workload_context = workload_context
        self.tasks: list[Task] = []

        logger.info(f"  Tasks file: {workload_context.tasks_file}")
        logger.info(f"  Fragments file: {workload_context.fragments_file}")

    def load_and_aggregate_tasks(self) -> tuple[list[Task], datetime]:
        """Load tasks and fragments, aggregating fragments into tasks.

        Returns:
            Tuple of (tasks, earliest_submission_time)

        Raises:
            FileNotFoundError: If required files don't exist
        """
        logger.info("Loading task and fragment data...")

        # Load tasks
        tasks_df = pd.read_parquet(self.workload_context.tasks_file)
        logger.info(f"Loaded {len(tasks_df)} tasks")

        # Get earliest task submission time
        earliest_task_time = tasks_df["submission_time"].min().to_pydatetime()
        logger.info(f"Earliest task submission time: {earliest_task_time}")

        # Load fragments
        fragments_df = pd.read_parquet(self.workload_context.fragments_file)
        logger.info(f"Loaded {len(fragments_df)} fragments")

        # Aggregate fragments by task_id
        logger.info("Aggregating fragments into tasks...")
        fragments_by_task = fragments_df.groupby("id")

        # Create Task objects with nested fragments
        tasks = []
        for _, task_row in tasks_df.iterrows():
            task_dict = task_row.to_dict()
            task_id = task_dict["id"]

            # Get fragments for this task
            if task_id in fragments_by_task.groups:
                task_fragments_df = fragments_by_task.get_group(task_id)
                fragments = [
                    Fragment(**frag_row.to_dict()) for _, frag_row in task_fragments_df.iterrows()
                ]
                task_dict["fragments"] = fragments
            else:
                task_dict["fragments"] = []

            try:
                tasks.append(Task(**task_dict))
            except Exception as e:
                logger.warning(f"Failed to parse task {task_id}: {e}")

        logger.info(f"Created {len(tasks)} task aggregates")
        total_fragments = sum(len(t.fragments) for t in tasks)
        logger.info(f"Total fragments aggregated: {total_fragments}")

        # Sort tasks by submission time
        tasks.sort(key=lambda t: t.submission_time)

        if tasks:
            logger.info(f"Time range: {tasks[0].submission_time} to {tasks[-1].submission_time}")

        return tasks, earliest_task_time

    def run(self) -> None:
        """Run the workload producer (streams task events)."""
        logger.info("WorkloadProducer running")

        try:
            # Load and aggregate tasks
            self.tasks, earliest_task_time = self.load_and_aggregate_tasks()

            if not self.tasks:
                logger.warning("No tasks to stream")
                return

            logger.info(f"Streaming {len(self.tasks)} task events...")

            # Track simulation time
            sim_start_time = self.tasks[0].submission_time
            real_start_time = time.time()

            for i, task in enumerate(self.tasks):
                if self.should_stop():
                    logger.info("WorkloadProducer interrupted")
                    break

                # Calculate elapsed simulation time
                sim_elapsed = (task.submission_time - sim_start_time).total_seconds()

                # Calculate required sleep based on speed_factor
                if self.speed_factor > 0:
                    required_real_elapsed = sim_elapsed / self.speed_factor
                    real_elapsed = time.time() - real_start_time
                    sleep_time = required_real_elapsed - real_elapsed

                    if sleep_time > 0:
                        # Use interruptible wait
                        if self.wait_interruptible(sleep_time):
                            logger.info("WorkloadProducer interrupted during sleep")
                            break
                # If speed_factor == -1, don't sleep (max speed)

                # Emit task event
                self.emit_message(
                    message=task.model_dump(mode="json"),
                    key=str(task.id),
                )

                # Periodic flush and logging
                if (i + 1) % 100 == 0:
                    progress = (i + 1) / len(self.tasks) * 100
                    logger.info(
                        f"WorkloadProducer progress: {i + 1}/{len(self.tasks)} ({progress:.1f}%)"
                    )
                    self.flush()

            # Final flush
            logger.info("WorkloadProducer flushing remaining messages...")
            self.flush()
            logger.info("WorkloadProducer finished streaming")

        except Exception as e:
            logger.error(f"Fatal error in WorkloadProducer: {e}", exc_info=True)
            raise

    def get_earliest_task_time_ms(self) -> int | None:
        """Get the earliest task submission time in epoch milliseconds.

        Returns:
            Earliest task time in ms, or None if no tasks loaded
        """
        if not self.tasks:
            return None
        return int(self.tasks[0].submission_time.timestamp() * 1000)
