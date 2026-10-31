"""Workload producer for DC-Mock service.

Streams task/workload events to Kafka with proper timing.
"""

import logging
from datetime import timedelta

import pandas as pd
from odt_common import Task, WorkloadContext

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

    def load_and_aggregate_tasks(self) -> list[Task]:
        """The workload's tasks, each with its fragments, in order of submission."""
        tasks_df = pd.read_parquet(self.workload_context.tasks_file)
        fragments_df = pd.read_parquet(self.workload_context.fragments_file)
        fragments: dict[str, list[dict]] = {}
        for fragment in fragments_df.to_dict("records"):
            fragments.setdefault(fragment["id"], []).append(fragment)
        tasks = [
            Task(**row, fragments=fragments.get(row["id"], []))
            for row in tasks_df.to_dict("records")
        ]
        tasks.sort(key=lambda t: t.submission_time)
        logger.info(f"Loaded {len(tasks)} tasks with {len(fragments_df)} fragments")
        return tasks

    def run(self) -> None:
        """Replay the tasks at their submission times, on the trace's clock, with a heartbeat every
        `heartbeat_frequency_minutes` of the trace, as only heartbeats close the simulator's windows."""
        self.tasks = self.load_and_aggregate_tasks()
        start = self.tasks[0].submission_time
        self.start_clock(start)
        every = timedelta(minutes=self.heartbeat_frequency_minutes)
        heartbeat = start.replace(second=0, microsecond=0)
        heartbeats = 0
        for i, task in enumerate(self.tasks, 1):
            while heartbeat <= task.submission_time:  # the heartbeats due before the task
                if self.wait_until(heartbeat):
                    return
                message = {"message_type": "heartbeat", "timestamp": heartbeat.isoformat()}
                self.emit_message(message, key="heartbeat")
                heartbeats += 1
                heartbeat += every
            if self.wait_until(task.submission_time):
                return
            message = {
                "message_type": "task",
                "timestamp": task.submission_time.isoformat(),
                "task": task.model_dump(mode="json"),
            }
            self.emit_message(message, key=str(task.id))
            if i % 500 == 0:
                logger.info(f"WorkloadProducer progress: {i}/{len(self.tasks)} tasks")
        logger.info(
            f"WorkloadProducer finished streaming: {len(self.tasks)} tasks, {heartbeats} heartbeats"
        )
