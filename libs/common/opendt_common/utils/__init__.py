"""Shared utilities for OpenDT services."""

from opendt_common.utils.kafka import get_kafka_consumer, get_kafka_producer

__all__ = [
    "get_kafka_producer",
    "get_kafka_consumer",
]
