"""Calibrator Service - Main Entry Point."""

import logging
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from odt_common import TaskAccumulator, load_config_from_env
from odt_common.models import Task
from odt_common.utils import get_kafka_bootstrap_servers, get_kafka_consumer

from calibrator.calibration_engine import CalibrationEngine
from calibrator.mape_comparator import MapeComparator
from calibrator.power_tracker import PowerTracker
from calibrator.result_processor import CalibrationResultProcessor
from calibrator.topology_manager import TopologyManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CalibrationService:
    """Core calibration service with decoupled message consumption and calibration execution.

    Architecture:
    - Consumer thread: Continuously accumulates tasks from Kafka
    - Calibration thread: Runs calibrations in a loop using latest available data
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        workload_topic: str,
        topology_topic: str,
        sim_topology_topic: str,
        power_topic: str,
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
        """Initialize the calibration service."""
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.speed_factor = speed_factor
        self.run_id = run_id

        # Calibration parameters
        self.calibrated_property = calibrated_property
        self.min_value = min_value
        self.max_value = max_value
        self.linspace_points = linspace_points

        # Setup output directories
        self.output_base_dir = Path(run_output_dir) / run_id / "calibrator"
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Calibrator output directory: {self.output_base_dir}")

        # Initialize Kafka consumer for workload
        self.consumer = get_kafka_consumer(
            topics=[workload_topic],
            group_id=consumer_group,
            bootstrap_servers=kafka_bootstrap_servers,
        )

        # Initialize task accumulator (thread-safe)
        self.task_accumulator = TaskAccumulator()

        # Initialize calibration modules
        self.power_tracker = PowerTracker(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            power_topic=power_topic,
            consumer_group=f"{consumer_group}-power",
            debug=True,
        )

        self.topology_manager = TopologyManager(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            dc_topology_topic=topology_topic,
            sim_topology_topic=sim_topology_topic,
            consumer_group=f"{consumer_group}-topology",
        )

        self.calibration_engine = CalibrationEngine(max_workers=max_parallel_workers)
        self.mape_comparator = MapeComparator(mape_window_minutes=mape_window_minutes)
        self.result_processor = CalibrationResultProcessor(self.output_base_dir)

        # Start background trackers
        self.power_tracker.start()
        self.topology_manager.start()

        # Statistics
        self.tasks_processed = 0
        self.calibrations_run = 0
        self.run_number = 0

        # Thread control
        self.running = threading.Event()
        self.consumer_thread: threading.Thread | None = None
        self.calibration_thread: threading.Thread | None = None

        logger.info(f"Initialized CalibrationService with run ID: {run_id}")
        logger.info(f"Consumer group: {consumer_group}")
        logger.info("Calibration mode: Continuous (runs as fast as possible with latest data)")
        logger.info(f"Speed factor: {speed_factor}x (for tracking only)")
        logger.info(f"Calibrated property: {calibrated_property}")
        logger.info(f"Parameter range: [{min_value}, {max_value}] with {linspace_points} points")
        logger.info(f"Max parallel workers: {max_parallel_workers}")
        logger.info(f"MAPE window: {mape_window_minutes} minutes")

    def _consume_messages(self):
        """Consumer thread: accumulate tasks from Kafka."""
        logger.info("🔄 Consumer thread started")
        logger.info(f"📨 Consumer group: {self.consumer_group}")
        logger.info(f"📋 Subscribed to: {self.workload_topic}")

        message_count = 0
        try:
            for message in self.consumer:
                if not self.running.is_set():
                    break

                message_count += 1
                if message_count == 1:
                    logger.info(
                        f"✅ First message received! Offset: {message.offset}, "
                        f"Partition: {message.partition}"
                    )
                elif message_count % 100 == 0:
                    logger.info(f"📊 Consumed {message_count} Kafka messages")

                try:
                    value = message.value
                    message_type = value.get("message_type")

                    if message_type == "task":
                        task = Task(**value["task"])
                        self.task_accumulator.add_task(task)
                        self.tasks_processed += 1

                        # Log every 50 tasks
                        if self.tasks_processed % 50 == 0:
                            all_tasks = self.task_accumulator.get_all_tasks()
                            if all_tasks:
                                first_task = min(t.submission_time for t in all_tasks)
                                latest_task = max(t.submission_time for t in all_tasks)
                                span_min = (latest_task - first_task).total_seconds() / 60
                                logger.info(
                                    f"📥 Accumulated {self.tasks_processed} tasks\n"
                                    f"   Time range: {first_task.isoformat()} to "
                                    f"{latest_task.isoformat()}\n"
                                    f"   Span: {span_min:.1f} minutes"
                                )

                    elif message_type == "heartbeat":
                        # Just log heartbeats, don't trigger calibration
                        pass

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Consumer thread error: {e}", exc_info=True)
        finally:
            logger.info("Consumer thread exiting")

    def _run_calibration_loop(self):
        """Calibration thread: continuously run calibrations with latest data."""
        logger.info("🔬 Calibration thread started")
        logger.info("⏳ Waiting for sufficient data before first calibration...")

        # Wait a bit for initial data to accumulate
        time.sleep(5)

        while self.running.is_set():
            try:
                calibration_start_time = datetime.now(UTC)

                # Get current topology
                base_topology = self.topology_manager.get_current_topology()
                if base_topology is None:
                    logger.debug("No topology available, waiting...")
                    time.sleep(1)
                    continue

                # Get all accumulated tasks
                all_tasks = self.task_accumulator.get_all_tasks()
                if not all_tasks:
                    logger.debug("No tasks accumulated yet, waiting...")
                    time.sleep(1)
                    continue

                # Get data ranges
                first_task_time = min(task.submission_time for task in all_tasks)
                latest_task_time = max(task.submission_time for task in all_tasks)
                task_span_minutes = (latest_task_time - first_task_time).total_seconds() / 60

                # Get latest power data
                latest_power_time = self.power_tracker.get_latest_timestamp()
                if not latest_power_time:
                    logger.debug("No power data available yet, waiting...")
                    time.sleep(1)
                    continue

                # Get power data range
                power_reading_count = self.power_tracker.get_reading_count()

                # Determine MAPE comparison window (intersection of task and power data)
                # This is ONLY for comparison - ALL tasks are still sent to OpenDC
                mape_end_time = min(latest_task_time, latest_power_time)
                mape_span_minutes = (mape_end_time - first_task_time).total_seconds() / 60
                min_required_minutes = min(30, self.mape_comparator.mape_window_minutes)

                if mape_span_minutes < min_required_minutes:
                    logger.info(
                        f"⏳ Insufficient data overlap: {mape_span_minutes:.1f} min "
                        f"(need {min_required_minutes} min), waiting..."
                    )
                    time.sleep(5)
                    continue

                # Log comprehensive data overview
                logger.info("=" * 80)
                logger.info(f"🔬 Starting Calibration Run {self.run_number + 1}")
                logger.info("=" * 80)
                logger.info(
                    f"📋 Workload Data:\n"
                    f"   Total tasks:  {len(all_tasks)}\n"
                    f"   Time range:   {first_task_time.isoformat()} to {latest_task_time.isoformat()}\n"
                    f"   Duration:     {task_span_minutes:.1f} minutes"
                )
                logger.info(
                    f"⚡ Ground Truth Power Data:\n"
                    f"   Readings:     {power_reading_count}\n"
                    f"   Latest at:    {latest_power_time.isoformat()}"
                )
                logger.info(
                    f"🎯 Simulation Strategy:\n"
                    f"   OpenDC input: ALL {len(all_tasks)} tasks "
                    f"({first_task_time.isoformat()} to {latest_task_time.isoformat()})\n"
                    f"   MAPE window:  {first_task_time.isoformat()} to {mape_end_time.isoformat()} "
                    f"({mape_span_minutes:.1f} min)\n"
                    f"   → Reason:     Limited by {'tasks' if latest_task_time < latest_power_time else 'power data'}"
                )
                logger.info("=" * 80)

                # Increment run number
                self.run_number += 1

                # Create calibration run directory
                calibrator_run_dir = self.output_base_dir / "opendc" / f"run_{self.run_number}"
                calibrator_run_dir.mkdir(parents=True, exist_ok=True)

                # Run calibration sweep with ALL tasks
                logger.info(f"🔄 Running {self.linspace_points} OpenDC simulations...")
                results = self.calibration_engine.run_calibration_sweep(
                    base_topology=base_topology,
                    tasks=all_tasks,  # ALL tasks sent to OpenDC
                    property_path=self.calibrated_property,
                    min_value=self.min_value,
                    max_value=self.max_value,
                    num_points=self.linspace_points,
                    run_number=self.run_number,
                    calibrator_run_dir=calibrator_run_dir,
                    simulated_time=latest_task_time,  # Full simulation end time
                    topology_modifier_func=self.topology_manager.create_variant,
                    timeout_seconds=120,
                )

                if not results:
                    logger.error("❌ Calibration sweep produced no results")
                    continue

                logger.info("✅ Simulations complete, retrieving ground truth for comparison...")

                # Get actual power data for MAPE comparison window only
                actual_power = self.power_tracker.get_power_in_window(
                    first_task_time, mape_end_time
                )

                if actual_power.empty:
                    logger.warning("⚠️  No actual power data for comparison")
                    best_result = results[len(results) // 2]
                    best_mape = float("inf")
                    mape_by_value = {}
                else:
                    logger.info(f"📊 Comparing {len(results)} simulations against ground truth...")

                    # Compare each simulation with actual power
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
                            simulation_end_time=mape_end_time,  # Use MAPE window end
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

                        logger.debug(
                            f"   sim_{result.sim_number}: {self.calibrated_property}="
                            f"{result.param_value:.3f} → MAPE={mape_result['mape']:.2f}%"
                        )

                    # Find best result
                    best_comparison = min(comparison_results, key=lambda x: x["mape"])
                    best_result = results[best_comparison["sim_number"]]
                    best_mape = best_comparison["mape"]

                    # Round best value to 2 decimal places
                    best_value = round(best_result.param_value, 2)

                    logger.info(
                        f"🏆 Best: {self.calibrated_property}={best_value:.2f} "
                        f"(MAPE={best_mape:.2f}%)"
                    )

                    # Check if topology should be broadcast
                    should_broadcast = self.result_processor.should_broadcast_topology(best_value)

                    if should_broadcast:
                        winning_topology = self.topology_manager.create_variant(
                            self.calibrated_property, best_value
                        )
                        if winning_topology:
                            success = self.topology_manager.publish_topology(winning_topology)
                            if success:
                                logger.info(
                                    f"📡 Published topology with {self.calibrated_property}="
                                    f"{best_value:.2f}"
                                )
                    else:
                        logger.info(f"Skipping broadcast - value unchanged at {best_value:.2f}")

                    # Prepare MAPE results (already rounded in calibration_engine)
                    mape_by_value = {
                        f"{comp['value']:.2f}": comp["mape"] for comp in comparison_results
                    }
                    mape_results_dict = {
                        "window_start": best_comparison.get("window_start"),
                        "window_end": best_comparison.get("window_end"),
                        "mape_by_value": mape_by_value,
                    }

                    # Process and save results
                    try:
                        topology_changed = should_broadcast
                        self.result_processor.process_calibration_results(
                            run_number=self.run_number,
                            run_dir=calibrator_run_dir,
                            aligned_simulated_time=mape_end_time,  # MAPE comparison window end
                            last_task_time=latest_task_time,
                            task_count=len(all_tasks),
                            wall_clock_time=datetime.now(UTC),
                            mape_results=mape_results_dict,
                            best_value=best_value,
                            best_mape=best_mape,
                            calibrated_property=self.calibrated_property,
                            topology_changed=topology_changed,
                        )
                    except Exception as e:
                        logger.error(f"Failed to process calibration results: {e}", exc_info=True)

                # Update statistics
                self.calibrations_run += 1
                self.task_accumulator.last_simulation_time = latest_task_time

                # Log calibration duration
                calibration_wall_end_time = datetime.now(UTC)
                calibration_duration = (
                    calibration_wall_end_time - calibration_start_time
                ).total_seconds()

                logger.info(
                    f"✅ Calibration run {self.run_number} complete in {calibration_duration:.1f}s"
                )
                logger.info(
                    f"📊 Total: {self.tasks_processed} tasks accumulated, "
                    f"{self.calibrations_run} calibrations completed"
                )
                logger.info("")  # Blank line for readability

                # Small sleep before next calibration
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in calibration loop: {e}", exc_info=True)
                time.sleep(5)  # Wait longer on error

        logger.info("Calibration thread exiting")

    def run(self):
        """Start the calibration service (consumer and calibration threads)."""
        logger.info("🚀 Starting Calibration Service")

        self.running.set()

        # Start consumer thread
        self.consumer_thread = threading.Thread(
            target=self._consume_messages, name="ConsumerThread", daemon=True
        )
        self.consumer_thread.start()

        # Start calibration thread
        self.calibration_thread = threading.Thread(
            target=self._run_calibration_loop, name="CalibrationThread", daemon=True
        )
        self.calibration_thread.start()

        try:
            # Main thread just waits
            while self.running.is_set():
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")

        finally:
            self.stop()

    def stop(self):
        """Stop the service."""
        logger.info("Stopping calibration service...")
        self.running.clear()

        # Wait for threads to finish
        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=5)
        if self.calibration_thread and self.calibration_thread.is_alive():
            self.calibration_thread.join(timeout=5)

        # Close consumers
        self.consumer.close()
        self.power_tracker.stop()
        self.topology_manager.stop()

        logger.info("Calibration service stopped")


def main():
    """Main entry point."""
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

    # Ensure calibrator config exists
    if config.services.calibrator is None:
        logger.error("Calibration is enabled but calibrator configuration is missing")
        raise ValueError("Calibrator configuration required when calibration_enabled=true")

    # Get configuration
    kafka_bootstrap_servers = get_kafka_bootstrap_servers()
    workload_topic = config.kafka.topics["workload"].name
    topology_topic = config.kafka.topics["topology"].name
    sim_topology_topic = config.kafka.topics["sim_topology"].name
    power_topic = config.kafka.topics["power"].name

    calibrator_config = config.services.calibrator
    calibrated_property = calibrator_config.calibrated_property
    min_value = calibrator_config.min_value
    max_value = calibrator_config.max_value
    linspace_points = calibrator_config.linspace_points
    max_parallel_workers = calibrator_config.max_parallel_workers
    mape_window_minutes = calibrator_config.mape_window_minutes
    speed_factor = config.global_config.speed_factor
    run_output_dir = Path(os.getenv("DATA_DIR", "/app/data"))

    # Get run ID
    run_id = os.getenv("RUN_ID")
    if not run_id:
        logger.error("RUN_ID environment variable not set")
        raise ValueError("RUN_ID environment variable is required")

    consumer_group = os.getenv("CONSUMER_GROUP", "calibrators")

    logger.info(f"Run ID: {run_id}")
    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")

    # Create and run service
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
