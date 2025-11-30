"""Topology producer for DC-Mock service.

Periodically publishes datacenter topology to Kafka.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from odt_common import Topology, TopologySnapshot

from dc_mock.producers.base import BaseProducer

logger = logging.getLogger(__name__)


class TopologyProducer(BaseProducer):
    """Periodically publishes datacenter topology to Kafka.

    Re-reads the topology file and publishes it at a fixed interval,
    allowing for dynamic topology updates during simulation.
    """

    def __init__(
        self,
        topology_file: Path,
        kafka_bootstrap_servers: str,
        speed_factor: float,
        topic: str,
        publish_interval_seconds: float = 30.0,
    ):
        """Initialize the topology producer.

        Args:
            topology_file: Path to topology.json file
            kafka_bootstrap_servers: Kafka broker addresses
            speed_factor: Simulation speed multiplier
            topic: Kafka topic name for topology events
            publish_interval_seconds: Publish interval in realtime seconds (default: 30s)
        """
        super().__init__(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            speed_factor=speed_factor,
            topic=topic,
            name="TopologyProducer",
        )
        self.topology_file = topology_file
        self.publish_interval_seconds = publish_interval_seconds

        logger.info(f"  Topology file: {topology_file}")
        logger.info(f"  Publish interval (realtime): {publish_interval_seconds}s")

    def load_topology(self) -> Topology:
        """Load and validate topology from JSON file.

        Returns:
            Validated Topology object

        Raises:
            FileNotFoundError: If topology file doesn't exist
            ValueError: If topology JSON is invalid
        """
        if not self.topology_file.exists():
            raise FileNotFoundError(f"Topology file not found: {self.topology_file}")

        with open(self.topology_file) as f:
            topology_data = json.load(f)

        try:
            topology = Topology(**topology_data)
            logger.debug(f"Loaded topology with {len(topology.clusters)} cluster(s)")
            logger.debug(f"  Total hosts: {topology.total_host_count()}")
            logger.debug(f"  Total cores: {topology.total_core_count()}")
            return topology
        except Exception as e:
            logger.error(f"Failed to parse topology: {e}")
            raise ValueError(f"Invalid topology format: {e}") from e

    def run(self) -> None:
        """Run the topology producer (publishes periodically in a loop)."""
        logger.info("TopologyProducer running")

        try:
            # Load topology once at startup
            topology = self.load_topology()
            logger.info(
                f"Loaded topology: {topology.total_host_count()} hosts, "
                f"{topology.total_core_count()} cores"
            )

            # Calculate effective interval based on speed factor
            effective_interval = self.calculate_sleep_time(self.publish_interval_seconds)
            logger.info(f"Effective publish interval: {effective_interval:.2f}s")

            # Publish immediately on startup
            snapshot = TopologySnapshot(timestamp=datetime.now(), topology=topology)
            self.emit_message(
                message=snapshot.model_dump(mode="json"),
                key="datacenter",  # Single key for compaction
            )
            self.flush()
            logger.info("Published initial topology")

            # Then publish periodically
            while not self.should_stop():
                # Wait for the interval (with ability to interrupt)
                if self.wait_interruptible(effective_interval):
                    break

                # Re-read topology file (allows for dynamic updates)
                try:
                    topology = self.load_topology()
                    snapshot = TopologySnapshot(timestamp=datetime.now(), topology=topology)
                    self.emit_message(
                        message=snapshot.model_dump(mode="json"),
                        key="datacenter",
                    )
                    self.flush()
                    logger.debug("Published topology update")
                except Exception as e:
                    logger.error(f"Error publishing topology: {e}", exc_info=True)
                    # Continue even if one iteration fails

            logger.info("TopologyProducer finished")

        except Exception as e:
            logger.error(f"Fatal error in TopologyProducer: {e}", exc_info=True)
            raise
