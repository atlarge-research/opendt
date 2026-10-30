"""The producers replay the trace at the current speed, and follow a speed change at once."""

from datetime import UTC, datetime, timedelta

import pytest
from dc_mock.producers import base
from dc_mock.speed import Speed

T0 = datetime(2022, 10, 6, 22, tzinfo=UTC)


class Replay(base.BaseProducer):
    """A producer without Kafka, on a fake wall clock that `wait_interruptible` moves forward."""

    def __init__(self, speed, on_tick):
        super().__init__(speed, "topic")
        self.wall, self.on_tick = 0.0, on_tick

    def run(self):
        pass

    def wait_interruptible(self, seconds):
        self.wall += seconds
        self.on_tick(self.wall)
        return False


@pytest.fixture
def replay(monkeypatch):
    def make(factor, on_tick=lambda wall: None):
        producer = Replay(Speed(factor), on_tick)
        monkeypatch.setattr(base.time, "time", lambda: producer.wall)
        producer.start_clock(T0)
        return producer

    return make


def test_waits_at_speed(replay):
    producer = replay(10)
    assert producer.wait_until(T0 + timedelta(seconds=100)) is False
    assert producer.wall == pytest.approx(10)


def test_speed_change(replay):
    def speed_up(wall):
        if wall >= 10:  # after 10 s at real time, 10 s of the trace are done
            producer.speed.factor = 10

    producer = replay(1, speed_up)
    producer.wait_until(T0 + timedelta(seconds=100))
    assert producer.wall == pytest.approx(10 + 90 / 10)  # the other 90 s of the trace at 10x


def test_max_speed(replay):
    producer = replay(-1)
    assert producer.wait_until(T0 + timedelta(hours=1)) is False
    assert producer.wall == 0
