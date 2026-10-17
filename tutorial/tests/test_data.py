"""Tests for SURF workload, measured power and carbon trace loading."""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from opendt_tutorial.data import (
    CARBON_ZONES,
    TRACE_END,
    TRACE_START,
    carbon_intensity,
    carbon_trace_path,
    load_surf,
    measured_power,
)


def test_trace_window_constants():
    assert TRACE_START == pd.Timestamp("2022-10-06 22:00", tz="UTC")
    assert TRACE_END == pd.Timestamp("2022-10-13 22:00", tz="UTC")


def test_load_surf_shapes():
    s = load_surf()
    assert len(s.tasks) == 7850 and len(s.fragments) == 2_323_475
    assert s.measured.index.tz is not None
    assert s.measured.index[0] == TRACE_START + pd.Timedelta(seconds=30)
    assert 21_000 < s.measured.mean() < 22_500


def test_task_ids_are_ints_and_times_are_utc():
    s = load_surf()
    assert pd.api.types.is_integer_dtype(s.tasks["id"]) and pd.api.types.is_integer_dtype(s.fragments["id"])
    assert str(s.tasks["submission_time"].dt.tz) == "UTC"
    assert s.tasks["submission_time"].min() == TRACE_START


def test_measured_power_slice_has_30s_samples():
    one_hour = measured_power(TRACE_START, TRACE_START + pd.Timedelta("1h"))
    assert len(one_hour) == 120  # 22:00:30 … 23:00:00 at 30-s steps


def test_carbon_week_means():
    w = slice(TRACE_START, TRACE_END - pd.Timedelta("1ms"))
    assert abs(carbon_intensity("NO")[w].mean() - 29.1) < 0.5
    assert abs(carbon_intensity("PL")[w].mean() - 868.0) < 2


def test_unknown_zone_lists_available():
    with pytest.raises(ValueError, match="SE, NO, FR, NL, DE, PL"):
        carbon_intensity("XX")


def test_carbon_files_have_opendc_schema():
    for zone in CARBON_ZONES:
        schema = pq.read_schema(carbon_trace_path(zone))
        assert schema.field("timestamp").type == pa.timestamp("ms") and not schema.field("timestamp").nullable
        assert schema.field("carbon_intensity").type == pa.float64() and not schema.field("carbon_intensity").nullable


def test_all_simulated_jobs_take_one_host():
    s = load_surf()
    with_frag = s.tasks[s.tasks["id"].isin(s.fragments["id"].unique())]
    assert (with_frag["cpu_count"] == 16).all() and len(with_frag) == 6295
