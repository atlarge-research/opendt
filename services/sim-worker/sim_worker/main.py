"""Sim-Worker Service - Main Entry Point."""

import copy
import logging
import os
import time
from datetime import datetime
from typing import Any

from opendt_common import load_config_from_env
from opendt_common.models import Task, Topology, TopologySnapshot
from opendt_common.utils import get_kafka_consumer, get_kafka_producer

from .experiment_manager import ExperimentManager
from .runner import OpenDCRunner, SimulationResults
from .window_manager import TimeWindow, WindowManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimulationWorker:
    """Consumes workload events from Kafka and runs simulations.

    The worker:
    1. Listens to dc.workload (tasks) and dc.topology (topology updates)
    2. Aggregates tasks into fixed time windows (default: 5 minutes)
    3. When a window closes, runs OpenDC simulation with:
       - Real topology (from dc.topology)
       - Simulated topology (operator-defined, initially same as real)
    4. Publishes simulation results to Kafka
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        worker_id: str,
        workload_topic: str,
        topology_topic: str,
        power_topic: str,
        results_topic: str,
        window_size_minutes: int,
        consumer_group: str = "sim-workers",
        debug_mode: bool = False,
        debug_output_dir: str = "/app/output",
        experiment_mode: bool = False,
        experiment_name: str = "default",
        experiment_output_dir: str = "/app/output",
    ):
        """Initialize the simulation worker.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            worker_id: Unique identifier for this worker
            workload_topic: Kafka topic name for workload events (dc.workload)
            topology_topic: Kafka topic name for topology updates (dc.topology)
            results_topic: Kafka topic name for simulation results
            window_size_minutes: Size of time windows in minutes
            consumer_group: Kafka consumer group ID
            debug_mode: If True, write debug files alongside main output
            debug_output_dir: Directory to write debug output files
            experiment_mode: If True, write results to parquet instead of Kafka
            experiment_name: Name of the experiment (used for output directory)
        """
        self.worker_id = worker_id
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.topology_topic = topology_topic
        self.power_topic = power_topic
        self.results_topic = results_topic
        self.debug_mode = debug_mode
        self.debug_output_dir = debug_output_dir
        self.experiment_mode = experiment_mode
        self.experiment_name = experiment_name

        # Initialize Kafka consumer (subscribe to workload, topology, and power in experiment mode)
        topics = [workload_topic, topology_topic]
        if self.experiment_mode:
            topics.append(power_topic)

        self.consumer = get_kafka_consumer(
            topics=topics,
            group_id=consumer_group,
            bootstrap_servers=kafka_bootstrap_servers,
        )

        # Initialize Kafka producer for results
        self.producer = get_kafka_producer(kafka_bootstrap_servers)

        # Initialize window manager
        self.window_manager = WindowManager(window_size_minutes=window_size_minutes)

        # Initialize OpenDC runner
        try:
            self.opendc_runner = OpenDCRunner()
        except FileNotFoundError as e:
            logger.error(f"Failed to initialize OpenDC runner: {e}")
            logger.error("Simulation will not be available")
            self.opendc_runner = None

        # Topology state
        self.real_topology: Topology | None = None
        self.simulated_topology: Topology | None = None  # Initially same as real

        # Statistics
        self.tasks_processed = 0
        self.windows_simulated = 0

        # Initialize result cache for avoiding redundant simulations
        from .result_cache import ResultCache

        self.result_cache = ResultCache()

        # Setup experiment mode
        self.experiment_manager: ExperimentManager | None = None
        if self.experiment_mode:
            run_number = ExperimentManager.get_next_run_number(
                experiment_name, experiment_output_dir
            )
            self.experiment_manager = ExperimentManager(
                experiment_name=experiment_name,
                experiment_output_dir=experiment_output_dir,
                run_number=run_number,
            )
            logger.info("🧪 EXPERIMENT MODE ENABLED")
            logger.info(f"   Experiment: {experiment_name}")
            logger.info(f"   Run: {run_number}")

        logger.info(f"Initialized SimulationWorker '{worker_id}' in group '{consumer_group}'")
        logger.info(f"Subscribed to topics: {workload_topic}, {topology_topic}")
        logger.info(f"Window size: {window_size_minutes} minutes")

    def _process_window(self, window: TimeWindow) -> None:
        """Process a closed window by running simulation.

        This triggers the simulation run for the closed window.

        Args:
            window: The window to process
        """
        logger.info(
            f"🎯 Window {window.window_id} closed "
            f"[{window.window_start} - {window.window_end}], "
            f"triggering simulation..."
        )

        if not self.opendc_runner:
            logger.warning("OpenDC runner not available, skipping simulation")
            return

        if not window.topology:
            logger.warning(f"Window {window.window_id} has no topology, skipping simulation")
            return

        # Get all tasks from window 0 up to this window (cumulative)
        all_tasks = self.window_manager.get_all_tasks_up_to_window(window.window_id)

        # Use simulated topology (initially same as real topology from first message)
        topology_to_use = self.simulated_topology if self.simulated_topology else window.topology

        # Check if we can reuse cached results (same topology + same task count)
        cached_results = self.result_cache.get_cached_results()
        if self.result_cache.can_reuse(topology_to_use, len(all_tasks)) and cached_results:
            logger.info(
                f"♻️  Reusing cached results for window {window.window_id} "
                f"(topology unchanged, {len(all_tasks)} cumulative tasks)"
            )
            simulated_results = cached_results
        else:
            # Run new simulation
            logger.info(
                f"Running simulation for window {window.window_id} "
                f"with {len(all_tasks)} cumulative tasks ({len(window.tasks)} new)"
            )
            simulated_results = self._run_simulation(
                window_id=window.window_id,
                tasks=all_tasks,
                topology=topology_to_use,
                topology_type="simulated",
            )
            # Update cache with new results
            self.result_cache.update(topology_to_use, len(all_tasks), simulated_results)

        # Handle results (write to parquet in experiment mode, or publish to Kafka)
        self._handle_results(window, simulated_results, all_tasks)

        self.windows_simulated += 1

        # Log statistics
        stats = self.window_manager.get_stats()
        logger.info(
            f"📊 Stats: {self.tasks_processed} tasks processed, "
            f"{self.windows_simulated} windows simulated, "
            f"{stats['total_windows']} total windows "
            f"({stats['open_windows']} open, {stats['closed_windows']} closed)"
        )

    def _run_simulation(
        self,
        window_id: int,
        tasks: list[Task],
        topology: Topology,
        topology_type: str,
    ) -> SimulationResults:
        """Run OpenDC simulation for a window.

        Args:
            window_id: Window ID
            tasks: List of tasks to simulate
            topology: Topology to use
            topology_type: "real" or "simulated"

        Returns:
            SimulationResults object
        """
        if not self.opendc_runner:
            return SimulationResults(status="error", error="OpenDC runner not initialized")

        experiment_name = f"window-{window_id}-{topology_type}"

        try:
            results = self.opendc_runner.run_simulation(
                tasks=tasks,
                topology=topology,
                experiment_name=experiment_name,
                timeout_seconds=120,
            )

            logger.info(
                f"✅ Simulation ({topology_type}) for window {window_id}: "
                f"energy={results.energy_kwh:.4f} kWh, "
                f"cpu_util={results.cpu_utilization:.3f}, "
                f"max_power={results.max_power_draw:.1f} W"
            )

            return results

        except Exception as e:
            logger.error(f"Error running simulation ({topology_type}): {e}", exc_info=True)
            return SimulationResults(status="error", error=str(e))

    def _handle_results(
        self,
        window: TimeWindow,
        simulated_results: SimulationResults,
        cumulative_tasks: list[Task],
    ) -> None:
        """Handle simulation results (write to parquet in experiment mode, or publish to Kafka).

        Args:
            window: The window that was simulated
            simulated_results: Results from simulated topology simulation
            cumulative_tasks: All tasks from window 0 up to this window (used in simulation)
        """
        # Experiment mode: write results parquet, OpenDC I/O files, and update plot
        if self.experiment_mode and self.experiment_manager:
            try:
                self.experiment_manager.write_simulation_results(
                    window, simulated_results, cumulative_tasks
                )
                self.experiment_manager.archive_opendc_files(
                    window, simulated_results, cumulative_tasks
                )
                self.experiment_manager.generate_power_plot()
            except Exception as e:
                logger.error(f"Failed to write experiment results: {e}", exc_info=True)

    def _process_workload_message(self, message_data: dict[str, Any]) -> None:
        """Process a workload message (task or heartbeat) from Kafka.

        Args:
            message_data: Raw message data from Kafka
        """
        try:
            message_type = message_data.get("message_type")

            if message_type == "task":
                # Extract task from nested structure
                task = Task(**message_data["task"])
                logger.debug(
                    f"Received task {task.id} at {task.submission_time} "
                    f"with {len(task.fragments)} fragments"
                )

                # Add to window manager (does NOT close windows)
                self.window_manager.add_task(task)
                self.tasks_processed += 1

            elif message_type == "heartbeat":
                # Parse heartbeat timestamp
                heartbeat_time = datetime.fromisoformat(message_data["timestamp"])
                logger.debug(f"Received heartbeat at {heartbeat_time}")

                # Check which windows can be closed
                closed_windows = self.window_manager.close_windows_before(heartbeat_time)

                # Process each closed window sequentially
                for window in closed_windows:
                    self._process_window(window)

            else:
                logger.warning(f"Unknown message_type: {message_type}")

        except Exception as e:
            logger.error(f"Error processing workload message: {e}", exc_info=True)

    def _process_power_message(self, message_data: dict[str, Any]) -> None:
        """Process a power consumption message from Kafka.

        Args:
            message_data: Raw message data from Kafka (dc.power)
        """
        if not self.experiment_manager:
            return

        try:
            timestamp_str = message_data.get("timestamp")
            power_draw = message_data.get("power_draw")

            if timestamp_str and power_draw is not None:
                timestamp = datetime.fromisoformat(timestamp_str)
                self.experiment_manager.record_actual_power(timestamp, power_draw)

        except Exception as e:
            logger.error(f"Error processing power message: {e}", exc_info=True)

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

            # Update window manager with new topology
            self.window_manager.update_topology(topology_snapshot)

        except Exception as e:
            logger.error(f"Error processing topology message: {e}", exc_info=True)

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
            elif topic == self.power_topic:
                self._process_power_message(value)
            else:
                logger.warning(f"Unknown topic: {topic}")

        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}", exc_info=True)

    def run(self):
        """Run the simulation worker (main event loop)."""
        logger.info(f"Starting Simulation Worker '{self.worker_id}'")
        logger.info("Waiting for messages...")

        try:
            for message in self.consumer:
                self.process_message(message)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")

        except Exception as e:
            logger.error(f"Error in simulation worker: {e}", exc_info=True)
            raise

        finally:
            logger.info("Closing Kafka connections...")
            self.consumer.close()
            self.producer.close()
            logger.info("Simulation worker stopped")


def main():
    """Main entry point."""
    # Load configuration from environment
    try:
        config = load_config_from_env()
        logger.info(f"Loaded configuration for workload: {config.workload}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Get Kafka configuration from config file
    kafka_bootstrap_servers = config.kafka.bootstrap_servers
    workload_topic = config.kafka.topics["workload"].name
    topology_topic = config.kafka.topics["topology"].name
    power_topic = config.kafka.topics["power"].name
    results_topic = config.kafka.topics["results"].name

    # Get simulation configuration
    window_size_minutes = config.simulation.window_size_minutes

    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")
    logger.info(f"Workload topic: {workload_topic}")
    logger.info(f"Topology topic: {topology_topic}")
    logger.info(f"Power topic: {power_topic}")
    logger.info(f"Results topic: {results_topic}")
    logger.info(f"Window size: {window_size_minutes} minutes")

    # Get worker configuration from environment
    worker_id = os.getenv("WORKER_ID", "worker-1")
    consumer_group = os.getenv("CONSUMER_GROUP", "sim-workers")

    # Debug mode configuration
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes")
    debug_output_dir = os.getenv("DEBUG_OUTPUT_DIR", "/app/output")

    # Experiment mode configuration
    experiment_mode = config.simulation.experiment_mode
    experiment_name = os.getenv("EXPERIMENT_NAME", "default")
    experiment_output_dir = os.getenv("EXPERIMENT_OUTPUT_DIR", "/app/output")

    if debug_mode:
        logger.info("=" * 60)
        logger.info("🐛 DEBUG MODE ENABLED")
        logger.info(f"   Debug files will be written to: {debug_output_dir}")
        logger.info("=" * 60)

    if experiment_mode:
        logger.info("=" * 60)
        logger.info("🧪 EXPERIMENT MODE ENABLED")
        logger.info(f"   Experiment: {experiment_name}")
        logger.info("   Results will be written to parquet")
        logger.info("=" * 60)

    # Wait for Kafka to be ready
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to Kafka (attempt {attempt + 1}/{max_retries})")
            worker = SimulationWorker(
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                worker_id=worker_id,
                workload_topic=workload_topic,
                topology_topic=topology_topic,
                power_topic=power_topic,
                results_topic=results_topic,
                window_size_minutes=window_size_minutes,
                consumer_group=consumer_group,
                experiment_mode=experiment_mode,
                experiment_name=experiment_name,
                experiment_output_dir=experiment_output_dir,
                debug_mode=debug_mode,
                debug_output_dir=debug_output_dir,
            )
            worker.run()
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
