"""Topology management for calibration service.

Handles topology subscription, modification, and publishing.
"""

import copy
import logging
import threading

from odt_common.models import Topology, TopologySnapshot
from odt_common.utils import get_kafka_consumer, get_kafka_producer, send_message

logger = logging.getLogger(__name__)


class TopologyManager:
    """Manages topology state and modifications for calibration."""

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        dc_topology_topic: str,
        sim_topology_topic: str,
        consumer_group: str = "calibrator-topology",
    ):
        """Initialize the topology manager.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            dc_topology_topic: Kafka topic for real topology (dc.topology)
            sim_topology_topic: Kafka topic for simulated topology (sim.topology)
            consumer_group: Kafka consumer group ID
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.dc_topology_topic = dc_topology_topic
        self.sim_topology_topic = sim_topology_topic
        self.consumer_group = consumer_group

        # Topology state
        self._real_topology: Topology | None = None
        self._sim_topology: Topology | None = None
        self._lock = threading.Lock()

        # Thread control
        self._stop_event = threading.Event()
        self._consumer_thread: threading.Thread | None = None

        # Kafka producer
        self._producer = get_kafka_producer(kafka_bootstrap_servers)

        logger.info(
            f"Initialized TopologyManager for topics {dc_topology_topic}, {sim_topology_topic}"
        )

    def start(self) -> None:
        """Start consuming topology updates in background thread."""
        if self._consumer_thread and self._consumer_thread.is_alive():
            logger.warning("TopologyManager already running")
            return

        self._stop_event.clear()
        self._consumer_thread = threading.Thread(target=self._consume_topology_updates, daemon=True)
        self._consumer_thread.start()
        logger.info("TopologyManager started")

    def stop(self) -> None:
        """Stop consuming topology updates."""
        if not self._consumer_thread:
            return

        logger.info("Stopping TopologyManager...")
        self._stop_event.set()

        if self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)

        if self._producer:
            self._producer.close()

        logger.info("TopologyManager stopped")

    def _consume_topology_updates(self) -> None:
        """Background thread that consumes topology updates from Kafka."""
        consumer = None

        try:
            consumer = get_kafka_consumer(
                topics=[self.dc_topology_topic, self.sim_topology_topic],
                group_id=self.consumer_group,
                bootstrap_servers=self.kafka_bootstrap_servers,
            )

            logger.info("TopologyManager consumer started")

            for message in consumer:
                if self._stop_event.is_set():
                    break

                try:
                    if message.topic == self.dc_topology_topic:
                        # Real topology (wrapped in TopologySnapshot)
                        snapshot = TopologySnapshot(**message.value)
                        with self._lock:
                            self._real_topology = snapshot.topology
                            # Initialize sim topology if not set
                            if self._sim_topology is None:
                                self._sim_topology = copy.deepcopy(self._real_topology)
                                logger.info("Initialized simulated topology from real topology")
                        logger.debug("Updated real topology")

                    elif message.topic == self.sim_topology_topic:
                        # Simulated topology (raw Topology)
                        topology = Topology(**message.value)
                        with self._lock:
                            self._sim_topology = topology
                        logger.debug("Updated simulated topology")

                except Exception as e:
                    logger.error(f"Error processing topology message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in TopologyManager consumer thread: {e}", exc_info=True)

        finally:
            if consumer:
                consumer.close()
            logger.info("TopologyManager consumer thread exited")

    def get_current_topology(self) -> Topology | None:
        """Get the current topology for calibration (prefer simulated over real).

        Returns:
            Current topology or None if no topology available
        """
        with self._lock:
            return copy.deepcopy(self._sim_topology)

    def create_variant(self, property_path: str, value: float) -> Topology | None:
        """Create a topology variant with modified property value.

        Args:
            property_path: Dot-notation path to property (e.g., "cpuPowerModel.asymUtil")
            value: New value for the property

        Returns:
            Modified topology or None if current topology not available
        """
        current = self.get_current_topology()
        if not current:
            logger.error("Cannot create variant: no topology available")
            return None

        # Parse property path
        parts = property_path.split(".")

        # Modify all hosts in all clusters
        modified_count = 0
        for cluster in current.clusters:
            for host in cluster.hosts:
                # Navigate to the property and update it
                obj = host
                try:
                    # Navigate to parent object
                    for part in parts[:-1]:
                        obj = getattr(obj, part)

                    # Set the final property
                    setattr(obj, parts[-1], value)
                    modified_count += 1

                except AttributeError as e:
                    logger.error(f"Failed to set {property_path}={value} on host {host.name}: {e}")
                    continue

        logger.debug(
            f"Created topology variant with {property_path}={value} ({modified_count} hosts)"
        )

        return current

    def publish_topology(self, topology: Topology) -> bool:
        """Publish topology to simulated topology topic.

        Args:
            topology: Topology to publish

        Returns:
            True if published successfully, False otherwise
        """
        try:
            message_data = topology.model_dump(mode="json")
            # Use a consistent key for compacted topic (only latest topology is kept)
            send_message(
                producer=self._producer,
                topic=self.sim_topology_topic,
                message=message_data,
                key="topology",  # Required for compacted topics
            )
            logger.info(f"Published topology to {self.sim_topology_topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish topology: {e}", exc_info=True)
            return False
