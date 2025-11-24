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
from opendt_common.utils.kafka import send_message

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
        results_topic: str,
        window_size_minutes: int,
        consumer_group: str = "sim-workers",
        debug_mode: bool = False,
        debug_output_dir: str = "/app/output",
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
            debug_mode: If True, write results to files instead of Kafka
            debug_output_dir: Directory to write debug output files
        """
        self.worker_id = worker_id
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.topology_topic = topology_topic
        self.results_topic = results_topic
        self.debug_mode = debug_mode
        self.debug_output_dir = debug_output_dir

        # Initialize Kafka consumer (subscribe to both workload and topology)
        self.consumer = get_kafka_consumer(
            topics=[workload_topic, topology_topic],
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

        # Create debug output directory if in debug mode
        if self.debug_mode:
            from pathlib import Path

            self.debug_run_dir = Path(debug_output_dir) / f"run-{worker_id}-{int(time.time())}"
            self.debug_run_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"🐛 DEBUG MODE ENABLED - Writing results to: {self.debug_run_dir}")

        logger.info(f"Initialized SimulationWorker '{worker_id}' in group '{consumer_group}'")
        logger.info(f"Subscribed to topics: {workload_topic}, {topology_topic}")
        logger.info(f"Window size: {window_size_minutes} minutes")
        if debug_mode:
            logger.info(f"Debug output: {self.debug_run_dir}")

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

        if len(all_tasks) == 0:
            logger.info(f"Window {window.window_id} has no cumulative tasks, skipping simulation")
            return

        logger.info(
            f"Running simulation for window {window.window_id} "
            f"with {len(all_tasks)} cumulative tasks ({len(window.tasks)} in this window)"
        )

        # Run simulation with real topology
        real_results = self._run_simulation(
            window_id=window.window_id,
            tasks=all_tasks,
            topology=window.topology,
            topology_type="real",
        )

        # Run simulation with simulated topology (if different from real)
        simulated_results = None
        if self.simulated_topology and self.simulated_topology != window.topology:
            simulated_results = self._run_simulation(
                window_id=window.window_id,
                tasks=all_tasks,
                topology=self.simulated_topology,
                topology_type="simulated",
            )

        # Publish results
        self._publish_results(window, real_results, simulated_results, all_tasks)

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

    def _publish_results(
        self,
        window: TimeWindow,
        real_results: SimulationResults,
        simulated_results: SimulationResults | None,
        cumulative_tasks: list[Task],
    ) -> None:
        """Publish simulation results to Kafka.

        Args:
            window: The window that was simulated
            real_results: Results from real topology simulation
            simulated_results: Results from simulated topology (optional)
            cumulative_tasks: All tasks from window 0 up to this window (used in simulation)
        """
        message = {
            "worker_id": self.worker_id,
            "window_id": window.window_id,
            "window_start": window.window_start.isoformat(),
            "window_end": window.window_end.isoformat(),
            "task_count": len(window.tasks),
            "timestamp": datetime.utcnow().isoformat(),
            "real_topology": real_results.model_dump(mode="json"),
        }

        if simulated_results:
            message["simulated_topology"] = simulated_results.model_dump(mode="json")

        # Debug mode: write to file
        if self.debug_mode:
            try:
                import json

                # Create window-specific directory
                window_dir = self.debug_run_dir / f"window_{window.window_id:04d}"
                window_dir.mkdir(parents=True, exist_ok=True)

                # Write simulation results
                results_file = window_dir / "results.json"
                with open(results_file, "w") as f:
                    json.dump(message, f, indent=2)

                # Write tasks/workload (minimal data without fragments)
                tasks_file = window_dir / "tasks.json"
                window_tasks_minimal = [
                    {"id": task.id, "submission_time": task.submission_time.isoformat()}
                    for task in window.tasks
                ]
                cumulative_tasks_minimal = [
                    {"id": task.id, "submission_time": task.submission_time.isoformat()}
                    for task in cumulative_tasks
                ]

                with open(tasks_file, "w") as f:
                    json.dump(
                        {
                            "window_id": window.window_id,
                            "window_start": window.window_start.isoformat(),
                            "window_end": window.window_end.isoformat(),
                            "window_task_count": len(window.tasks),
                            "cumulative_task_count": len(cumulative_tasks),
                            "window_tasks": window_tasks_minimal,
                            "cumulative_tasks": cumulative_tasks_minimal,
                        },
                        f,
                        indent=2,
                    )

                logger.info(
                    f"🐛 Wrote window {window.window_id} debug output to {window_dir}/ "
                    f"({len(window.tasks)} new tasks, {len(cumulative_tasks)} cumulative)"
                )
            except Exception as e:
                logger.error(f"Failed to write debug output: {e}", exc_info=True)
        # Normal mode: publish to Kafka
        else:
            try:
                send_message(
                    self.producer,
                    topic=self.results_topic,
                    message=message,
                    key=str(window.window_id),
                )
                logger.info(f"📤 Published results for window {window.window_id}")
            except Exception as e:
                logger.error(f"Failed to publish results: {e}", exc_info=True)

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
    results_topic = config.kafka.topics["results"].name

    # Get simulation configuration
    window_size_minutes = config.simulation.window_size_minutes

    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")
    logger.info(f"Workload topic: {workload_topic}")
    logger.info(f"Topology topic: {topology_topic}")
    logger.info(f"Results topic: {results_topic}")
    logger.info(f"Window size: {window_size_minutes} minutes")

    # Get worker configuration from environment
    worker_id = os.getenv("WORKER_ID", "worker-1")
    consumer_group = os.getenv("CONSUMER_GROUP", "sim-workers")

    # Debug mode configuration
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes")
    debug_output_dir = os.getenv("DEBUG_OUTPUT_DIR", "/app/output")

    if debug_mode:
        logger.info("=" * 60)
        logger.info("🐛 DEBUG MODE ENABLED")
        logger.info(f"   Results will be written to: {debug_output_dir}")
        logger.info("   Kafka publishing: DISABLED")
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
                results_topic=results_topic,
                window_size_minutes=window_size_minutes,
                consumer_group=consumer_group,
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
