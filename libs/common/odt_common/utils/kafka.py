"""Kafka utilities for OpenDT services."""

import json
import logging
import os
from typing import Any

from kafka import KafkaConsumer, KafkaProducer

logger = logging.getLogger(__name__)


def get_kafka_bootstrap_servers() -> str:
    """Get Kafka bootstrap servers from environment or use default."""
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")


def get_kafka_producer(bootstrap_servers: str | None = None, **kwargs: Any) -> KafkaProducer:
    """A producer of JSON messages; `kwargs` override its settings."""
    if bootstrap_servers is None:
        bootstrap_servers = get_kafka_bootstrap_servers()

    default_config = {
        "bootstrap_servers": bootstrap_servers,
        "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
        "key_serializer": lambda k: k.encode("utf-8") if k else None,
        "acks": "all",
        "retries": 3,
        "max_in_flight_requests_per_connection": 1,
        "linger_ms": 10,  # batches of at most 10 ms
        "batch_size": 16384,
        # tasks with many fragments make large messages
        "max_request_size": 10485760,  # 10 MB, 10x Kafka's default
    }

    config = {**default_config, **kwargs}

    logger.info(f"Creating Kafka producer for {bootstrap_servers}")
    return KafkaProducer(**config)


def get_kafka_consumer(
    topics: list[str], group_id: str, bootstrap_servers: str | None = None, **kwargs: Any
) -> KafkaConsumer:
    """A consumer of JSON messages, from its group's earliest offset; `kwargs` override settings."""
    if bootstrap_servers is None:
        bootstrap_servers = get_kafka_bootstrap_servers()

    default_config = {
        "bootstrap_servers": bootstrap_servers,
        "group_id": group_id,
        "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
        "key_deserializer": lambda k: k.decode("utf-8") if k else None,
        "auto_offset_reset": "earliest",
        "enable_auto_commit": True,
        "max_poll_records": 500,
    }

    config = {**default_config, **kwargs}

    logger.info(f"Creating Kafka consumer for topics {topics} in group {group_id}")
    return KafkaConsumer(*topics, **config)


def send_message(
    producer: KafkaProducer, topic: str, message: dict[str, Any], key: str | None = None
) -> None:
    """Send a message and wait until Kafka has it."""
    producer.send(topic, key=key, value=message).get(timeout=10)
