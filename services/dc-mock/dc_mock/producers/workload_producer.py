"""Workload producer for DC-Mock service.

Streams task/workload events to Kafka with proper timing.
"""

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
from odt_common import Fragment, Task, WorkloadContext

from dc_mock.producers.base import BaseProducer
from dc_mock.speed import Speed

logger = logging.getLogger(__name__)


class WorkloadProducer(BaseProducer):
    """Streams workload (task) events to Kafka in time order.

    Pre-aggregates fragments into their parent tasks before streaming.
    """

    def __init__(
        self,
        workload_context: WorkloadContext,
        speed: Speed,
        topic: str,
        heartbeat_frequency_minutes: int = 1,
    ):
        """Initialize the workload producer."""
        super().__init__(
            speed=speed,
            topic=topic,
            name="WorkloadProducer",
        )
        self.workload_context = workload_context
        self.tasks: list[Task] = []
        self.heartbeat_frequency_minutes = heartbeat_frequency_minutes

        logger.info(f"  Tasks file: {workload_context.tasks_file}")
        logger.info(f"  Fragments file: {workload_context.fragments_file}")
        logger.info(f"  Heartbeat frequency: {heartbeat_frequency_minutes} simulated minutes")

    def load_and_aggregate_tasks(self) -> tuple[list[Task], datetime]:
        """Load tasks and fragments, aggregating fragments into tasks."""
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
            logger.info("WorkloadProducer loading tasks...")
            self.tasks, earliest_task_time = self.load_and_aggregate_tasks()

            if not self.tasks:
                logger.warning("No tasks to stream")
                return

            logger.info(f"Streaming {len(self.tasks)} task events with heartbeats...")

            # the trace's clock starts at the first task
            sim_start_time = self.tasks[0].submission_time
            self.start_clock(sim_start_time)
            logger.info(f"WorkloadProducer starts at {sim_start_time}")
            logger.info(f"WorkloadProducer real start time: {time.time()}")

            # Initialize heartbeat tracking
            heartbeat_frequency = timedelta(minutes=self.heartbeat_frequency_minutes)
            # Round down to the nearest minute for first heartbeat
            next_heartbeat_time = sim_start_time.replace(second=0, microsecond=0)
            heartbeats_sent = 0

            logger.info(
                f"First heartbeat scheduled at: {next_heartbeat_time}, "
                f"first task at: {self.tasks[0].submission_time}"
            )

            for i, task in enumerate(self.tasks):
                if self.should_stop():
                    logger.info("WorkloadProducer interrupted")
                    break

                # Debug: Log when we're about to process a task
                if i < 5:
                    logger.info(
                        f"Processing task #{i + 1}: submission_time={task.submission_time.isoformat()}, "
                        f"next_heartbeat_time={next_heartbeat_time.isoformat()}"
                    )

                # Emit any pending heartbeats before this task
                heartbeats_to_send = 0
                temp_heartbeat_time = next_heartbeat_time
                while temp_heartbeat_time <= task.submission_time:
                    heartbeats_to_send += 1
                    temp_heartbeat_time += heartbeat_frequency

                if i < 5 and heartbeats_to_send > 0:
                    logger.info(f"Will send {heartbeats_to_send} heartbeat(s) before this task")

                while next_heartbeat_time <= task.submission_time:
                    if self.wait_until(next_heartbeat_time):
                        logger.info("WorkloadProducer interrupted during heartbeat sleep")
                        break

                    # Emit heartbeat message
                    heartbeat_msg = {
                        "message_type": "heartbeat",
                        "timestamp": next_heartbeat_time.isoformat(),
                    }

                    # Debug: Log first few heartbeat emissions
                    if heartbeats_sent < 5:
                        logger.info(
                            f"WorkloadProducer sending heartbeat #{heartbeats_sent + 1}: "
                            f"timestamp={next_heartbeat_time.isoformat()}"
                        )

                    self.emit_message(message=heartbeat_msg, key="heartbeat")
                    heartbeats_sent += 1

                    # Move to next heartbeat time
                    next_heartbeat_time += heartbeat_frequency

                if self.wait_until(task.submission_time):
                    logger.info("WorkloadProducer interrupted during sleep")
                    break

                # Emit task event wrapped with message_type
                task_msg = {
                    "message_type": "task",
                    "timestamp": task.submission_time.isoformat(),
                    "task": task.model_dump(mode="json"),
                }

                # Debug: Log first few task emissions
                if i < 5 or (i + 1) % 100 == 0:
                    logger.info(
                        f"WorkloadProducer sending task #{i + 1}: id={task.id}, "
                        f"timestamp={task.submission_time.isoformat()}"
                    )

                self.emit_message(message=task_msg, key=str(task.id))

                # Periodic flush and logging
                if (i + 1) % 100 == 0:
                    progress = (i + 1) / len(self.tasks) * 100
                    logger.info(
                        f"WorkloadProducer progress: {i + 1}/{len(self.tasks)} tasks, "
                        f"{heartbeats_sent} heartbeats ({progress:.1f}%)"
                    )
                    self.flush()

            # Final flush
            logger.info("WorkloadProducer flushing remaining messages...")
            self.flush()
            logger.info(
                f"WorkloadProducer finished streaming: "
                f"{len(self.tasks)} tasks, {heartbeats_sent} heartbeats"
            )

        except Exception as e:
            logger.error(f"Fatal error in WorkloadProducer: {e}", exc_info=True)
            raise
