"""The calibrator: fits the power model's r to the measured power with parallel OpenDC runs."""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path

import numpy as np
from odt_common import TaskAccumulator, load_config_from_env
from odt_common.config import (
    CALIBRATION,
    CALIBRATION_MAX,
    CALIBRATION_MIN,
    CALIBRATION_POINTS,
    MAPE_WINDOW,
    PARALLEL_RUNS,
    DynamicConfigEvent,
)
from odt_common.models import Task
from odt_common.utils import get_kafka_bootstrap_servers, get_kafka_consumer

from calibrator.calibration_engine import sweep
from calibrator.mape_comparator import mape
from calibrator.power_tracker import PowerTracker
from calibrator.result_processor import record
from calibrator.topology_manager import TopologyManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def twin_time(run_dir: Path) -> datetime | None:
    """The twin's time: the end of the simulator's latest complete window (as the API's); None before
    the first. The calibration follows it, not the replay, which at maximum speed is days ahead."""
    folder = run_dir / "simulator" / "opendc"
    names = os.listdir(folder) if folder.exists() else []
    for n in sorted((int(name[4:]) for name in names if name.startswith("run_")), reverse=True):
        metadata = folder / f"run_{n}" / "metadata.json"
        if metadata.exists():
            return datetime.fromisoformat(json.loads(metadata.read_text())["simulated_time"])
    return None


class CalibrationService:
    """Core calibration service with decoupled message consumption and calibration execution.

    Architecture:
    - Consumer thread: Continuously accumulates tasks from Kafka
    - Calibration thread: Runs calibrations in a loop using latest available data
    """

    def __init__(
        self,
        workload_topic: str,
        topology_topic: str,
        sim_topology_topic: str,
        power_topic: str,
        system_topic: str,
        calibrated_property: str,
        min_value: float,
        max_value: float,
        linspace_points: int,
        max_parallel_workers: int,
        mape_window_minutes: int,
        run_output_dir: str,
        run_id: str,
        enabled: bool,
        consumer_group: str = "calibrators",
    ):
        """Initialize the calibration service."""
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic
        self.system_topic = system_topic
        self.enabled = enabled  # calibrating, or waiting for the control panel to switch it on
        self.run_id = run_id

        self.calibrated_property = calibrated_property
        self.min_value = min_value
        self.max_value = max_value
        self.linspace_points = linspace_points
        self.workers = max_parallel_workers
        self.window_minutes = mape_window_minutes

        self.output_base_dir = Path(run_output_dir) / run_id / "calibrator"
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Calibrator output directory: {self.output_base_dir}")

        self.consumer = get_kafka_consumer(
            topics=[workload_topic, system_topic],  # sys.config: the parallel simulations
            group_id=consumer_group,
        )

        self.task_accumulator = TaskAccumulator()

        self.power_tracker = PowerTracker(
            power_topic=power_topic,
            consumer_group=f"{consumer_group}-power",
            debug=True,
        )

        self.topology_manager = TopologyManager(
            dc_topology_topic=topology_topic,
            sim_topology_topic=sim_topology_topic,
            consumer_group=f"{consumer_group}-topology",
        )

        self.power_tracker.start()
        self.topology_manager.start()

        self.tasks_processed = 0
        self.run_number = 0

        self.running = threading.Event()
        self.consumer_thread: threading.Thread | None = None
        self.calibration_thread: threading.Thread | None = None

        logger.info(f"Initialized CalibrationService with run ID: {run_id}")
        logger.info(f"Consumer group: {consumer_group}")
        logger.info(f"Calibrated property: {calibrated_property}")
        logger.info(f"Parameter range: [{min_value}, {max_value}] with {linspace_points} points")
        logger.info(f"Max parallel workers: {max_parallel_workers}")
        logger.info(f"MAPE window: {mape_window_minutes} minutes")

    def _process_config_event(self, message_data: dict) -> None:
        """Follow a change of the calibration's settings, from the next grid search; the other runtime settings
        are not the calibrator's."""
        event = DynamicConfigEvent(**message_data)
        followed = {
            CALIBRATION: (self, "enabled"),
            PARALLEL_RUNS: (self, "workers"),
            CALIBRATION_MIN: (self, "min_value"),
            CALIBRATION_MAX: (self, "max_value"),
            CALIBRATION_POINTS: (self, "linspace_points"),
            MAPE_WINDOW: (self, "window_minutes"),
        }
        if event.setting_key in followed:
            setattr(*followed[event.setting_key], event.new_value)
            logger.info(f"{event.setting_key}: {event.new_value}")

    def _consume_messages(self):
        """Consumer thread: accumulate tasks from Kafka."""
        logger.info("Consumer thread started")
        logger.info(f"Consumer group: {self.consumer_group}")
        logger.info(f"Subscribed to: {self.workload_topic}")

        message_count = 0
        try:
            for message in self.consumer:
                if not self.running.is_set():
                    break

                message_count += 1
                if message_count == 1:
                    logger.info(
                        f"First message received! Offset: {message.offset}, "
                        f"Partition: {message.partition}"
                    )
                elif message_count % 100 == 0:
                    logger.info(f"Consumed {message_count} Kafka messages")

                try:
                    value = message.value
                    if message.topic == self.system_topic:
                        self._process_config_event(value)
                        continue
                    message_type = value.get("message_type")

                    if message_type == "task":
                        task = Task(**value["task"])
                        self.task_accumulator.add_task(task)
                        self.tasks_processed += 1

                        if self.tasks_processed % 50 == 0:
                            all_tasks = self.task_accumulator.get_all_tasks()
                            if all_tasks:
                                first_task = min(t.submission_time for t in all_tasks)
                                latest_task = max(t.submission_time for t in all_tasks)
                                span_min = (latest_task - first_task).total_seconds() / 60
                                logger.info(
                                    f"Accumulated {self.tasks_processed} tasks\n"
                                    f"   Time range: {first_task.isoformat()} to "
                                    f"{latest_task.isoformat()}\n"
                                    f"   Span: {span_min:.1f} minutes"
                                )

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Consumer thread error: {e}", exc_info=True)
        finally:
            logger.info("Consumer thread exiting")

    def _run_calibration_loop(self):
        """Calibration thread: one sweep after the other, with the latest data, while calibration is on."""
        logger.info("Calibration thread started")
        while self.running.is_set():
            if self.enabled:  # off until the control panel switches it on
                try:
                    self._calibrate()
                except Exception as e:
                    logger.error(f"Error in calibration loop: {e}", exc_info=True)
            time.sleep(1)
        logger.info("Calibration thread exiting")

    def _calibrate(self) -> None:
        """One sweep: OpenDC with each value of the calibrated property, on the tasks up to the twin's time,
        each compared with the measured power over the MAPE window; the best value goes to the simulator if
        it changed. Returns at once, to try again a second later, while the data is not there yet."""
        started = time.monotonic()
        topology = self.topology_manager.get_current_topology()
        now = twin_time(self.output_base_dir.parent)
        latest_power = self.power_tracker.get_latest_timestamp()
        if topology is None or now is None or latest_power is None:
            return
        # the tasks and the power up to the twin's time, not the replay's
        tasks = [t for t in self.task_accumulator.get_all_tasks() if t.submission_time <= now]
        if not tasks:
            return
        first_task = min(t.submission_time for t in tasks)
        last_task = max(t.submission_time for t in tasks)
        # OpenDC runs all the tasks; the MAPE compares where the tasks and the power overlap
        end = min(last_task, latest_power, now)
        if (end - first_task).total_seconds() / 60 < min(30, self.window_minutes):
            return
        measured = self.power_tracker.get_power_in_window(first_task, end)
        if measured.empty:
            logger.warning("No measured power to compare with")
            return

        self.run_number += 1
        run_dir = self.output_base_dir / "opendc" / f"run_{self.run_number}"
        logger.info(
            f"Calibration run {self.run_number}: {len(tasks)} tasks, "
            f"{self.linspace_points} values of {self.calibrated_property}"
        )
        values = np.round(np.linspace(self.min_value, self.max_value, self.linspace_points), 2)
        variant = self.topology_manager.create_variant
        topologies = {float(v): variant(self.calibrated_property, float(v)) for v in values}
        powers = sweep(topologies, tasks, run_dir, last_task, self.workers)
        window = timedelta(minutes=self.window_minutes)
        no_run = (float("inf"), None)
        results = {
            v: no_run if p is None else mape(p, measured, end, window) for v, p in powers.items()
        }

        best = min(results, key=lambda v: results[v][0])
        best_mape, start = results[best]
        if best_mape == float("inf"):
            logger.error("No OpenDC run to compare with the measured power; r stays")
            return
        logger.info(f"Best: {self.calibrated_property}={best:.2f} (MAPE={best_mape:.2f}%)")
        # sent whenever the twin runs another value: a change from the control panel, made before a
        # window ran the value sent last, carries the value of that window
        host = self.topology_manager.get_current_topology().clusters[0].hosts[0]
        changed = best != reduce(getattr, self.calibrated_property.split("."), host)
        if changed:
            self.topology_manager.publish_topology(variant(self.calibrated_property, best))
        mapes = {v: m for v, (m, _) in results.items()}
        record(
            self.output_base_dir,
            run_dir,
            self.run_number,
            end,
            start,
            len(tasks),
            mapes,
            self.calibrated_property,
            best,
            changed,
        )
        logger.info(f"Calibration run {self.run_number} done in {time.monotonic() - started:.1f}s")

    def run(self):
        """Start the calibration service (consumer and calibration threads)."""
        logger.info("Starting Calibration Service")

        self.running.set()

        self.consumer_thread = threading.Thread(
            target=self._consume_messages, name="ConsumerThread", daemon=True
        )
        self.consumer_thread.start()

        self.calibration_thread = threading.Thread(
            target=self._run_calibration_loop, name="CalibrationThread", daemon=True
        )
        self.calibration_thread.start()

        try:
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

        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=5)
        if self.calibration_thread and self.calibration_thread.is_alive():
            self.calibration_thread.join(timeout=5)

        self.consumer.close()
        self.power_tracker.stop()
        self.topology_manager.stop()

        logger.info("Calibration service stopped")


def main():
    config = load_config_from_env()
    logger.info(f"Loaded configuration for workload: {config.workload}")

    # off at the start, the calibrator waits until the control panel switches it on; without settings, it has
    # nothing to calibrate
    if config.services.calibrator is None:
        logger.info("No calibrator settings; exiting")
        return
    workload_topic = config.kafka.topics["workload"].name
    topology_topic = config.kafka.topics["topology"].name
    sim_topology_topic = config.kafka.topics["sim_topology"].name
    power_topic = config.kafka.topics["power"].name
    system_topic = config.kafka.topics["system"].name

    calibrator_config = config.services.calibrator
    calibrated_property = calibrator_config.calibrated_property
    min_value = calibrator_config.min_value
    max_value = calibrator_config.max_value
    linspace_points = calibrator_config.linspace_points
    max_parallel_workers = calibrator_config.max_parallel_workers
    mape_window_minutes = calibrator_config.mape_window_minutes
    run_output_dir = Path(os.getenv("DATA_DIR", "/app/data"))

    run_id = os.getenv("RUN_ID")
    if not run_id:
        logger.error("RUN_ID environment variable not set")
        raise ValueError("RUN_ID environment variable is required")

    consumer_group = os.getenv("CONSUMER_GROUP", "calibrators")

    logger.info(f"Run ID: {run_id}")
    logger.info(f"Kafka bootstrap servers: {get_kafka_bootstrap_servers()}")

    # kafka-init has made the topics, so Kafka is up (docker-compose starts this service after it)
    service = CalibrationService(
        workload_topic=workload_topic,
        topology_topic=topology_topic,
        sim_topology_topic=sim_topology_topic,
        power_topic=power_topic,
        system_topic=system_topic,
        calibrated_property=calibrated_property,
        min_value=min_value,
        max_value=max_value,
        linspace_points=linspace_points,
        max_parallel_workers=max_parallel_workers,
        mape_window_minutes=mape_window_minutes,
        run_output_dir=str(run_output_dir),
        run_id=run_id,
        enabled=config.global_config.calibration_enabled,
        consumer_group=consumer_group,
    )
    service.run()


if __name__ == "__main__":
    main()
