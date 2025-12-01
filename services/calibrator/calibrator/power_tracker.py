"""Power consumption tracker for calibration service.

Subscribes to actual power consumption data and provides historical queries.
"""

import logging
import threading
from datetime import datetime

import pandas as pd
from odt_common.models import Consumption
from odt_common.utils import get_kafka_consumer

logger = logging.getLogger(__name__)


class PowerTracker:
    """Tracks actual power consumption from Kafka for calibration comparisons."""

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        power_topic: str,
        consumer_group: str = "calibrator-power",
        debug: bool = False,
    ):
        """Initialize the power tracker.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            power_topic: Kafka topic for power consumption (dc.power)
            consumer_group: Kafka consumer group ID
            debug: Enable debug logging for power consumption
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.power_topic = power_topic
        self.consumer_group = consumer_group
        self.debug = debug

        # Store power readings without size limit - accumulate everything
        self.power_readings: list[tuple[datetime, float]] = []

        # Thread control
        self._stop_event = threading.Event()
        self._consumer_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        logger.info(f"Initialized PowerTracker for topic {power_topic}")
        logger.info("Accumulating all power readings (no size limit)")
        if self.debug:
            logger.info("Debug mode enabled for PowerTracker")

    def start(self) -> None:
        """Start consuming power data in background thread."""
        if self._consumer_thread and self._consumer_thread.is_alive():
            logger.warning("PowerTracker already running")
            return

        self._stop_event.clear()
        self._consumer_thread = threading.Thread(target=self._consume_power_data, daemon=True)
        self._consumer_thread.start()
        logger.info("PowerTracker started")

    def stop(self) -> None:
        """Stop consuming power data."""
        if not self._consumer_thread:
            return

        logger.info("Stopping PowerTracker...")
        self._stop_event.set()

        if self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)

        logger.info("PowerTracker stopped")

    def _consume_power_data(self) -> None:
        """Background thread that consumes power data from Kafka."""
        consumer = None

        try:
            consumer = get_kafka_consumer(
                topics=[self.power_topic],
                group_id=self.consumer_group,
                bootstrap_servers=self.kafka_bootstrap_servers,
            )

            logger.info(f"PowerTracker consumer started for topic {self.power_topic}")

            for message in consumer:
                if self._stop_event.is_set():
                    break

                try:
                    consumption = Consumption(**message.value)

                    with self._lock:
                        self.power_readings.append((consumption.timestamp, consumption.power_draw))

                        # Log first message
                        if len(self.power_readings) == 1:
                            logger.info(
                                f"PowerTracker received first power reading: "
                                f"{consumption.timestamp} = {consumption.power_draw}W"
                            )

                    # Log every 100 messages
                    if len(self.power_readings) % 100 == 0:
                        logger.debug(
                            f"PowerTracker: {len(self.power_readings)} readings accumulated. "
                            f"Latest: {consumption.timestamp}"
                        )

                except Exception as e:
                    logger.error(f"Error processing power message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in PowerTracker consumer thread: {e}", exc_info=True)

        finally:
            if consumer:
                consumer.close()
            logger.info("PowerTracker consumer thread exited")

    def get_power_in_window(
        self, start_time: datetime, end_time: datetime, prune_old: bool = True
    ) -> pd.DataFrame:
        """Get power readings within a time window.

        Args:
            start_time: Window start time
            end_time: Window end time
            prune_old: If True, prune readings older than start_time to save memory

        Returns:
            DataFrame with columns: timestamp, power_draw (frozen copy at query time)
        """
        with self._lock:
            total_readings = len(self.power_readings)

            # Debug: Log window and stored data info
            if total_readings > 0:
                earliest = self.power_readings[0][0]
                latest = self.power_readings[-1][0]
                logger.debug(f"PowerTracker has {total_readings} readings: {earliest} to {latest}")
                logger.debug(f"Requested window: {start_time} to {end_time}")

                # Debug: Check timezone awareness
                logger.debug(f"Window timezone: start={start_time.tzinfo}, end={end_time.tzinfo}")
                logger.debug(f"Data timezone: earliest={earliest.tzinfo}, latest={latest.tzinfo}")

            # Filter readings within window (make a frozen copy)
            filtered = [
                (timestamp, power)
                for timestamp, power in self.power_readings
                if start_time <= timestamp <= end_time
            ]

            # Prune old readings if requested (keep only data >= start_time)
            if prune_old and total_readings > 0:
                # Keep readings that are >= start_time
                self.power_readings = [
                    (timestamp, power)
                    for timestamp, power in self.power_readings
                    if timestamp >= start_time
                ]
                pruned_count = total_readings - len(self.power_readings)
                if pruned_count > 0:
                    logger.info(
                        f"Pruned {pruned_count} old power readings "
                        f"(kept {len(self.power_readings)})"
                    )

        if not filtered:
            logger.warning(
                f"No power readings found in window {start_time} to {end_time}. "
                f"Total readings in memory: {total_readings}"
            )
            if total_readings > 0:
                with self._lock:
                    if self.power_readings:
                        logger.warning(
                            f"Available data range: {self.power_readings[0][0]} to "
                            f"{self.power_readings[-1][0]}"
                        )
            return pd.DataFrame({"timestamp": [], "power_draw": []})

        df = pd.DataFrame(filtered, columns=["timestamp", "power_draw"])  # type: ignore[call-overload]
        df = df.sort_values("timestamp", ignore_index=True)

        logger.info(
            f"Retrieved {len(df)} power readings from "
            f"{df['timestamp'].min()} to {df['timestamp'].max()}"
        )

        return df

    def get_latest_timestamp(self) -> datetime | None:
        """Get timestamp of most recent power reading.

        Returns:
            Latest timestamp or None if no readings
        """
        with self._lock:
            if not self.power_readings:
                return None
            return self.power_readings[-1][0]

    def get_reading_count(self) -> int:
        """Get current number of power readings in memory.

        Returns:
            Number of readings
        """
        with self._lock:
            return len(self.power_readings)
