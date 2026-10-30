"""dc-mock: replays the workload, power, and topology of the datacenter onto Kafka, at the replay speed."""

import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from odt_common import Topology, TopologySnapshot, load_config_from_env
from odt_common.utils import get_kafka_bootstrap_servers, get_kafka_producer, send_message

from dc_mock.producers import PowerProducer, WorkloadProducer
from dc_mock.speed import Speed, follow

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def publish_topology(topology_file: Path, topic: str) -> None:
    """The datacenter's topology, once, before the replay: the simulator and the calibrator start from it."""
    topology = Topology(**json.loads(topology_file.read_text()))
    snapshot = TopologySnapshot(timestamp=datetime.now(), topology=topology)
    producer = get_kafka_producer()
    send_message(producer, topic, snapshot.model_dump(mode="json"), key="datacenter")
    producer.close()
    logger.info(f"Published the topology: {topology.total_host_count()} hosts")


class DCMockOrchestrator:
    """The workload and power producers, each on its own thread."""

    def __init__(self):
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
        speed: Speed,
        topology_topic: str,
        workload_topic: str,
        power_topic: str,
        heartbeat_frequency_minutes: int = 1,
    ) -> None:
        """Start the producers, with the heartbeats every `heartbeat_frequency_minutes` of the trace."""
        logger.info("Starting DC-Mock Producers")
        if workload_context.topology_file.exists():
            publish_topology(workload_context.topology_file, topology_topic)
        else:
            logger.warning(f"Topology file not found: {workload_context.topology_file}")

        self.workload_producer = WorkloadProducer(
            workload_context=workload_context,
            speed=speed,
            topic=workload_topic,
            heartbeat_frequency_minutes=heartbeat_frequency_minutes,
        )

        # the power's timestamps count from the first task, read here as the workload loads them later
        tasks_df = pd.read_parquet(workload_context.tasks_file, columns=["submission_time"])
        earliest_task_time = tasks_df["submission_time"].min().to_pydatetime()
        earliest_task_time_ms = int(earliest_task_time.timestamp() * 1000)
        logger.info(f"Earliest task time: {earliest_task_time} ({earliest_task_time_ms}ms)")

        self.workload_producer.start()

        if workload_context.consumption_file.exists():
            self.power_producer = PowerProducer(
                workload_context=workload_context,
                speed=speed,
                topic=power_topic,
                earliest_task_time_ms=earliest_task_time_ms,
            )
            self.power_producer.start()
        else:
            logger.warning(
                f"Consumption file not found: {workload_context.consumption_file}, "
                "skipping power consumption streaming"
            )

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

            logger.info("All producers completed")

        except KeyboardInterrupt:
            logger.info("Received interrupt during wait")
            self.stop_all()

    def stop_all(self) -> None:
        """Stop all running producers."""
        logger.info("Stopping all producers...")

        producers = [
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
            logger.info(f"Kafka bootstrap servers: {get_kafka_bootstrap_servers()}")

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
