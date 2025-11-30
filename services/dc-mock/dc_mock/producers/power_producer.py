"""Power consumption producer for DC-Mock service.

Streams historical power consumption data to Kafka with proper timing.
"""

import logging
import time

import pandas as pd
from odt_common import Consumption, WorkloadContext

from dc_mock.producers.base import BaseProducer

logger = logging.getLogger(__name__)


class PowerProducer(BaseProducer):
    """Streams power consumption events to Kafka in time order.

    Handles timestamp conversion from relative to absolute timestamps
    based on the earliest task submission time and configured offset.
    """

    def __init__(
        self,
        workload_context: WorkloadContext,
        kafka_bootstrap_servers: str,
        speed_factor: float,
        topic: str,
        earliest_task_time_ms: int,
    ):
        """Initialize the power producer.

        Args:
            workload_context: Workload context with resolved file paths
            kafka_bootstrap_servers: Kafka broker addresses
            speed_factor: Simulation speed multiplier
            topic: Kafka topic name for power consumption events
            earliest_task_time_ms: Earliest task submission time in epoch ms
        """
        super().__init__(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            speed_factor=speed_factor,
            topic=topic,
            name="PowerProducer",
        )
        self.workload_context = workload_context
        self.earliest_task_time_ms = earliest_task_time_ms
        self.consumption_records: list[Consumption] = []

        logger.info(f"  Consumption file: {workload_context.consumption_file}")
        logger.info(f"  Earliest task time: {earliest_task_time_ms}ms")

    def load_consumption_data(self) -> list[Consumption]:
        """Load consumption data from Parquet file.

        Returns:
            List of Consumption records with absolute timestamps

        Raises:
            FileNotFoundError: If consumption file doesn't exist
        """
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

        # Convert to Pydantic models
        consumption_records = []
        for _, row in consumption_df.iterrows():
            try:
                consumption_records.append(Consumption(**row.to_dict()))
            except Exception as e:
                logger.warning(f"Failed to parse consumption record: {e}")

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

            # Track simulation time
            sim_start_time = self.consumption_records[0].timestamp
            real_start_time = time.time()

            for i, consumption in enumerate(self.consumption_records):
                if self.should_stop():
                    logger.info("PowerProducer interrupted")
                    break

                # Calculate elapsed simulation time
                sim_elapsed = (consumption.timestamp - sim_start_time).total_seconds()

                # Calculate required sleep based on speed_factor
                if self.speed_factor > 0:
                    required_real_elapsed = sim_elapsed / self.speed_factor
                    real_elapsed = time.time() - real_start_time
                    sleep_time = required_real_elapsed - real_elapsed

                    if sleep_time > 0:
                        # Use interruptible wait
                        if self.wait_interruptible(sleep_time):
                            logger.info("PowerProducer interrupted during sleep")
                            break
                # If speed_factor == -1, don't sleep (max speed)

                # Emit consumption event
                self.emit_message(
                    message=consumption.model_dump(mode="json"),
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
