"""The producers replay the trace at the current speed, and follow a speed change at once."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# services/dc-mock, for `import dc_mock`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dc_mock.producers import base  # noqa: E402
from dc_mock.speed import Speed  # noqa: E402

T0 = datetime(2022, 10, 6, 22, tzinfo=UTC)


class Replay(base.BaseProducer):
    """A producer without Kafka, on a fake wall clock that `wait_interruptible` moves forward."""

    def __init__(self, speed, on_tick=lambda wall: None):
        super().__init__("kafka:9092", speed, "topic")
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


def test_waits_for_the_trace_at_the_current_speed(replay):
    producer = replay(10)
    assert producer.wait_until(T0 + timedelta(seconds=100)) is False
    assert producer.wall == pytest.approx(10)


def test_a_speed_change_applies_from_where_the_replay_is(replay):
    speed = Speed(1)

    def speed_up(wall):
        if wall >= 10:  # after 10 s at real time, 10 s of the trace are done
            speed.factor = 10

    producer = replay(1, speed_up)
    producer.speed = speed
    producer.wait_until(T0 + timedelta(seconds=100))
    assert producer.wall == pytest.approx(10 + 90 / 10)  # the other 90 s of the trace at 10x


def test_maximum_speed_does_not_wait(replay):
    producer = replay(-1)
    assert producer.wait_until(T0 + timedelta(hours=1)) is False
    assert producer.wall == 0
