#!/usr/bin/env python3
"""kafka-init: creates the Kafka topics of the configuration, with their partitions, replication, and settings
(e.g., compaction), before the other services start; exits with 1 if Kafka does not answer."""

import logging
import time

from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError
from odt_common import load_config_from_env
from odt_common.utils import get_kafka_bootstrap_servers

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def admin(bootstrap_servers: str, attempts: int = 30) -> KafkaAdminClient:
    """An admin client, once Kafka answers (it may take a minute to start)."""
    for attempt in range(1, attempts + 1):
        try:
            return KafkaAdminClient(
                bootstrap_servers=bootstrap_servers,
                client_id="topic-manager",
                request_timeout_ms=10000,
            )
        except KafkaError as error:
            logger.warning(f"Kafka not ready (attempt {attempt}/{attempts}): {error}")
            time.sleep(2)
    raise SystemExit(1)


def main() -> None:
    topics = [
        NewTopic(
            name=topic.name,
            num_partitions=topic.partitions,
            replication_factor=topic.replication_factor,
            topic_configs=topic.config,
        )
        for topic in load_config_from_env().kafka.topics.values()
    ]
    client = admin(get_kafka_bootstrap_servers())
    missing = [topic for topic in topics if topic.name not in client.list_topics()]
    if missing:
        client.create_topics(missing)
    logger.info(f"Topics {[t.name for t in topics]}; created now: {[t.name for t in missing]}")
    client.close()


if __name__ == "__main__":
    main()
