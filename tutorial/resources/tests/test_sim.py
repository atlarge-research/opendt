"""Tests for writing OpenDC inputs and running cached simulations."""

import dataclasses
import logging
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from conftest import REPO
from odt_common.models import Fragment, Task
from odt_common.odc_runner import OpenDCRunner
from resources import sim
from resources.data import TRACE_END, TRACE_START, carbon_intensity
from resources.paths import PATHS
from resources.sim import simulate, simulate_many, write_inputs

SIX_HOURS = TRACE_START + pd.Timedelta("6h")
DAY = TRACE_START + pd.Timedelta("24h")
LIVE_RUN = REPO / "data/2026_05_05_06_54_23"  # Radu's uncalibrated live-twin run (5-min windows)
needs_live_run = pytest.mark.skipif(
    not LIVE_RUN.exists(), reason="needs Radu's recorded live-twin run in data/"
)


def boom(*_args, **_kwargs):
    raise AssertionError("OpenDC must not run")


def shipped(monkeypatch):
    """The notebooks' shipped results (conftest hides them: the other tests run OpenDC)."""
    monkeypatch.setattr(sim, "PATHS", dataclasses.replace(sim.PATHS, results=PATHS.results))


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
def test_full_week_has_one_row_per_timestamp():
    """OpenDC writes the very last instant of the trace twice (the second time with 0 J)."""
    r = simulate(until=TRACE_END)
    assert r.power.index.is_unique and r.service.index.is_unique
    # the service row kept for that instant is the final state: every job has finished
    assert r.service["tasks_completed"].iloc[-1] == (r.tasks["finish_time"] <= TRACE_END).sum()


@pytest.mark.opendc
def test_summary_is_physically_consistent():
    s = simulate(until=SIX_HOURS).summary()
    assert s["energy_kwh"] == pytest.approx(
        s["avg_power_kw"] * 6, rel=1e-3
    )  # 6 h at the average power
    grid = carbon_intensity()[TRACE_START:SIX_HOURS]
    assert grid.min() * s["energy_kwh"] / 1000 <= s["co2_kg"] <= grid.max() * s["energy_kwh"] / 1000
    assert s["jobs_waited"] == 0 and s["waiting_at_end"] == 0  # 277 hosts never queue on SURF


@pytest.mark.opendc
def test_summary_counts_jobs_still_waiting_when_the_run_ends():
    """With a quarter of the machines, part of day 1's work is deferred past the end of the day."""
    r = simulate(until=TRACE_START + pd.Timedelta("24h"), hosts=69)
    s = r.summary()
    assert s["waiting_at_end"] == r.service["tasks_pending"].iloc[-1] > 100  # OpenDC agrees
    assert s["jobs_waited"] > s["waiting_at_end"]


@pytest.mark.opendc
def test_simulate_many_hosts_keys():
    runs = simulate_many("hosts", [138, 2770], until=SIX_HOURS)
    assert set(runs) == {138, 2770} and runs[2770].label == "hosts = 2,770"
    assert (
        runs[138].service["hosts_up"].max() == 138 and runs[2770].service["hosts_up"].max() == 2770
    )


@pytest.mark.opendc
def test_cache_hit_does_not_rerun(monkeypatch):
    simulate(until=SIX_HOURS)
    monkeypatch.setattr(sim, "_run_opendc", boom)
    assert simulate(until=SIX_HOURS).cached is True


@pytest.mark.opendc
def test_interrupted_run_is_rerun():
    first = simulate(until=SIX_HOURS)
    (first.run_dir / "DONE").unlink()  # an interrupted run never writes DONE
    again = simulate(until=SIX_HOURS)
    assert again.cached is False and again.power.equals(first.power)


def test_the_notebooks_simulations_need_no_opendc(monkeypatch):
    shipped(monkeypatch)
    monkeypatch.setattr(sim, "_run_opendc", boom)
    assert simulate(until=DAY, hosts=69).run_dir.parent == PATHS.results


def test_a_simulation_not_precomputed_needs_java(monkeypatch):
    monkeypatch.setattr(sim, "java_version", lambda: None)
    with pytest.raises(RuntimeError, match="Java 21"):
        simulate(until=SIX_HOURS, hosts=13)


@pytest.mark.opendc
def test_shipped_results_equal_a_fresh_opendc_run(monkeypatch):
    fresh = simulate(until=DAY, hosts=138)
    shipped(monkeypatch)
    loaded = simulate(until=DAY, hosts=138)
    assert loaded.run_dir.parent == PATHS.results
    assert all(getattr(loaded, f).equals(getattr(fresh, f)) for f in ("power", "service", "tasks"))


@pytest.mark.opendc
def test_r_as_int_or_float_is_the_same_simulation(monkeypatch):
    simulate(until=SIX_HOURS, r=5)
    monkeypatch.setattr(sim, "_run_opendc", boom)
    assert simulate(until=SIX_HOURS, r=5.0).cached
