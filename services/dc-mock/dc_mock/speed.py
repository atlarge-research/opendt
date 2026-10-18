"""The replay speed, shared by all producers and changed at runtime through sys.config."""

import logging
import threading

from odt_common.config import DynamicConfigEvent
from odt_common.utils import get_kafka_consumer

logger = logging.getLogger(__name__)


class Speed:
    """The current speed factor (1 = real time, -1 = maximum speed)."""

    def __init__(self, factor: float):
        self.factor = factor


def follow(speed: Speed, topic: str) -> None:
    """Apply every `global.speed_factor` change published on `topic` to `speed`, from a background thread."""

    def listen():
        for message in get_kafka_consumer([topic], group_id="dc-mock-speed"):
            event = DynamicConfigEvent(**message.value)
            if event.setting_key == "global.speed_factor":
                speed.factor = float(event.new_value)
                logger.info(f"Replay speed changed to {speed.factor}x")

    threading.Thread(target=listen, daemon=True, name="SpeedListener").start()
