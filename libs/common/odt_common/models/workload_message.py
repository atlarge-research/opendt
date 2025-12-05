"""Workload message wrapper for dc.workload topic.

Wraps both task submissions and heartbeat messages.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .task import Task


class WorkloadMessage(BaseModel):
    """Wrapper for messages on dc.workload topic.

    Supports two message types:
    - 'task': A workload submission containing task data
    - 'heartbeat': A keepalive message to help consumers detect end-of-stream

    The heartbeat mechanism allows consumers to distinguish between:
    - No new tasks because the workload is complete
    - No new tasks because Kafka is delayed
    """

    message_type: Literal["task", "heartbeat"] = Field(
        ..., description="Type of message: 'task' for workload or 'heartbeat' for keepalive"
    )
    timestamp: datetime = Field(..., description="Simulation timestamp of this message")
    task: Task | None = Field(None, description="Task data (only present when message_type='task')")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "message_type": "task",
                    "timestamp": "2024-01-01T00:05:30",
                    "task": {
                        "id": 123,
                        "submission_time": "2024-01-01T00:05:30",
                        "duration": 120500,
                        "cpu_count": 4,
                        "cpu_capacity": 2400.0,
                        "mem_capacity": 4096,
                        "fragments": [],
                    },
                },
                {"message_type": "heartbeat", "timestamp": "2024-01-01T00:06:00", "task": None},
            ]
        }
