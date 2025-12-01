"""Calibrator Service - Main Entry Point."""

import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from odt_common import TaskAccumulator, load_config_from_env
from odt_common.models import Task
from odt_common.utils import get_kafka_bootstrap_servers, get_kafka_consumer

from calibrator.calibration_engine import CalibrationEngine
from calibrator.mape_comparator import MapeComparator
from calibrator.power_tracker import PowerTracker
from calibrator.topology_manager import TopologyManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CalibrationService:
    """Core calibration service that processes workload and runs OpenDC simulations.

    The service:
    1. Listens to dc.workload (tasks) and dc.topology (topology snapshots)
    2. Accumulates tasks chronologically
    3. Triggers calibration runs at specified frequency (simulated time)
    4. Caches results based on topology hash + task count
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        workload_topic: str,
        topology_topic: str,
        sim_topology_topic: str,
        power_topic: str,
        calibration_frequency_minutes: int,
        calibrated_property: str,
        min_value: float,
        max_value: float,
        linspace_points: int,
        max_parallel_workers: int,
        mape_window_minutes: int,
        run_output_dir: str,
        run_id: str,
        speed_factor: float,
        consumer_group: str = "calibrators",
    ):
        """Initialize the calibration service.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            workload_topic: Kafka topic name for workload events (dc.workload)
            topology_topic: Kafka topic name for topology updates (dc.topology)
            sim_topology_topic: Kafka topic name for simulated topology updates (sim.topology)
            power_topic: Kafka topic name for actual power consumption (dc.power)
            calibration_frequency_minutes: Calibration frequency in simulated time minutes
            calibrated_property: Dot-notation path to property to calibrate
            min_value: Minimum value for calibrated property
            max_value: Maximum value for calibrated property
            linspace_points: Number of linspace points to test
            max_parallel_workers: Maximum parallel OpenDC simulations
            mape_window_minutes: Rolling window for MAPE calculation
            run_output_dir: Base directory for run outputs
            run_id: Unique run ID for this session
            speed_factor: Simulation speed multiplier
            consumer_group: Kafka consumer group ID
        """
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.calibration_frequency = timedelta(minutes=calibration_frequency_minutes)
        self.speed_factor = speed_factor
        self.run_id = run_id

        # Calibration parameters
        self.calibrated_property = calibrated_property
        self.min_value = min_value
        self.max_value = max_value
        self.linspace_points = linspace_points

        # Setup output directories - calibrator writes to run_dir/calibrator/
        self.output_base_dir = Path(run_output_dir) / run_id / "calibrator"
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Calibrator output directory: {self.output_base_dir}")

        # Initialize Kafka consumer for workload only
        self.consumer = get_kafka_consumer(
            topics=[workload_topic],
            group_id=consumer_group,
            bootstrap_servers=kafka_bootstrap_servers,
        )

        # Initialize task accumulator
        self.task_accumulator = TaskAccumulator()

        # Initialize calibration modules
        self.power_tracker = PowerTracker(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            power_topic=power_topic,
            consumer_group=f"{consumer_group}-power",
            debug=True,  # Temporary debug flag
        )

        self.topology_manager = TopologyManager(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            dc_topology_topic=topology_topic,
            sim_topology_topic=sim_topology_topic,
            consumer_group=f"{consumer_group}-topology",
        )

        self.calibration_engine = CalibrationEngine(max_workers=max_parallel_workers)

        self.mape_comparator = MapeComparator(mape_window_minutes=mape_window_minutes)

        # Start background trackers
        self.power_tracker.start()
        self.topology_manager.start()

        # Statistics
        self.tasks_processed = 0
        self.calibrations_run = 0
        self.run_number = 0

        # Timing tracking (for drift calculation)
        self.first_calibration_wall_time: datetime | None = None
        self.first_calibration_sim_time: datetime | None = None

        logger.info(f"Initialized CalibrationService with run ID: {run_id}")
        logger.info(f"Consumer group: {consumer_group}")
        logger.info(f"Subscribed to workload: {workload_topic}")
        logger.info(
            f"Calibration frequency: {calibration_frequency_minutes} minutes (simulated time)"
        )
        logger.info(f"Speed factor: {speed_factor}x")
        logger.info(f"Calibrated property: {calibrated_property}")
        logger.info(f"Parameter range: [{min_value}, {max_value}] with {linspace_points} points")
        logger.info(f"Max parallel workers: {max_parallel_workers}")
        logger.info(f"MAPE window: {mape_window_minutes} minutes")

    def _run_calibration(self) -> None:
        """Run calibration sweep with accumulated tasks."""
        # Track timing for performance monitoring
        calibration_start_time = datetime.now(UTC)

        # Get current topology
        base_topology = self.topology_manager.get_current_topology()
        if base_topology is None:
            logger.warning("No topology available, skipping calibration")
            return

        # Get all accumulated tasks
        all_tasks = self.task_accumulator.get_all_tasks()
        if not all_tasks:
            logger.info("No tasks to calibrate, skipping")
            return

        # Calculate aligned calibration time
        aligned_simulated_time = self.task_accumulator.get_next_simulation_time(
            self.calibration_frequency
        )
        if aligned_simulated_time is None:
            logger.error("Cannot calculate aligned calibration time")
            return

        # Track timing for first calibration
        if self.first_calibration_wall_time is None:
            self.first_calibration_wall_time = calibration_start_time
            self.first_calibration_sim_time = aligned_simulated_time
            logger.info(
                f"⏱️  First calibration baseline: "
                f"wall_time={calibration_start_time.strftime('%H:%M:%S')}, "
                f"sim_time={aligned_simulated_time.strftime('%H:%M:%S')}"
            )

        # Calculate time drift relative to workload start
        last_sim_time = self.task_accumulator.last_simulation_time
        if last_sim_time and self.first_calibration_sim_time and self.first_calibration_wall_time:
            # Overall elapsed times (from first calibration to now)
            total_sim_elapsed_seconds = (
                aligned_simulated_time - self.first_calibration_sim_time
            ).total_seconds()
            total_wall_elapsed_seconds = (
                calibration_start_time - self.first_calibration_wall_time
            ).total_seconds()

            # Calculate overall actual speedup
            if total_wall_elapsed_seconds > 0:
                overall_actual_speedup = total_sim_elapsed_seconds / total_wall_elapsed_seconds
                overall_drift_percent = (
                    ((overall_actual_speedup - self.speed_factor) / self.speed_factor) * 100
                    if self.speed_factor > 0
                    else 0
                )
            else:
                overall_actual_speedup = 0
                overall_drift_percent = 0

            # Log in clear format similar to simulator
            logger.info(
                f"⏱️  Calibrator Speed Tracking:\n"
                f"   Configured speed: {self.speed_factor}x\n"
                f"   Actual speed:     {overall_actual_speedup:.2f}x\n"
                f"   Drift:            {overall_drift_percent:+.1f}%\n"
                f"   Wall elapsed:     {total_wall_elapsed_seconds:.1f}s\n"
                f"   Sim elapsed:      {total_sim_elapsed_seconds:.0f}s "
                f"({total_sim_elapsed_seconds / 60:.1f}min)"
            )

            # Warn if drift is significant
            if abs(overall_drift_percent) > 10:
                logger.warning(
                    f"⚠️  Calibrator is drifting! Running at {overall_actual_speedup:.2f}x "
                    f"instead of {self.speed_factor}x ({overall_drift_percent:+.1f}% drift)"
                )

        # Increment run number
        self.run_number += 1

        # Create calibration run directory
        calibrator_run_dir = self.output_base_dir / f"run_{self.run_number}"
        calibrator_run_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"🔬 Starting calibration run {self.run_number} with {len(all_tasks)} tasks")
        logger.info(f"   Calibrating: {self.calibrated_property}")
        logger.info(f"   Range: [{self.min_value}, {self.max_value}]")
        logger.info(f"   Points: {self.linspace_points}")
        logger.info(f"   Wall clock: {calibration_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Run calibration sweep
        results = self.calibration_engine.run_calibration_sweep(
            base_topology=base_topology,
            tasks=all_tasks,
            property_path=self.calibrated_property,
            min_value=self.min_value,
            max_value=self.max_value,
            num_points=self.linspace_points,
            run_number=self.run_number,
            calibrator_run_dir=calibrator_run_dir,
            simulated_time=aligned_simulated_time,
            topology_modifier_func=self.topology_manager.create_variant,
            timeout_seconds=120,
        )

        if not results:
            logger.error("Calibration sweep produced no results")
            return

        # Get actual power data for comparison
        # Use window from earliest task to aligned_simulated_time
        first_task_time = all_tasks[0].submission_time
        actual_power = self.power_tracker.get_power_in_window(
            first_task_time, aligned_simulated_time
        )

        if actual_power.empty:
            logger.warning("No actual power data available for comparison")
            # Still record calibration metadata, but without MAPE scores
            best_result = results[len(results) // 2]  # Use middle value
            best_mape = float("inf")
        else:
            # Compare each simulation result with actual power
            comparison_results = []
            for result in results:
                if not result.success or result.power_df is None:
                    comparison_results.append(
                        {
                            "sim_number": result.sim_number,
                            "value": result.param_value,
                            "mape": float("inf"),
                        }
                    )
                    continue

                mape_result = self.mape_comparator.compare(
                    simulated_power=result.power_df,
                    actual_power=actual_power,
                    simulation_end_time=aligned_simulated_time,
                )

                comparison_results.append(
                    {
                        "sim_number": result.sim_number,
                        "value": result.param_value,
                        "mape": mape_result["mape"],
                        "window_start": mape_result["window_start"],
                        "window_end": mape_result["window_end"],
                        "num_points": mape_result["num_points"],
                    }
                )

                logger.info(
                    f"   sim_{result.sim_number}: "
                    f"{self.calibrated_property}={result.param_value:.3f} "
                    f"→ MAPE={mape_result['mape']:.2f}%"
                )

            # Find best result (lowest MAPE)
            best_comparison = min(comparison_results, key=lambda x: x["mape"])
            best_result = results[best_comparison["sim_number"]]
            best_mape = best_comparison["mape"]

            logger.info(
                f"🏆 Best: {self.calibrated_property}={best_result.param_value:.3f} "
                f"(MAPE={best_mape:.2f}%)"
            )

            # Write calibration metadata
            metadata = {
                "run_number": self.run_number,
                "wall_clock_time": datetime.now(UTC)
                .replace(microsecond=0, tzinfo=None)
                .isoformat(),
                "simulated_time": aligned_simulated_time.replace(microsecond=0).isoformat(),
                "task_count": len(all_tasks),
                "calibrated_property": self.calibrated_property,
                "variants_tested": len(results),
                "best_value": best_result.param_value,
                "best_mape": best_mape,
                "all_results": comparison_results,
                "mape_window_minutes": self.mape_comparator.mape_window_minutes,
            }

            metadata_file = calibrator_run_dir / "metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2))
            logger.info(f"   Metadata written to {metadata_file}")

            # Publish winning topology to sim.topology
            winning_topology = self.topology_manager.create_variant(
                self.calibrated_property, best_result.param_value
            )
            if winning_topology:
                success = self.topology_manager.publish_topology(winning_topology)
                if success:
                    logger.info(
                        f"📡 Published winning topology with "
                        f"{self.calibrated_property}={best_result.param_value:.3f} to sim.topology"
                    )
                else:
                    logger.error("Failed to publish winning topology")
            else:
                logger.error("Failed to create winning topology variant")

        # Update statistics and simulation time
        self.calibrations_run += 1
        self.task_accumulator.last_simulation_time = aligned_simulated_time

        # Calculate and log calibration duration
        calibration_end_time = datetime.now(UTC)
        calibration_duration = (calibration_end_time - calibration_start_time).total_seconds()

        logger.info(
            f"📊 Stats: {self.tasks_processed} tasks processed, "
            f"{self.calibrations_run} calibrations run"
        )
        logger.info(
            f"⏱️  Calibration duration: {calibration_duration:.1f}s "
            f"({calibration_duration / 60:.2f} minutes)"
        )

        # Warn if calibration took longer than the frequency interval
        frequency_seconds = self.calibration_frequency.total_seconds()
        if calibration_duration > frequency_seconds:
            logger.warning(
                f"⚠️  Calibration took {calibration_duration:.1f}s, which exceeds "
                f"the configured frequency of {frequency_seconds:.1f}s! "
                f"The calibrator may fall behind. Consider increasing "
                f"the frequency or reducing parallel workers/points."
            )

        # Sleep if we're running faster than the configured speed factor
        self._sleep_if_ahead(aligned_simulated_time)

    def _sleep_if_ahead(self, aligned_simulated_time: datetime) -> None:
        """Sleep if calibrator is running ahead of the configured speed factor.

        This prevents the calibrator from processing faster than the speed factor allows,
        which would cause it to wait idle for more data.

        Args:
            aligned_simulated_time: Current simulation time
        """
        if self.speed_factor <= 0:
            return  # Max speed mode, no throttling

        if self.first_calibration_wall_time is None or self.first_calibration_sim_time is None:
            return  # Not enough data yet

        current_wall_time = datetime.now(UTC)

        # Calculate how much wall time should have elapsed for this simulated time
        sim_elapsed_seconds = (
            aligned_simulated_time - self.first_calibration_sim_time
        ).total_seconds()
        expected_wall_elapsed = sim_elapsed_seconds / self.speed_factor

        # Calculate actual wall time elapsed
        actual_wall_elapsed = (current_wall_time - self.first_calibration_wall_time).total_seconds()

        # If we're ahead, sleep to stay synchronized
        sleep_time = expected_wall_elapsed - actual_wall_elapsed

        if sleep_time > 0:
            logger.info(
                f"💤 Calibrator is ahead of schedule, sleeping for {sleep_time:.2f}s "
                f"to maintain {self.speed_factor}x speed"
            )
            time.sleep(sleep_time)

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

                # Check if we should trigger calibration
                if self.task_accumulator.should_simulate(
                    heartbeat_time, self.calibration_frequency
                ):
                    self._run_calibration()

            else:
                logger.warning(f"Unknown message_type: {message_type}")

        except Exception as e:
            logger.error(f"Error processing workload message: {e}", exc_info=True)

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
            else:
                logger.warning(f"Unknown topic: {topic}")

        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}", exc_info=True)

    def run(self):
        """Run the calibration service (main event loop)."""
        logger.info("Starting Calibration Service")
        logger.info("Waiting for messages...")

        try:
            for message in self.consumer:
                self.process_message(message)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")

        except Exception as e:
            logger.error(f"Error in calibration service: {e}", exc_info=True)
            raise

        finally:
            logger.info("Shutting down calibration service...")
            self.consumer.close()
            self.power_tracker.stop()
            self.topology_manager.stop()
            logger.info("Calibration service stopped")


def main():
    """Main entry point."""
    # Load configuration from environment
    try:
        config = load_config_from_env()
        logger.info(f"Loaded configuration for workload: {config.workload}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Check if calibration is enabled
    if not config.global_config.calibration_enabled:
        logger.warning("Calibration is disabled in configuration. Exiting gracefully.")
        return

    # Ensure calibrator config exists (should be caught by model validator, but check anyway)
    if config.services.calibrator is None:
        logger.error("Calibration is enabled but calibrator configuration is missing")
        raise ValueError("Calibrator configuration required when calibration_enabled=true")

    # Get Kafka configuration from environment variable
    kafka_bootstrap_servers = get_kafka_bootstrap_servers()
    workload_topic = config.kafka.topics["workload"].name
    topology_topic = config.kafka.topics["topology"].name
    sim_topology_topic = config.kafka.topics["sim_topology"].name
    power_topic = config.kafka.topics["power"].name

    # Get calibrator configuration
    calibrator_config = config.services.calibrator
    calibration_frequency_minutes = calibrator_config.calibration_frequency_minutes
    calibrated_property = calibrator_config.calibrated_property
    min_value = calibrator_config.min_value
    max_value = calibrator_config.max_value
    linspace_points = calibrator_config.linspace_points
    max_parallel_workers = calibrator_config.max_parallel_workers
    mape_window_minutes = calibrator_config.mape_window_minutes
    speed_factor = config.global_config.speed_factor
    run_output_dir = Path(os.getenv("DATA_DIR", "/app/data"))

    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")
    logger.info(f"Workload topic: {workload_topic}")
    logger.info(f"Topology topic: {topology_topic}")
    logger.info(f"Simulated topology topic: {sim_topology_topic}")
    logger.info(f"Power topic: {power_topic}")
    logger.info(f"Calibration frequency: {calibration_frequency_minutes} minutes")
    logger.info(f"Calibrated property: {calibrated_property}")
    logger.info(f"Parameter range: [{min_value}, {max_value}]")
    logger.info(f"Linspace points: {linspace_points}")
    logger.info(f"Max parallel workers: {max_parallel_workers}")
    logger.info(f"MAPE window: {mape_window_minutes} minutes")
    logger.info(f"Data directory: {run_output_dir}")

    # Get run ID from environment
    run_id = os.getenv("RUN_ID")
    if not run_id:
        logger.error("RUN_ID environment variable not set")
        raise ValueError("RUN_ID environment variable is required")

    logger.info(f"Run ID: {run_id}")

    # Get consumer group from environment
    consumer_group = os.getenv("CONSUMER_GROUP", "calibrators")

    # Wait for Kafka to be ready
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to Kafka (attempt {attempt + 1}/{max_retries})")
            service = CalibrationService(
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                workload_topic=workload_topic,
                topology_topic=topology_topic,
                sim_topology_topic=sim_topology_topic,
                power_topic=power_topic,
                calibration_frequency_minutes=calibration_frequency_minutes,
                calibrated_property=calibrated_property,
                min_value=min_value,
                max_value=max_value,
                linspace_points=linspace_points,
                max_parallel_workers=max_parallel_workers,
                mape_window_minutes=mape_window_minutes,
                run_output_dir=str(run_output_dir),
                run_id=run_id,
                speed_factor=speed_factor,
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
