"""Base producer class for DC-Mock threaded producers."""

import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from kafka import KafkaProducer
from odt_common.utils import get_kafka_producer
from odt_common.utils.kafka import send_message

from dc_mock.speed import Speed

logger = logging.getLogger(__name__)


class BaseProducer(ABC):
    """Base class for threaded Kafka producers.

    Provides common functionality for all producers:
    - Kafka producer management
    - Thread lifecycle management
    - Message emission utilities
    - Speed factor handling
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        speed: Speed,
        topic: str,
        name: str | None = None,
    ):
        """Initialize the base producer."""
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.speed = speed
        self.topic = topic
        self.name = name or self.__class__.__name__
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._producer: KafkaProducer | None = None

        logger.info(f"Initialized {self.name}")
        logger.info(f"  Topic: {self.topic}")
        logger.info(f"  Speed factor: {self.speed.factor}x")

    def _get_producer(self) -> KafkaProducer:
        """Get or create the Kafka producer."""
        if self._producer is None:
            self._producer = get_kafka_producer(self.kafka_bootstrap_servers)
        return self._producer

    def emit_message(self, message: dict[str, Any], key: str | None = None) -> None:
        """Emit a message to Kafka."""
        try:
            send_message(
                self._get_producer(),
                topic=self.topic,
                message=message,
                key=key,
            )
        except Exception as e:
            logger.error(f"Failed to emit message to {self.topic}: {e}", exc_info=True)
            raise

    def flush(self) -> None:
        """Flush buffered messages to Kafka."""
        if self._producer:
            self._producer.flush()

    def start_clock(self, trace_start: datetime) -> None:
        """Start replaying: `trace_start` of the trace is now."""
        self._trace_start = trace_start
        self._wall_start = time.time()
        self._factor = self.speed.factor

    def wait_until(self, trace_time: datetime) -> bool:
        """Sleep until `trace_time` of the trace is due at the current speed; True if stopped meanwhile.

        The speed is checked at least every second; after a change, the pace restarts from where the replay is.
        """
        while True:
            if self.speed.factor != self._factor:
                if self._factor > 0:
                    replayed = timedelta(seconds=(time.time() - self._wall_start) * self._factor)
                    trace_time_now = min(self._trace_start + replayed, trace_time)
                else:
                    trace_time_now = trace_time
                self._trace_start, self._wall_start = trace_time_now, time.time()
                self._factor = self.speed.factor
            if self._factor <= 0:  # -1: maximum speed
                return self.should_stop()
            due = (trace_time - self._trace_start).total_seconds() / self._factor
            delay = due - (time.time() - self._wall_start)
            if delay <= 0:
                return False
            if self.wait_interruptible(min(delay, 1.0)):
                return True

    @abstractmethod
    def run(self) -> None:
        """Run the producer (main logic).

        This method should be implemented by subclasses and will be
        executed in a separate thread.
        """
        pass

    def start(self) -> None:
        """Start the producer in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning(f"{self.name} is already running")
            return

        logger.info(f"Starting {self.name} in background thread...")
        self._thread = threading.Thread(target=self._run_wrapper, daemon=True, name=self.name)
        self._thread.start()
        logger.info(f"{self.name} started")

    def _run_wrapper(self) -> None:
        """Wrapper around run() for exception handling and cleanup."""
        try:
            self.run()
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Error in {self.name}: {e}", exc_info=True)
        finally:
            self._cleanup()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the producer and wait for thread to finish."""
        if self._thread is None or not self._thread.is_alive():
            logger.debug(f"{self.name} is not running")
            return

        logger.info(f"Stopping {self.name}...")
        self._stop_event.set()

        # Wait for thread to finish
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            logger.warning(f"{self.name} did not terminate within {timeout}s")
        else:
            logger.info(f"{self.name} stopped")

    def _cleanup(self) -> None:
        """Clean up resources (called automatically on exit)."""
        if self._producer:
            try:
                self._producer.flush()
                self._producer.close()
                logger.info(f"{self.name} Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing {self.name} producer: {e}")
            finally:
                self._producer = None

    def is_running(self) -> bool:
        """Check if the producer thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def should_stop(self) -> bool:
        """Check if stop has been requested."""
        return self._stop_event.is_set()

    def wait_interruptible(self, seconds: float) -> bool:
        """Wait for specified seconds, but can be interrupted by stop event."""
        return self._stop_event.wait(timeout=seconds)
