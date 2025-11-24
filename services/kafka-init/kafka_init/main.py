#!/usr/bin/env python3
"""Kafka Infrastructure Initialization Script.

This script:
1. Loads configuration from the environment
2. Creates Kafka topics based on the configuration
3. Applies partitions, replication factor, and topic-specific settings
4. Exits with code 1 if creation fails (Fail Fast)
"""

import logging
import sys
import time

from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError
from opendt_common import load_config_from_env

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def ensure_topics_exist(
    bootstrap_servers: str,
    topics: list[NewTopic],
    max_retries: int = 10,
    retry_delay: float = 2.0,
) -> bool:
    """Ensure Kafka topics exist, creating them if necessary.

    Args:
        bootstrap_servers: Kafka bootstrap servers
        topics: List of NewTopic objects defining topic configurations
        max_retries: Maximum number of connection retries
        retry_delay: Delay between retries in seconds

    Returns:
        True if all topics exist or were created successfully

    Raises:
        KafkaError: If topics cannot be created after max retries
    """
    if not topics:
        logger.info("No topics to create")
        return True

    topic_names = [t.name for t in topics]

    for attempt in range(max_retries):
        try:
            admin_client = KafkaAdminClient(
                bootstrap_servers=bootstrap_servers,
                client_id="topic-manager",
                request_timeout_ms=10000,
            )

            # Get existing topics
            existing_topics = admin_client.list_topics()
            topics_to_create = [t for t in topics if t.name not in existing_topics]

            if not topics_to_create:
                logger.info(f"All topics already exist: {topic_names}")
                admin_client.close()
                return True

            # Create missing topics with their specific configurations
            try:
                admin_client.create_topics(topics_to_create, validate_only=False)
                created_names = [t.name for t in topics_to_create]
                logger.info(f"Created topics: {created_names}")

                # Give Kafka a moment to create the topics
                time.sleep(1.0)

                # Verify topics were created
                existing_topics_after = admin_client.list_topics()
                still_missing = [
                    t.name for t in topics_to_create if t.name not in existing_topics_after
                ]

                if still_missing:
                    logger.warning(f"Some topics may not be ready yet: {still_missing}")
                else:
                    logger.info(f"✓ Successfully ensured all topics exist: {topic_names}")

                admin_client.close()
                return True

            except TopicAlreadyExistsError:
                logger.info("Topics already exist (race condition)")
                admin_client.close()
                return True

        except KafkaError as e:
            logger.warning(f"Failed to connect to Kafka (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

    return False


def main() -> int:
    """Initialize Kafka infrastructure.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    try:
        # Load configuration from environment
        logger.info("Loading configuration...")
        config = load_config_from_env()
        logger.info(f"Configuration loaded for workload: {config.workload}")

        # Extract Kafka configuration
        kafka_config = config.kafka
        logger.info(f"Kafka bootstrap servers: {kafka_config.bootstrap_servers}")
        logger.info(f"Topics to create: {list(kafka_config.topics.keys())}")

        # Convert topic configurations to NewTopic objects
        new_topics: list[NewTopic] = []
        for logical_key, topic_config in kafka_config.topics.items():
            logger.info(
                f"  - {logical_key}: {topic_config.name} "
                f"(partitions={topic_config.partitions}, "
                f"replication_factor={topic_config.replication_factor})"
            )

            # Create NewTopic with configuration
            new_topic = NewTopic(
                name=topic_config.name,
                num_partitions=topic_config.partitions,
                replication_factor=topic_config.replication_factor,
                topic_configs=topic_config.config,  # Apply topic-specific configs
            )
            new_topics.append(new_topic)

        # Ensure topics exist
        logger.info("Creating Kafka topics...")
        success = ensure_topics_exist(
            bootstrap_servers=kafka_config.bootstrap_servers,
            topics=new_topics,
            max_retries=30,  # Kafka may take time to start
            retry_delay=2.0,
        )

        if success:
            logger.info("✅ Kafka infrastructure initialization complete")
            return 0
        else:
            logger.error("❌ Failed to initialize Kafka infrastructure")
            return 1

    except Exception as e:
        logger.error(f"❌ Error during Kafka initialization: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
