"""Power consumption producer for DC-Mock service.

Streams historical power consumption data to Kafka with proper timing.
"""

import logging
from datetime import UTC

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
        self.consumption_records: list[Consumption] = []

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
        """Run the power producer (streams consumption events)."""
        logger.info("PowerProducer running")

        try:
            # Load consumption data
            self.consumption_records = self.load_consumption_data()

            if not self.consumption_records:
                logger.warning("No consumption data to stream")
                return

            logger.info(f"Streaming {len(self.consumption_records)} consumption events...")

            # the trace's clock starts at the first task, as the workload's
            from datetime import datetime

            sim_start_time = datetime.fromtimestamp(self.earliest_task_time_ms / 1000.0, tz=UTC)
            self.start_clock(sim_start_time)

            logger.info(f"PowerProducer starts at {sim_start_time}")

            for i, consumption in enumerate(self.consumption_records):
                if self.should_stop():
                    logger.info("PowerProducer interrupted")
                    break

                if self.wait_until(consumption.timestamp):
                    logger.info("PowerProducer interrupted during sleep")
                    break

                # Emit consumption event
                consumption_msg = consumption.model_dump(mode="json")

                # Debug: Log first few power emissions
                if i < 5 or (i + 1) % 100 == 0:
                    logger.info(
                        f"PowerProducer sending power #{i + 1}: "
                        f"timestamp={consumption.timestamp.isoformat()}"
                    )

                self.emit_message(
                    message=consumption_msg,
                    key=None,  # No key for consumption
                )

                # Periodic flush and logging
                if (i + 1) % 100 == 0:
                    progress = (i + 1) / len(self.consumption_records) * 100
                    logger.info(
                        f"PowerProducer progress: {i + 1}/"
                        f"{len(self.consumption_records)} ({progress:.1f}%)"
                    )
                    self.flush()

            # Final flush
            logger.info("PowerProducer flushing remaining messages...")
            self.flush()
            logger.info("PowerProducer finished streaming")

        except Exception as e:
            logger.error(f"Fatal error in PowerProducer: {e}", exc_info=True)
            raise
