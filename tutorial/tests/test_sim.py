"""Tests for writing OpenDC inputs and running cached simulations."""

import logging
import time

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import REPO

from opendt_tutorial import sim
from opendt_tutorial.data import TRACE_END, TRACE_START
from opendt_tutorial.sim import simulate, write_inputs

SIX_HOURS = TRACE_START + pd.Timedelta("6h")
LIVE_RUN_1 = REPO / "data/2026_05_05_06_54_23/simulator/opendc/run_1/input/workload"  # Radu's uncalibrated run


def test_input_parquet_schema(tmp_path):
    write_inputs(until=SIX_HOURS, out_dir=tmp_path)
    tasks = pq.read_schema(tmp_path / "tasks.parquet")
    assert tasks.field("id").type == pa.int32() and not tasks.field("id").nullable
    assert tasks.field("submission_time").type == pa.int64() and not tasks.field("submission_time").nullable
    frags = pq.read_schema(tmp_path / "fragments.parquet")
    assert [(f.name, f.type, f.nullable) for f in frags] == [
        ("id", pa.int32(), False),
        ("duration", pa.int64(), False),
        ("cpu_count", pa.int32(), False),
        ("cpu_usage", pa.float64(), False),
    ]


def test_inputs_cover_jobs_submitted_before_until(tmp_path):
    assert write_inputs(until=TRACE_START + pd.Timedelta("5min"), out_dir=tmp_path) == 122
    assert write_inputs(until=SIX_HOURS, out_dir=tmp_path) == 153


@pytest.mark.skipif(not LIVE_RUN_1.exists(), reason="needs Radu's recorded live-twin run in data/")
def test_inputs_match_live_twin_window(tmp_path):
    write_inputs(until=TRACE_START + pd.Timedelta("5min"), out_dir=tmp_path)
    for name in ("tasks.parquet", "fragments.parquet"):
        ours, live = pq.read_table(tmp_path / name), pq.read_table(LIVE_RUN_1 / name)
        assert ours.schema.equals(live.schema, check_metadata=False)
        assert ours.equals(live), name


@pytest.mark.opendc
@pytest.mark.skipif(not LIVE_RUN_1.exists(), reason="needs Radu's recorded live-twin run in data/")
def test_power_matches_live_twin_window():
    """The notebooks' engine predicts exactly what the live twin predicted for window 1."""
    live_out = LIVE_RUN_1.parents[1] / "output"
    live = pq.read_table(next(live_out.glob("**/powerSource.parquet")), columns=["timestamp_absolute", "power_draw"])
    live = live.to_pandas().set_index("timestamp_absolute")["power_draw"]
    ours = simulate(until=TRACE_START + pd.Timedelta("5min")).forecast["power_draw"]
    ours.index = (ours.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1ms")
    assert len(live) > 100 and ours.reindex(live.index).equals(live)  # bit-identical


def test_epoch_ms_is_utc_independent_of_local_tz(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Amsterdam")
    time.tzset()
    try:
        write_inputs(until=TRACE_START + pd.Timedelta("1h"), out_dir=tmp_path)
        assert pq.read_table(tmp_path / "tasks.parquet")["submission_time"][0].as_py() == 1665093600000
    finally:
        monkeypatch.undo()
        time.tzset()


def test_until_is_clipped(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert write_inputs(until=TRACE_END + pd.Timedelta("1d"), out_dir=tmp_path) == 7850
    assert "end of the trace" in caplog.text


def test_until_before_trace_start_is_rejected():
    with pytest.raises(ValueError, match="after the trace start"):
        simulate(until=TRACE_START)


@pytest.mark.opendc
def test_simulate_6h_runs_and_is_plausible():
    r = simulate(until=SIX_HOURS)
    assert r.power.index[0] == TRACE_START + pd.Timedelta(seconds=150)
    assert 6_900 <= r.power["power_draw"].min() and r.power["power_draw"].max() <= 48_300
    assert r.service["hosts_up"].eq(277).all()


@pytest.mark.opendc
def test_result_clipped_to_until():
    r = simulate(until=SIX_HOURS)
    assert r.power.index.max() <= SIX_HOURS < r.forecast.index.max()
    assert r.service.index.max() <= SIX_HOURS


@pytest.mark.opendc
def test_summary_matches_hand_computed_sums():
    r = simulate(until=SIX_HOURS)
    s = r.summary()
    assert s["energy_kwh"] == pytest.approx(r.power["energy_usage"].sum() / 3.6e6)
    assert s["co2_kg"] == pytest.approx(r.power["carbon_emission"].sum() / 1000)
    assert s["max_pending"] == 0 and s["jobs_waited"] == 0  # 277 hosts never queue on SURF


@pytest.mark.opendc
def test_cache_hit_does_not_rerun(monkeypatch):
    simulate(until=SIX_HOURS)

    def boom(*_args, **_kwargs):
        raise AssertionError("OpenDC must not run on a cache hit")

    monkeypatch.setattr(sim, "_run_opendc", boom)
    assert simulate(until=SIX_HOURS).cached is True


@pytest.mark.opendc
def test_corrupt_cache_is_rerun():
    first = simulate(until=SIX_HOURS)
    power_file = next(first.run_dir.glob("output/**/powerSource.parquet"))
    power_file.write_bytes(b"PAR1")  # what an interrupted OpenDC run leaves behind
    again = simulate(until=SIX_HOURS)
    assert again.cached is False and len(again.power) == len(first.power)
