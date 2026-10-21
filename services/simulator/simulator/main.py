"""The simulator: runs OpenDC on the replayed workload, one window of operation at a time."""

import copy
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from odt_common import ResultCache, TaskAccumulator, load_config_from_env
from odt_common.config import SCHEDULER, DynamicConfigEvent
from odt_common.models import Task, Topology, TopologySnapshot
from odt_common.odc_runner import OpenDCRunner
from odt_common.utils import get_kafka_bootstrap_servers, get_kafka_consumer

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
        system_topic: str,
        simulation_frequency_minutes: int,
        run_output_dir: str,
        run_id: str,
        background_load_nodes: int = 0,
        consumer_group: str = "simulators",
    ):
        """Initialize the simulation service."""
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.topology_topic = topology_topic
        self.sim_topology_topic = sim_topology_topic
        self.system_topic = system_topic
        self.simulation_frequency = timedelta(minutes=simulation_frequency_minutes)
        self.run_id = run_id
        self.background_load_nodes = background_load_nodes

        self.output_base_dir = Path(run_output_dir) / run_id / "simulator"
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Simulator output directory: {self.output_base_dir}")

        self.result_processor = SimulationResultProcessor(self.output_base_dir)
        logger.info("Initialized result processor")

        topics = [workload_topic, topology_topic, sim_topology_topic, system_topic]
        self.consumer = get_kafka_consumer(
            topics=topics,
            group_id=consumer_group,
            bootstrap_servers=kafka_bootstrap_servers,
        )

        self.task_accumulator = TaskAccumulator()

        try:
            self.opendc_runner = OpenDCRunner()
        except FileNotFoundError as e:
            logger.error(f"Failed to initialize OpenDC runner: {e}")
            logger.error("Simulation will not be available")
            self.opendc_runner = None

        # Topology state
        self.real_topology: Topology | None = None
        self.simulated_topology: Topology | None = None
        self.scheduler: str | None = None  # OpenDC's default until the control panel picks one

        self.tasks_processed = 0
        self.run_number = 0

        self.result_cache = ResultCache()

        logger.info(f"Initialized SimulationService with run ID: {run_id}")
        logger.info(f"Consumer group: {consumer_group}")
        logger.info(f"Subscribed: {workload_topic}, {topology_topic}, {sim_topology_topic}")
        logger.info(
            f"Simulation frequency: {simulation_frequency_minutes} minutes (simulated time)"
        )
        logger.info(f"Background load nodes: {background_load_nodes}")

    def _reduce_topology_for_background_load(self, topology: Topology) -> Topology:
        """Create a topology with reduced host count to simulate background load.

        Subtracts background_load_nodes from the first host type in the first cluster.
        This simulates nodes being occupied by background workload and unavailable
        for the simulation.
        """
        if self.background_load_nodes == 0:
            return topology

        reduced = copy.deepcopy(topology)

        if not reduced.clusters or not reduced.clusters[0].hosts:
            logger.warning("Topology has no clusters or hosts, cannot reduce")
            return topology

        first_host = reduced.clusters[0].hosts[0]
        original_count = first_host.count

        if self.background_load_nodes >= original_count:
            logger.warning(
                f"background_load_nodes ({self.background_load_nodes}) >= "
                f"available hosts ({original_count}) in first cluster, "
                f"setting to {original_count - 1}"
            )
            first_host.count = max(1, original_count - self.background_load_nodes)
        else:
            first_host.count = original_count - self.background_load_nodes

        logger.info(
            f"Reduced topology: {original_count} -> {first_host.count} hosts "
            f"in cluster '{reduced.clusters[0].name}' ({self.background_load_nodes} for background load)"
        )

        return reduced

    def _run_simulation(self) -> None:
        """Run OpenDC simulation with accumulated tasks."""
        if not self.opendc_runner:
            logger.warning("OpenDC runner not available, skipping simulation")
            return

        if not self.simulated_topology:
            logger.warning("No topology available, skipping simulation")
            return

        all_tasks = self.task_accumulator.get_all_tasks()

        if not all_tasks:
            logger.info("No tasks to simulate, skipping")
            return

        first_task_time = min(task.submission_time for task in all_tasks)
        latest_task_time = max(task.submission_time for task in all_tasks)
        task_span_minutes = (latest_task_time - first_task_time).total_seconds() / 60

        aligned_simulated_time = self.task_accumulator.get_next_simulation_time(
            self.simulation_frequency
        )
        if aligned_simulated_time is None:
            logger.error("Cannot calculate aligned simulation time")
            return

        logger.info(f"Simulation Run {self.run_number + 1}")
        logger.info(
            f"OpenDC Input Data:\n"
            f"   Total tasks:      {len(all_tasks)}\n"
            f"   First task:       {first_task_time.isoformat()}\n"
            f"   Latest task:      {latest_task_time.isoformat()}\n"
            f"   Time span:        {task_span_minutes:.1f} minutes\n"
            f"   Simulation end:   {aligned_simulated_time.isoformat()}"
        )

        self.run_number += 1

        topology_to_use = self._reduce_topology_for_background_load(self.simulated_topology)

        run_dir = self.output_base_dir / "opendc" / f"run_{self.run_number}"
        was_cached = False

        if self.result_cache.can_reuse(topology_to_use, self.scheduler, len(all_tasks)):
            logger.info(
                f"Reusing cached results for run {self.run_number} "
                f"(topology unchanged, {len(all_tasks)} tasks)"
            )

            # Copy the cached run, without its metadata.json, to the new run location
            cached_run_dir = self.result_cache.get_cached_run_dir()
            if cached_run_dir:
                self.result_cache.copy_to_new_run(cached_run_dir, run_dir)

                # The cached run's metadata with the new time, written last: a run with
                # metadata.json counts as complete
                metadata = json.loads((cached_run_dir / "metadata.json").read_text())
                metadata["simulated_time"] = aligned_simulated_time.replace(
                    microsecond=0
                ).isoformat()
                metadata["wall_clock_time"] = (
                    datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()
                )
                metadata["cached"] = True
                (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

                logger.info(f"Cached results copied to run_{self.run_number}")
                was_cached = True
        else:
            logger.info(f"Running simulation {self.run_number} with {len(all_tasks)} tasks")

            success, _ = self.opendc_runner.run_simulation(
                tasks=all_tasks,
                topology=topology_to_use,
                run_dir=run_dir,
                run_number=self.run_number,
                simulated_time=aligned_simulated_time,
                timeout_seconds=120,
                scheduler=self.scheduler,
            )

            if not success:
                logger.error(f"Simulation {self.run_number} failed")
                return

            # Update cache with run directory (not output directory)
            self.result_cache.update(topology_to_use, self.scheduler, len(all_tasks), run_dir)
            logger.info(f"Simulation {self.run_number} complete, results cached")

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

        self.task_accumulator.last_simulation_time = aligned_simulated_time

        logger.info(
            f"Total Stats: {self.tasks_processed} tasks processed, "
            f"{self.run_number} simulations completed\n"
        )

    def _process_workload_message(self, message_data: dict[str, Any]) -> None:
        """A task joins the accumulated ones; a heartbeat may start a window of operation."""
        message_type = message_data.get("message_type")
        if message_type == "task":
            task = Task(**message_data["task"])
            logger.debug(f"Received task {task.id} at {task.submission_time}")
            self.task_accumulator.add_task(task)
            self.tasks_processed += 1
        elif message_type == "heartbeat":
            heartbeat_time = datetime.fromisoformat(message_data["timestamp"])
            if self.task_accumulator.should_simulate(heartbeat_time, self.simulation_frequency):
                self._run_simulation()
        else:
            logger.warning(f"Unknown message_type: {message_type}")

    def _process_topology_message(self, message_data: dict[str, Any]) -> None:
        """The real topology; the simulated one starts as a copy of it."""
        self.real_topology = TopologySnapshot(**message_data).topology
        if self.simulated_topology is None:
            self.simulated_topology = copy.deepcopy(self.real_topology)
            logger.info("Initialized simulated topology from real topology")

    def _process_topology_update_message(self, message_data: dict[str, Any]) -> None:
        """A new simulated topology (a Topology, not a TopologySnapshot)."""
        self.simulated_topology = Topology(**message_data)
        logger.info(f"Simulated topology: {self.simulated_topology.total_host_count()} hosts")

    def _process_config_event(self, message_data: dict[str, Any]) -> None:
        """Follow a scheduler change; the other runtime settings are not the simulator's."""
        event = DynamicConfigEvent(**message_data)
        if event.setting_key == SCHEDULER and event.new_value != self.scheduler:
            self.scheduler = event.new_value
            logger.info(f"Scheduler: {self.scheduler}")

    def process_message(self, message):
        """Process a single Kafka message."""
        topic = message.topic
        value = message.value

        try:
            if topic == self.workload_topic:
                self._process_workload_message(value)
            elif topic == self.topology_topic:
                self._process_topology_message(value)
            elif topic == self.sim_topology_topic:
                self._process_topology_update_message(value)
            else:  # the system topic, the last one the consumer follows
                self._process_config_event(value)
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
        finally:
            logger.info("Closing Kafka connections...")
            self.consumer.close()
            logger.info("Simulation service stopped")


def main():
    config = load_config_from_env()
    logger.info(f"Loaded configuration for workload: {config.workload}")

    kafka_bootstrap_servers = get_kafka_bootstrap_servers()
    workload_topic = config.kafka.topics["workload"].name
    topology_topic = config.kafka.topics["topology"].name
    sim_topology_topic = config.kafka.topics["sim_topology"].name
    system_topic = config.kafka.topics["system"].name

    simulation_frequency_minutes = config.services.simulator.simulation_frequency_minutes
    background_load_nodes = config.services.simulator.background_load_nodes
    run_output_dir = Path(os.getenv("DATA_DIR", "/app/data"))

    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")
    logger.info(f"Workload topic: {workload_topic}")
    logger.info(f"Topology topic: {topology_topic}")
    logger.info(f"Simulated topology topic: {sim_topology_topic}")
    logger.info(f"Simulation frequency: {simulation_frequency_minutes} minutes")
    logger.info(f"Background load nodes: {background_load_nodes}")
    logger.info(f"Data directory: {run_output_dir}")

    run_id = os.getenv("RUN_ID")
    if not run_id:
        logger.error("RUN_ID environment variable not set")
        raise ValueError("RUN_ID environment variable is required")

    logger.info(f"Run ID: {run_id}")

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
                system_topic=system_topic,
                simulation_frequency_minutes=simulation_frequency_minutes,
                run_output_dir=str(run_output_dir),
                run_id=run_id,
                background_load_nodes=background_load_nodes,
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
