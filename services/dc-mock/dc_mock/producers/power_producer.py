"""Power consumption producer for DC-Mock service.

Streams historical power consumption data to Kafka with proper timing.
"""

import logging
from datetime import UTC, datetime

import pandas as pd
from odt_common import Consumption, WorkloadContext

from dc_mock.producers.base import BaseProducer
from dc_mock.speed import Speed

logger = logging.getLogger(__name__)


class PowerProducer(BaseProducer):
    """Streams power consumption events to Kafka in time order.

    Handles timestamp conversion from relative to absolute timestamps
    based on the earliest task submission time and configured offset.
    """

    def __init__(
        self,
        workload_context: WorkloadContext,
        speed: Speed,
        topic: str,
        earliest_task_time_ms: int,
    ):
        """Initialize the power producer."""
        super().__init__(
            speed=speed,
            topic=topic,
            name="PowerProducer",
        )
        self.workload_context = workload_context
        self.earliest_task_time_ms = earliest_task_time_ms

        logger.info(f"  Consumption file: {workload_context.consumption_file}")
        logger.info(f"  Earliest task time: {earliest_task_time_ms}ms")

    def load_consumption_data(self) -> list[Consumption]:
        """Load consumption data from Parquet file."""
        if not self.workload_context.consumption_file.exists():
            logger.warning(f"Consumption file not found: {self.workload_context.consumption_file}")
            return []

        consumption_df = pd.read_parquet(self.workload_context.consumption_file)
        logger.info(f"Loaded {len(consumption_df)} consumption records")

        # Convert relative timestamps to absolute timestamps
        offset_ms = self.workload_context.consumption_offset_ms
        logger.info(f"Converting consumption timestamps with offset: {offset_ms}ms")

        # Formula: absolute_time_ms = earliest_task_time_ms + relative_ms + offset_ms
        consumption_df["timestamp"] = (
            self.earliest_task_time_ms + consumption_df["timestamp"] + offset_ms
        )

        consumption_records = [Consumption(**row) for row in consumption_df.to_dict("records")]

        logger.info(f"Parsed {len(consumption_records)} consumption records")
        if consumption_records:
            first_time = consumption_records[0].timestamp
            last_time = consumption_records[-1].timestamp
            logger.info(f"Time range: {first_time} to {last_time}")

        return consumption_records

    def run(self) -> None:
        """Replay the measured power at its times, on the trace's clock, which starts at the first task."""
        records = self.load_consumption_data()
        self.start_clock(datetime.fromtimestamp(self.earliest_task_time_ms / 1000, tz=UTC))
        for i, consumption in enumerate(records, 1):
            if self.wait_until(consumption.timestamp):
                return
            self.emit_message(consumption.model_dump(mode="json"))
            if i % 500 == 0:
                logger.info(f"PowerProducer progress: {i}/{len(records)}")
        logger.info("PowerProducer finished streaming")
