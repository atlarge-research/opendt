"""Simulator Service - Main Entry Point."""

import copy
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from odt_common import ResultCache, TaskAccumulator, load_config_from_env
from odt_common.models import Task, Topology, TopologySnapshot
from odt_common.odc_runner import OpenDCRunner
from odt_common.utils import get_kafka_bootstrap_servers, get_kafka_consumer, get_kafka_producer

from simulator.result_processor import SimulationResultProcessor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimulationService:
    """Core simulation service that processes workload and runs OpenDC simulations.

    The service:
    1. Listens to dc.workload (tasks) and dc.topology (topology snapshots)
    2. Accumulates tasks chronologically
    3. Triggers simulations at specified frequency (simulated time)
    4. Caches results based on topology hash + task count
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        workload_topic: str,
        topology_topic: str,
        sim_topology_topic: str,
        simulation_frequency_minutes: int,
        run_output_dir: str,
        run_id: str,
        consumer_group: str = "simulators",
    ):
        """Initialize the simulation service.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            workload_topic: Kafka topic name for workload events (dc.workload)
            topology_topic: Kafka topic name for topology updates (dc.topology)
            sim_topology_topic: Kafka topic name for simulated topology updates (sim.topology)
            simulation_frequency_minutes: Simulation frequency in simulated time minutes
            run_output_dir: Base directory for run outputs
            run_id: Unique run ID for this session
            consumer_group: Kafka consumer group ID
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.topology_topic = topology_topic
        self.sim_topology_topic = sim_topology_topic
        self.simulation_frequency = timedelta(minutes=simulation_frequency_minutes)
        self.run_id = run_id

        # Setup output directories - simulator writes to run_dir/simulator/
        self.output_base_dir = Path(run_output_dir) / run_id / "simulator"
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Simulator output directory: {self.output_base_dir}")

        # Initialize result processor for aggregating simulation outputs
        self.result_processor = SimulationResultProcessor(self.output_base_dir)
        logger.info("Initialized result processor")

        # Initialize Kafka consumer
        topics = [workload_topic, topology_topic, sim_topology_topic]
        self.consumer = get_kafka_consumer(
            topics=topics,
            group_id=consumer_group,
            bootstrap_servers=kafka_bootstrap_servers,
        )

        # Initialize Kafka producer (for future use)
        self.producer = get_kafka_producer(kafka_bootstrap_servers)

        # Initialize task accumulator
        self.task_accumulator = TaskAccumulator()

        # Initialize OpenDC runner
        try:
            self.opendc_runner = OpenDCRunner()
        except FileNotFoundError as e:
            logger.error(f"Failed to initialize OpenDC runner: {e}")
            logger.error("Simulation will not be available")
            self.opendc_runner = None

        # Topology state
        self.real_topology: Topology | None = None
        self.simulated_topology: Topology | None = None

        # Statistics
        self.tasks_processed = 0
        self.simulations_run = 0
        self.run_number = 0

        # Initialize result cache
        self.result_cache = ResultCache()

        logger.info(f"Initialized SimulationService with run ID: {run_id}")
        logger.info(f"Consumer group: {consumer_group}")
        logger.info(f"Subscribed: {workload_topic}, {topology_topic}, {sim_topology_topic}")
        logger.info(
            f"Simulation frequency: {simulation_frequency_minutes} minutes (simulated time)"
        )

    def _run_simulation(self) -> None:
        """Run OpenDC simulation with accumulated tasks.

        Args:
            heartbeat_time: Timestamp that triggered this simulation
        """
        if not self.opendc_runner:
            logger.warning("OpenDC runner not available, skipping simulation")
            return

        if not self.simulated_topology:
            logger.warning("No topology available, skipping simulation")
            return

        # Get all accumulated tasks
        all_tasks = self.task_accumulator.get_all_tasks()

        if not all_tasks:
            logger.info("No tasks to simulate, skipping")
            return

        # Calculate aligned simulation time
        aligned_simulated_time = self.task_accumulator.get_next_simulation_time(
            self.simulation_frequency
        )
        if aligned_simulated_time is None:
            logger.error("Cannot calculate aligned simulation time")
            return

        # Increment run number
        self.run_number += 1

        # Check if we can reuse cached results
        topology_to_use = self.simulated_topology

        # Create directories
        run_dir = self.output_base_dir / "opendc" / f"run_{self.run_number}"
        was_cached = False

        if self.result_cache.can_reuse(topology_to_use, len(all_tasks)):
            logger.info(
                f"♻️  Reusing cached results for run {self.run_number} "
                f"(topology unchanged, {len(all_tasks)} tasks)"
            )

            # Copy entire cached run directory to new run location
            cached_run_dir = self.result_cache.get_cached_run_dir()
            if cached_run_dir:
                self.result_cache.copy_to_new_run(cached_run_dir, run_dir)

                # Update metadata with new timestamp and cached flag
                metadata_file = run_dir / "metadata.json"
                metadata = json.loads(metadata_file.read_text())
                metadata["simulated_time"] = aligned_simulated_time.replace(
                    microsecond=0
                ).isoformat()
                metadata["wall_clock_time"] = (
                    datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()
                )
                metadata["cached"] = True
                metadata_file.write_text(json.dumps(metadata, indent=2))

                logger.info(f"✅ Cached results copied to run_{self.run_number}")
                was_cached = True
        else:
            # Run new simulation
            logger.info(f"Running simulation {self.run_number} with {len(all_tasks)} tasks")

            success, _ = self.opendc_runner.run_simulation(
                tasks=all_tasks,
                topology=topology_to_use,
                run_dir=run_dir,
                run_number=self.run_number,
                simulated_time=aligned_simulated_time,
                timeout_seconds=120,
            )

            if not success:
                logger.error(f"Simulation {self.run_number} failed")
                return

            # Update cache with run directory (not output directory)
            self.result_cache.update(topology_to_use, len(all_tasks), run_dir)
            logger.info(f"✅ Simulation {self.run_number} complete, results cached")

        # Process and aggregate simulation results
        output_dir = run_dir / "output"
        try:
            self.result_processor.process_simulation_results(
                run_number=self.run_number,
                output_dir=output_dir,
                aligned_simulated_time=aligned_simulated_time,
                cached=was_cached,
            )
        except Exception as e:
            logger.error(f"Failed to process simulation results: {e}", exc_info=True)

        # Update statistics and simulation time
        self.simulations_run += 1
        self.task_accumulator.last_simulation_time = aligned_simulated_time

        logger.info(
            f"📊 Stats: {self.tasks_processed} tasks processed, "
            f"{self.simulations_run} simulations run"
        )

    def _process_workload_message(self, message_data: dict[str, Any]) -> None:
        """Process a workload message (task or heartbeat) from Kafka.

        Args:
            message_data: Raw message data from Kafka
        """
        try:
            message_type = message_data.get("message_type")

            if message_type == "task":
                # Extract task
                task = Task(**message_data["task"])
                logger.debug(
                    f"Received task {task.id} at {task.submission_time} "
                    f"with {len(task.fragments)} fragments"
                )

                # Add to accumulator
                self.task_accumulator.add_task(task)
                self.tasks_processed += 1

            elif message_type == "heartbeat":
                # Parse heartbeat timestamp
                heartbeat_time = datetime.fromisoformat(message_data["timestamp"])
                logger.debug(f"Received heartbeat at {heartbeat_time}")

                # Check if we should trigger simulation
                if self.task_accumulator.should_simulate(heartbeat_time, self.simulation_frequency):
                    self._run_simulation()

            else:
                logger.warning(f"Unknown message_type: {message_type}")

        except Exception as e:
            logger.error(f"Error processing workload message: {e}", exc_info=True)

    def _process_topology_message(self, message_data: dict[str, Any]) -> None:
        """Process a topology message from Kafka.

        Args:
            message_data: Raw message data from Kafka
        """
        try:
            # Parse into TopologySnapshot model
            topology_snapshot = TopologySnapshot(**message_data)

            logger.debug(
                f"📡 Received topology snapshot (timestamp: {topology_snapshot.timestamp})"
            )

            # Update real topology
            self.real_topology = topology_snapshot.topology

            # Initialize simulated topology if not set
            if self.simulated_topology is None:
                # Deep copy so we can modify it independently
                self.simulated_topology = copy.deepcopy(self.real_topology)
                logger.info("Initialized simulated topology from real topology")

        except Exception as e:
            logger.error(f"Error processing topology message: {e}", exc_info=True)

    def _process_topology_update_message(self, message_data: dict[str, Any]) -> None:
        """Process a simulated topology update message from Kafka.

        Args:
            message_data: Raw message data from Kafka (raw Topology, not TopologySnapshot)
        """
        try:
            # Parse into Topology model (not TopologySnapshot)
            topology = Topology(**message_data)

            logger.info(
                f"🔄 Received simulated topology update: {len(topology.clusters)} cluster(s)"
            )

            # Update simulated topology
            self.simulated_topology = topology

            # Clear result cache since topology changed
            self.result_cache.clear()
            logger.info("🗑️  Cleared result cache due to topology update")

            # Log update details
            total_hosts = sum(host.count for cluster in topology.clusters for host in cluster.hosts)
            logger.info(f"   Total hosts: {total_hosts}")

        except Exception as e:
            logger.error(f"Error processing topology update message: {e}", exc_info=True)

    def process_message(self, message):
        """Process a single Kafka message.

        Args:
            message: Kafka message
        """
        topic = message.topic
        value = message.value

        try:
            if topic == self.workload_topic:
                self._process_workload_message(value)
            elif topic == self.topology_topic:
                self._process_topology_message(value)
            elif topic == self.sim_topology_topic:
                self._process_topology_update_message(value)
            else:
                logger.warning(f"Unknown topic: {topic}")

        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}", exc_info=True)

    def run(self):
        """Run the simulation service (main event loop)."""
        logger.info("Starting Simulation Service")
        logger.info("Waiting for messages...")

        try:
            for message in self.consumer:
                self.process_message(message)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")

        except Exception as e:
            logger.error(f"Error in simulation service: {e}", exc_info=True)
            raise

        finally:
            logger.info("Closing Kafka connections...")
            self.consumer.close()
            self.producer.close()
            logger.info("Simulation service stopped")


def main():
    """Main entry point."""
    # Load configuration from environment
    try:
        config = load_config_from_env()
        logger.info(f"Loaded configuration for workload: {config.workload}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Get Kafka configuration from environment variable
    kafka_bootstrap_servers = get_kafka_bootstrap_servers()
    workload_topic = config.kafka.topics["workload"].name
    topology_topic = config.kafka.topics["topology"].name
    sim_topology_topic = config.kafka.topics["sim_topology"].name

    # Get simulator configuration
    simulation_frequency_minutes = config.services.simulator.simulation_frequency_minutes
    run_output_dir = Path(os.getenv("DATA_DIR", "/app/data"))

    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")
    logger.info(f"Workload topic: {workload_topic}")
    logger.info(f"Topology topic: {topology_topic}")
    logger.info(f"Simulated topology topic: {sim_topology_topic}")
    logger.info(f"Simulation frequency: {simulation_frequency_minutes} minutes")
    logger.info(f"Data directory: {run_output_dir}")

    # Get run ID from environment
    run_id = os.getenv("RUN_ID")
    if not run_id:
        logger.error("RUN_ID environment variable not set")
        raise ValueError("RUN_ID environment variable is required")

    logger.info(f"Run ID: {run_id}")

    # Get consumer group from environment
    consumer_group = os.getenv("CONSUMER_GROUP", "simulators")

    # Wait for Kafka to be ready
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to Kafka (attempt {attempt + 1}/{max_retries})")
            service = SimulationService(
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                workload_topic=workload_topic,
                topology_topic=topology_topic,
                sim_topology_topic=sim_topology_topic,
                simulation_frequency_minutes=simulation_frequency_minutes,
                run_output_dir=str(run_output_dir),
                run_id=run_id,
                consumer_group=consumer_group,
            )
            service.run()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error("Failed to connect to Kafka after maximum retries")
                raise


if __name__ == "__main__":
    main()
