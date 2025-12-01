"""DC-Mock Service - Main Entry Point.

This service:
1. Loads configuration from environment
2. Starts three independent threaded producers:
   - TopologyProducer: Periodically publishes datacenter topology
   - WorkloadProducer: Streams task/workload events in time order
   - PowerProducer: Streams power consumption telemetry in time order
3. Respects simulation speed_factor for timing
4. Gracefully handles shutdown
"""

import logging
import os
import signal
import sys
import threading
from pathlib import Path

from odt_common import load_config_from_env
from odt_common.utils import get_kafka_bootstrap_servers

from dc_mock.producers import PowerProducer, TopologyProducer, WorkloadProducer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DCMockOrchestrator:
    """Orchestrates multiple threaded producers for DC-Mock service."""

    def __init__(self):
        """Initialize the orchestrator."""
        self.topology_producer: TopologyProducer | None = None
        self.workload_producer: WorkloadProducer | None = None
        self.power_producer: PowerProducer | None = None
        self.shutdown_requested = False

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
            self.stop_all()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start_all(
        self,
        workload_context,
        kafka_bootstrap_servers: str,
        speed_factor: float,
        topology_topic: str,
        workload_topic: str,
        power_topic: str,
        heartbeat_frequency_minutes: int = 1,
    ) -> None:
        """Start all producers.

        Args:
            workload_context: Workload context with resolved file paths
            kafka_bootstrap_servers: Kafka broker addresses
            speed_factor: Simulation speed multiplier
            topology_topic: Kafka topic for topology events
            workload_topic: Kafka topic for workload events
            power_topic: Kafka topic for power consumption events
            heartbeat_frequency_minutes: Frequency in simulation minutes for heartbeat messages
        """
        logger.info("=" * 70)
        logger.info("Starting DC-Mock Producers")
        logger.info("=" * 70)

        # Create a synchronization barrier for all producers
        # This ensures they all start at the same wall-clock time
        num_producers = 2  # WorkloadProducer and PowerProducer (TopologyProducer is periodic)
        if workload_context.consumption_file.exists():
            start_barrier = threading.Barrier(num_producers, timeout=30)
            logger.info(f"Created start barrier for {num_producers} producers")
        else:
            start_barrier = None
            logger.info("No barrier needed (only workload producer active)")

        # 1. Start WorkloadProducer first (we need earliest_task_time for PowerProducer)
        logger.info("\n[1/3] Initializing WorkloadProducer...")
        self.workload_producer = WorkloadProducer(
            workload_context=workload_context,
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            speed_factor=speed_factor,
            topic=workload_topic,
            heartbeat_frequency_minutes=heartbeat_frequency_minutes,
            start_barrier=start_barrier if start_barrier else None,
        )

        # Quick-load tasks file to get earliest time (for PowerProducer initialization)
        # The full loading will happen in the WorkloadProducer's run() method
        logger.info("Quick-loading tasks to get earliest submission time...")
        import pandas as pd

        tasks_df = pd.read_parquet(workload_context.tasks_file)
        earliest_task_time = tasks_df["submission_time"].min().to_pydatetime()
        earliest_task_time_ms = int(earliest_task_time.timestamp() * 1000)
        logger.info(f"Earliest task time: {earliest_task_time} ({earliest_task_time_ms}ms)")
        del tasks_df  # Free memory

        # Start workload producer thread
        self.workload_producer.start()

        # 2. Start PowerProducer
        logger.info("\n[2/3] Initializing PowerProducer...")
        if workload_context.consumption_file.exists():
            self.power_producer = PowerProducer(
                workload_context=workload_context,
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                speed_factor=speed_factor,
                topic=power_topic,
                earliest_task_time_ms=earliest_task_time_ms,
                start_barrier=start_barrier,
            )
            self.power_producer.start()
        else:
            logger.warning(
                f"Consumption file not found: {workload_context.consumption_file}, "
                "skipping power consumption streaming"
            )

        # 3. Start TopologyProducer (no barrier needed, it's periodic)
        logger.info("\n[3/3] Initializing TopologyProducer...")
        if workload_context.topology_file.exists():
            self.topology_producer = TopologyProducer(
                topology_file=workload_context.topology_file,
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                speed_factor=speed_factor,
                topic=topology_topic,
                publish_interval_seconds=30.0,
                start_barrier=None,  # TopologyProducer doesn't need synchronization
            )
            self.topology_producer.start()
        else:
            logger.warning(
                f"Topology file not found: {workload_context.topology_file}, "
                "skipping topology publishing"
            )

        logger.info("\n" + "=" * 70)
        logger.info("✅ All producers started and synchronized")
        logger.info("=" * 70)

    def wait_for_completion(self) -> None:
        """Wait for all producers to complete or be interrupted."""
        logger.info("\nWaiting for producers to complete...")

        try:
            # Wait for workload producer (main event stream)
            if self.workload_producer and self.workload_producer._thread:
                if self.workload_producer.is_running():
                    logger.info("Waiting for WorkloadProducer to finish...")
                    self.workload_producer._thread.join()

            # Wait for power producer
            if self.power_producer and self.power_producer._thread:
                if self.power_producer.is_running():
                    logger.info("Waiting for PowerProducer to finish...")
                    self.power_producer._thread.join()

            # Topology producer runs indefinitely, so we stop it explicitly
            if self.topology_producer and self.topology_producer.is_running():
                logger.info("Stopping TopologyProducer...")
                self.topology_producer.stop()

            logger.info("All producers completed")

        except KeyboardInterrupt:
            logger.info("Received interrupt during wait")
            self.stop_all()

    def stop_all(self) -> None:
        """Stop all running producers."""
        logger.info("\n" + "=" * 70)
        logger.info("Stopping all producers...")
        logger.info("=" * 70)

        producers = [
            ("TopologyProducer", self.topology_producer),
            ("WorkloadProducer", self.workload_producer),
            ("PowerProducer", self.power_producer),
        ]

        for name, producer in producers:
            if producer and producer.is_running():
                logger.info(f"Stopping {name}...")
                producer.stop(timeout=5.0)
            elif producer:
                logger.info(f"{name} already stopped")

        logger.info("=" * 70)
        logger.info("✅ All producers stopped")
        logger.info("=" * 70)

    def run(self) -> int:
        """Run the orchestrator.

        Returns:
            Exit code: 0 for success, 1 for error
        """
        try:
            # Load configuration
            logger.info("Loading configuration...")
            config = load_config_from_env()
            logger.info(f"Loaded configuration for workload: {config.workload}")
            logger.info(f"Simulation speed: {config.global_config.speed_factor}x")

            # Get workload context
            workload_path = Path(os.getenv("WORKLOAD_PATH", "/app/workload"))
            workload_context = config.get_workload_context(base_path=workload_path)

            # Verify workload directory exists
            if not workload_context.exists():
                logger.error(f"Workload directory not found: {workload_context.workload_dir}")
                logger.info("Available workloads:")
                for item in workload_path.iterdir():
                    if item.is_dir():
                        logger.info(f"  - {item.name}")
                return 1

            # Log file status
            file_status = workload_context.get_file_status()
            logger.info("Workload files:")
            for file_type, exists in file_status.items():
                status = "✓" if exists else "✗"
                logger.info(f"  {status} {file_type}")

            # Get Kafka configuration from environment variable
            kafka_bootstrap_servers = get_kafka_bootstrap_servers()
            logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")

            # Get topic names
            topology_topic = config.kafka.topics["topology"].name
            workload_topic = config.kafka.topics["workload"].name
            power_topic = config.kafka.topics["power"].name
            logger.info(
                f"Topics: topology={topology_topic}, workload={workload_topic}, power={power_topic}"
            )

            # Setup signal handlers
            self.setup_signal_handlers()

            # Start all producers
            self.start_all(
                workload_context=workload_context,
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                speed_factor=config.global_config.speed_factor,
                topology_topic=topology_topic,
                workload_topic=workload_topic,
                power_topic=power_topic,
                heartbeat_frequency_minutes=config.services.dc_mock.heartbeat_frequency_minutes,
            )

            # Wait for completion
            self.wait_for_completion()

            logger.info("✅ DC-Mock service completed successfully")
            return 0

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop_all()
            return 0
        except Exception as e:
            logger.error(f"❌ Error in DC-Mock service: {e}", exc_info=True)
            self.stop_all()
            return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code: 0 for success, 1 for error
    """
    orchestrator = DCMockOrchestrator()
    return orchestrator.run()


if __name__ == "__main__":
    sys.exit(main())
