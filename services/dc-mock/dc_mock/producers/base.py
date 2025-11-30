"""Base producer class for DC-Mock threaded producers."""

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any

from kafka import KafkaProducer
from odt_common.utils import get_kafka_producer
from odt_common.utils.kafka import send_message

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
        speed_factor: float,
        topic: str,
        name: str | None = None,
    ):
        """Initialize the base producer.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            speed_factor: Simulation speed multiplier (1.0 = realtime, -1 = max speed)
            topic: Kafka topic name for this producer
            name: Optional producer name for logging
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.speed_factor = speed_factor
        self.topic = topic
        self.name = name or self.__class__.__name__
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._producer: KafkaProducer | None = None

        logger.info(f"Initialized {self.name}")
        logger.info(f"  Topic: {self.topic}")
        logger.info(f"  Speed factor: {self.speed_factor}x")

    def _get_producer(self) -> KafkaProducer:
        """Get or create the Kafka producer.

        Returns:
            Kafka producer instance
        """
        if self._producer is None:
            self._producer = get_kafka_producer(self.kafka_bootstrap_servers)
        return self._producer

    def emit_message(self, message: dict[str, Any], key: str | None = None) -> None:
        """Emit a message to Kafka.

        Args:
            message: Message payload (will be JSON serialized)
            key: Optional message key
        """
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

    def calculate_sleep_time(self, realtime_seconds: float) -> float:
        """Calculate actual sleep time based on speed factor.

        Args:
            realtime_seconds: Desired sleep time in realtime seconds

        Returns:
            Actual sleep time adjusted for speed factor
        """
        if self.speed_factor <= 0:
            # Max speed (-1): minimal sleep
            return 0.001
        return realtime_seconds / self.speed_factor

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
        """Stop the producer and wait for thread to finish.

        Args:
            timeout: Maximum time to wait for thread termination in seconds
        """
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
        """Check if the producer thread is running.

        Returns:
            True if thread is alive, False otherwise
        """
        return self._thread is not None and self._thread.is_alive()

    def should_stop(self) -> bool:
        """Check if stop has been requested.

        Returns:
            True if stop event is set, False otherwise
        """
        return self._stop_event.is_set()

    def wait_interruptible(self, seconds: float) -> bool:
        """Wait for specified seconds, but can be interrupted by stop event.

        Args:
            seconds: Time to wait in seconds

        Returns:
            True if interrupted (should stop), False if timed out normally
        """
        return self._stop_event.wait(timeout=seconds)
