"""dc-mock: replays the workload, power, and topology of the datacenter onto Kafka, at the replay speed."""

import logging
import os
import signal
import sys
import threading
from pathlib import Path

from odt_common import load_config_from_env
from odt_common.utils import get_kafka_bootstrap_servers

from dc_mock.producers import PowerProducer, TopologyProducer, WorkloadProducer
from dc_mock.speed import Speed, follow

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DCMockOrchestrator:
    """The three producers, each on its own thread."""

    def __init__(self):
        self.topology_producer: TopologyProducer | None = None
        self.workload_producer: WorkloadProducer | None = None
        self.power_producer: PowerProducer | None = None
        self.shutdown_requested = False

    def setup_signal_handlers(self) -> None:
        """Stop the producers on SIGINT and SIGTERM."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, stopping")
            self.shutdown_requested = True
            self.stop_all()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start_all(
        self,
        workload_context,
        kafka_bootstrap_servers: str,
        speed: Speed,
        topology_topic: str,
        workload_topic: str,
        power_topic: str,
        heartbeat_frequency_minutes: int = 1,
    ) -> None:
        """Start the producers, with the heartbeats every `heartbeat_frequency_minutes` of the trace."""
        logger.info("Starting DC-Mock Producers")

        # the workload and power producers start at the same wall-clock time
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
            speed=speed,
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

        self.workload_producer.start()

        # 2. Start PowerProducer
        logger.info("\n[2/3] Initializing PowerProducer...")
        if workload_context.consumption_file.exists():
            self.power_producer = PowerProducer(
                workload_context=workload_context,
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                speed=speed,
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
                speed=speed,
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

        logger.info("All producers started and synchronized")

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
        logger.info("Stopping all producers...")

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

        logger.info("All producers stopped")

    def run(self) -> int:
        """Replay the workload until it ends; the exit code is 0, or 1 on an error."""
        try:
            logger.info("Loading configuration...")
            config = load_config_from_env()
            logger.info(f"Loaded configuration for workload: {config.workload}")
            logger.info(f"Simulation speed: {config.global_config.speed_factor}x")

            workload_dir = Path(os.getenv("WORKLOAD_DIR", "/app/workload"))

            if not workload_dir.exists():
                logger.error(f"Workload directory not found: {workload_dir}")
                return 1

            from odt_common.config import WorkloadContext

            workload_context = WorkloadContext(workload_dir=workload_dir)

            file_status = workload_context.get_file_status()
            logger.info("Workload files:")
            for file_type, exists in file_status.items():
                logger.info(f"  {file_type}: {'found' if exists else 'missing'}")

            kafka_bootstrap_servers = get_kafka_bootstrap_servers()
            logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")

            topology_topic = config.kafka.topics["topology"].name
            workload_topic = config.kafka.topics["workload"].name
            power_topic = config.kafka.topics["power"].name
            logger.info(
                f"Topics: topology={topology_topic}, workload={workload_topic}, power={power_topic}"
            )

            self.setup_signal_handlers()

            # The replay speed starts as configured and follows changes from the control panel
            speed = Speed(config.global_config.speed_factor)
            follow(speed, config.kafka.topics["system"].name)

            self.start_all(
                workload_context=workload_context,
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                speed=speed,
                topology_topic=topology_topic,
                workload_topic=workload_topic,
                power_topic=power_topic,
                heartbeat_frequency_minutes=config.services.dc_mock.heartbeat_frequency_minutes,
            )

            self.wait_for_completion()

            logger.info("DC-Mock service completed successfully")
            return 0

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop_all()
            return 0
        except Exception as e:
            logger.error(f"Error in DC-Mock service: {e}", exc_info=True)
            self.stop_all()
            return 1


def main() -> int:
    orchestrator = DCMockOrchestrator()
    return orchestrator.run()


if __name__ == "__main__":
    sys.exit(main())
