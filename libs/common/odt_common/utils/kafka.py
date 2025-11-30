"""Kafka utilities for OpenDT services."""

import json
import logging
import os
from typing import Any

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


def get_kafka_bootstrap_servers() -> str:
    """Get Kafka bootstrap servers from environment or use default."""
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def get_kafka_producer(bootstrap_servers: str | None = None, **kwargs: Any) -> KafkaProducer:
    """Create a Kafka producer with sensible defaults.

    Args:
        bootstrap_servers: Kafka bootstrap servers (defaults to env var)
        **kwargs: Additional KafkaProducer configuration

    Returns:
        Configured KafkaProducer instance
    """
    if bootstrap_servers is None:
        bootstrap_servers = get_kafka_bootstrap_servers()

    default_config = {
        "bootstrap_servers": bootstrap_servers,
        "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
        "key_serializer": lambda k: k.encode("utf-8") if k else None,
        "acks": "all",
        "retries": 3,
        "max_in_flight_requests_per_connection": 1,
        # Streaming-friendly settings: send immediately rather than batching
        "linger_ms": 10,  # Wait max 10ms before sending a batch
        "batch_size": 16384,  # 16KB batch size (default)
        # Increase message size limits for large task aggregates with many fragments
        "max_request_size": 10485760,  # 10MB (default is 1MB)
        "buffer_memory": 33554432,  # 32MB buffer (default)
    }

    # Merge with user-provided config
    config = {**default_config, **kwargs}

    logger.info(f"Creating Kafka producer for {bootstrap_servers}")
    return KafkaProducer(**config)


def get_kafka_consumer(
    topics: list[str], group_id: str, bootstrap_servers: str | None = None, **kwargs: Any
) -> KafkaConsumer:
    """Create a Kafka consumer with sensible defaults.

    Args:
        topics: List of topics to subscribe to
        group_id: Consumer group ID
        bootstrap_servers: Kafka bootstrap servers (defaults to env var)
        **kwargs: Additional KafkaConsumer configuration

    Returns:
        Configured KafkaConsumer instance
    """
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

    # Merge with user-provided config
    config = {**default_config, **kwargs}

    logger.info(f"Creating Kafka consumer for topics {topics} in group {group_id}")
    return KafkaConsumer(*topics, **config)


_message_count = {"count": 0}  # Mutable counter for first-message logging


def send_message(
    producer: KafkaProducer, topic: str, message: dict[str, Any], key: str | None = None
) -> None:
    """Send a message to a Kafka topic.

    Args:
        producer: KafkaProducer instance
        topic: Topic name
        message: Message payload (will be JSON serialized)
        key: Optional message key
    """
    try:
        future = producer.send(topic, key=key, value=message)
        # Block for 'synchronous' sends
        record_metadata = future.get(timeout=10)

        # Log first few messages at INFO level for debugging
        _message_count["count"] += 1
        if _message_count["count"] <= 5:
            logger.info(
                f"✓ Message {_message_count['count']} sent to {topic} "
                f"partition {record_metadata.partition} offset {record_metadata.offset}"
            )
        else:
            logger.debug(
                f"Message sent to {topic} partition {record_metadata.partition} "
                f"at offset {record_metadata.offset}"
            )
    except KafkaError as e:
        logger.error(f"Failed to send message to {topic}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending message to {topic}: {e}", exc_info=True)
        raise
