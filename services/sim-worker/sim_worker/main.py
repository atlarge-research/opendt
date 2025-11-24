"""Sim-Worker Service - Main Entry Point."""

import logging
import os
import time
from typing import Any

from opendt_common import load_config_from_env
from opendt_common.utils import get_kafka_consumer, get_kafka_producer
from opendt_common.utils.kafka import send_message

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimulationWorker:
    """Consumes workload events from Kafka and runs simulations."""

    def __init__(
        self,
        kafka_bootstrap_servers: str,
        worker_id: str,
        workload_topic: str,
        consumer_group: str = "sim-workers",
    ):
        """Initialize the simulation worker.

        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            worker_id: Unique identifier for this worker
            workload_topic: Kafka topic name for workload events
            consumer_group: Kafka consumer group ID
        """
        self.worker_id = worker_id
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.consumer_group = consumer_group
        self.workload_topic = workload_topic

        # Initialize Kafka consumer
        self.consumer = get_kafka_consumer(
            topics=[workload_topic],
            group_id=consumer_group,
            bootstrap_servers=kafka_bootstrap_servers,
        )

        # Initialize Kafka producer for results
        self.producer = get_kafka_producer(kafka_bootstrap_servers)

        logger.info(f"Initialized SimulationWorker '{worker_id}' in group '{consumer_group}'")
        logger.info(f"Subscribed to topic: {workload_topic}")

    def simulate_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate a task.

        Args:
            task_data: Task data from Kafka

        Returns:
            Simulation results
        """
        logger.info(f"Simulating task: {task_data.get('id', 'unknown')}")

        # TODO: Implement actual simulation logic
        # This is a placeholder that demonstrates the structure

        # Simulate some processing time
        time.sleep(0.5)

        # Generate mock simulation results
        result = {
            "task_id": task_data.get("id"),
            "worker_id": self.worker_id,
            "simulation_time": time.time(),
            "status": "completed",
            "metrics": {
                "execution_time": task_data.get("runtime", 0),
                "cpu_usage": task_data.get("cpu_request", 0),
                "memory_usage": task_data.get("memory_request", 0),
                "power_consumption": self._estimate_power(task_data),
            },
        }

        return result

    def simulate_fragment(self, fragment_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate a workload fragment.

        Args:
            fragment_data: Fragment data from Kafka

        Returns:
            Simulation results
        """
        logger.info(f"Simulating fragment: {fragment_data.get('id', 'unknown')}")

        # TODO: Implement fragment simulation logic

        result = {
            "fragment_id": fragment_data.get("id"),
            "worker_id": self.worker_id,
            "simulation_time": time.time(),
            "status": "completed",
        }

        return result

    def _estimate_power(self, task_data: dict[str, Any]) -> float:
        """Estimate power consumption for a task.

        Args:
            task_data: Task data

        Returns:
            Estimated power in watts
        """
        # Simple power estimation: base + CPU factor + memory factor
        base_power = 50.0
        cpu_power = task_data.get("cpu_request", 0) * 30.0
        mem_power = task_data.get("memory_request", 0) * 5.0

        return base_power + cpu_power + mem_power

    def process_message(self, message):
        """Process a single Kafka message.

        Args:
            message: Kafka message
        """
        topic = message.topic
        value = message.value

        logger.debug(f"Received message from topic '{topic}'")

        try:
            if topic == self.workload_topic:
                # Process task aggregate (includes fragments)
                result = self.simulate_task(value)
                send_message(
                    self.producer,
                    topic="simulation-results",
                    message=result,
                    key=result.get("task_id"),
                )

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
    logger.info(f"Kafka bootstrap servers: {kafka_bootstrap_servers}")
    logger.info(f"Workload topic: {workload_topic}")

    # Get worker configuration from environment
    worker_id = os.getenv("WORKER_ID", "worker-1")
    consumer_group = os.getenv("CONSUMER_GROUP", "sim-workers")

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
                consumer_group=consumer_group,
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
