"""Tests for writing OpenDC inputs and running cached simulations."""

import logging
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from conftest import REPO
from odt_common.models import Fragment, Task
from odt_common.odc_runner import OpenDCRunner
from opendt_tutorial import sim
from opendt_tutorial.data import TRACE_END, TRACE_START, carbon_intensity
from opendt_tutorial.paths import PATHS
from opendt_tutorial.sim import simulate, simulate_many, write_inputs

SIX_HOURS = TRACE_START + pd.Timedelta("6h")
LIVE_RUN = REPO / "data/2026_05_05_06_54_23"  # Radu's uncalibrated live-twin run (5-min windows)
needs_live_run = pytest.mark.skipif(
    not LIVE_RUN.exists(), reason="needs Radu's recorded live-twin run in data/"
)


def test_input_schema_matches_opendt_runner(tmp_path):
    """Our OpenDC input has the schema OpenDT's own runner writes for the live twin."""
    task = Task(
        id=1,
        submission_time=TRACE_START,
        duration=30_000,
        cpu_count=16,
        cpu_capacity=33_600.0,
        mem_capacity=100_000,
        fragments=[Fragment(id=1, duration=30_000, cpu_count=16, cpu_usage=100.0)],
    )
    runner = OpenDCRunner(PATHS.opendc_bin)
    runner._create_tasks_parquet([task], tmp_path / "tasks.parquet")
    runner._create_fragments_parquet([task], tmp_path / "fragments.parquet")
    write_inputs(until=SIX_HOURS, out_dir=tmp_path / "ours")
    for name in ("tasks.parquet", "fragments.parquet"):
        assert pq.read_schema(tmp_path / "ours" / name).equals(
            pq.read_schema(tmp_path / name), check_metadata=False
        )


def test_inputs_cover_jobs_submitted_before_until(tmp_path):
    assert write_inputs(until=TRACE_START + pd.Timedelta("5min"), out_dir=tmp_path) == 122
    assert write_inputs(until=SIX_HOURS, out_dir=tmp_path) == 153


@needs_live_run
def test_inputs_match_live_twin_window(tmp_path):
    write_inputs(until=TRACE_START + pd.Timedelta("5min"), out_dir=tmp_path)
    for name in ("tasks.parquet", "fragments.parquet"):
        live = pq.read_table(LIVE_RUN / "simulator/opendc/run_1/input/workload" / name)
        assert pq.read_table(tmp_path / name).equals(live), name


@pytest.mark.opendc
@needs_live_run
def test_one_run_equals_the_live_twins_stitched_windows():
    """A single run reproduces the live twin's window-by-window predictions exactly."""
    live = pd.read_parquet(LIVE_RUN / "simulator/agg_results.parquet").set_index("timestamp")[
        "power_draw"
    ]
    ours = simulate(until=live.index.max()).power["power_draw"]
    assert len(live) == 278 and np.array_equal(ours.loc[live.index].to_numpy(), live.to_numpy())


def test_epoch_ms_is_utc_independent_of_local_tz(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Amsterdam")
    time.tzset()
    try:
        write_inputs(until=TRACE_START + pd.Timedelta("1h"), out_dir=tmp_path)
        assert (
            pq.read_table(tmp_path / "tasks.parquet")["submission_time"][0].as_py() == 1665093600000
        )
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


def test_workers_env_override(monkeypatch):
    monkeypatch.setenv("OPENDT_TUTORIAL_WORKERS", "1")
    assert sim.default_workers() == 1


@pytest.mark.opendc
def test_simulate_6h_runs_and_is_plausible():
    r = simulate(until=SIX_HOURS)
    assert r.power.index[0] == TRACE_START + pd.Timedelta(seconds=150)
    assert 6_900 <= r.power["power_draw"].min() and r.power["power_draw"].max() <= 48_300
    assert r.service["hosts_up"].eq(277).all()


@pytest.mark.opendc
def test_result_ends_at_until():
    r = simulate(until=SIX_HOURS)
    assert r.power.index.max() == SIX_HOURS and r.service.index.max() == SIX_HOURS


@pytest.mark.opendc
def test_summary_is_physically_consistent():
    s = simulate(until=SIX_HOURS).summary()
    assert s["energy_kwh"] == pytest.approx(
        s["avg_power_kw"] * 6, rel=1e-3
    )  # 6 h at the average power
    grid = carbon_intensity()[TRACE_START:SIX_HOURS]
    assert grid.min() * s["energy_kwh"] / 1000 <= s["co2_kg"] <= grid.max() * s["energy_kwh"] / 1000
    assert s["max_pending"] == 0 and s["jobs_waited"] == 0  # 277 hosts never queue on SURF


@pytest.mark.opendc
def test_simulate_many_hosts_keys():
    runs = simulate_many("hosts", [138, 277], until=SIX_HOURS)
    assert set(runs) == {138, 277} and runs[138].label == "hosts=138"
    assert runs[138].service["hosts_up"].max() == 138 and runs[277].service["hosts_up"].max() == 277


@pytest.mark.opendc
def test_cache_hit_does_not_rerun(monkeypatch):
    simulate(until=SIX_HOURS)

    def boom(*_args, **_kwargs):
        raise AssertionError("OpenDC must not run on a cache hit")

    monkeypatch.setattr(sim, "_run_opendc", boom)
    assert simulate(until=SIX_HOURS).cached is True


@pytest.mark.opendc
def test_interrupted_run_is_rerun():
    first = simulate(until=SIX_HOURS)
    (first.run_dir / "DONE").unlink()  # an interrupted run never writes DONE
    again = simulate(until=SIX_HOURS)
    assert again.cached is False and again.power.equals(first.power)
