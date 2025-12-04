"""Tests for Pydantic models with actual SURF workload data."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from odt_common import Consumption, Fragment, Task

# Locate test data
DATA_DIR = Path(__file__).parent.parent.parent.parent / "workload" / "SURF"
TASKS_FILE = DATA_DIR / "tasks.parquet"
FRAGMENTS_FILE = DATA_DIR / "fragments.parquet"
CONSUMPTION_FILE = DATA_DIR / "consumption.parquet"


@pytest.fixture
def tasks_df():
    """Load tasks dataframe."""
    if not TASKS_FILE.exists():
        pytest.skip(f"Test data not found: {TASKS_FILE}")
    return pd.read_parquet(TASKS_FILE)


@pytest.fixture
def fragments_df():
    """Load fragments dataframe."""
    if not FRAGMENTS_FILE.exists():
        pytest.skip(f"Test data not found: {FRAGMENTS_FILE}")
    return pd.read_parquet(FRAGMENTS_FILE)


@pytest.fixture
def consumption_df():
    """Load consumption dataframe."""
    if not CONSUMPTION_FILE.exists():
        pytest.skip(f"Test data not found: {CONSUMPTION_FILE}")
    return pd.read_parquet(CONSUMPTION_FILE)


class TestTaskModel:
    """Test Task Pydantic model."""

    def test_parse_first_task(self, tasks_df):
        """Test parsing first task row."""
        task_dict = tasks_df.iloc[0].to_dict()
        task = Task(**task_dict)

        assert isinstance(task.id, int)
        assert isinstance(task.submission_time, datetime)
        assert task.duration > 0
        assert task.cpu_count >= 0
        assert task.cpu_capacity >= 0
        assert task.mem_capacity >= 0

    def test_parse_all_tasks(self, tasks_df):
        """Test parsing all tasks."""
        errors = []
        for idx, row in tasks_df.iterrows():
            try:
                Task(**row.to_dict())
            except Exception as e:
                errors.append(f"Row {idx}: {e}")

        assert len(errors) == 0, f"Failed to parse {len(errors)} tasks:\n" + "\n".join(errors[:5])

    def test_task_id_parsing(self, tasks_df):
        """Test ID parsing from string."""
        task_dict = tasks_df.iloc[0].to_dict()
        task_dict["id"] = f"task-{task_dict['id']}"
        task = Task(**task_dict)
        assert isinstance(task.id, int)

    def test_task_properties(self, tasks_df):
        """Test computed properties."""
        task = Task(**tasks_df.iloc[0].to_dict())

        assert task.duration_seconds == task.duration / 1000.0
        assert task.total_cpu_mhz == task.cpu_count * task.cpu_capacity
        assert task.mem_capacity_gb == task.mem_capacity / 1024.0

    def test_task_with_fragments(self, tasks_df, fragments_df):
        """Test task with nested fragments."""
        first_task_id = tasks_df.iloc[0]["id"]
        fragments_by_task = fragments_df.groupby("id")

        task_dict = tasks_df.iloc[0].to_dict()

        if first_task_id in fragments_by_task.groups:
            task_fragments = fragments_by_task.get_group(first_task_id)
            task_dict["fragments"] = [
                Fragment(**row.to_dict()) for _, row in task_fragments.iterrows()
            ]

        task = Task(**task_dict)
        assert isinstance(task.fragments, list)
        assert task.fragment_count == len(task.fragments)


class TestFragmentModel:
    """Test Fragment Pydantic model."""

    def test_parse_first_fragment(self, fragments_df):
        """Test parsing first fragment row."""
        fragment_dict = fragments_df.iloc[0].to_dict()
        fragment = Fragment(**fragment_dict)

        assert isinstance(fragment.task_id, int)
        assert fragment.duration > 0
        assert fragment.cpu_count >= 0
        assert fragment.cpu_usage >= 0

    def test_parse_all_fragments(self, fragments_df):
        """Test parsing all fragments."""
        errors = []
        for idx, row in fragments_df.iterrows():
            try:
                Fragment(**row.to_dict())
            except Exception as e:
                errors.append(f"Row {idx}: {e}")

        assert len(errors) == 0, f"Failed to parse {len(errors)} fragments:\n" + "\n".join(
            errors[:5]
        )

    def test_fragment_id_parsing(self, fragments_df):
        """Test ID parsing with alias."""
        fragment_dict = fragments_df.iloc[0].to_dict()
        fragment_dict["id"] = f"task-{fragment_dict['id']}"
        fragment = Fragment(**fragment_dict)
        assert isinstance(fragment.task_id, int)

    def test_fragment_properties(self, fragments_df):
        """Test computed properties."""
        fragment = Fragment(**fragments_df.iloc[0].to_dict())

        assert fragment.duration_seconds == fragment.duration / 1000.0
        assert fragment.total_cpu_usage_mhz == fragment.cpu_count * fragment.cpu_usage


class TestConsumptionModel:
    """Test Consumption Pydantic model."""

    def test_parse_first_consumption(self, consumption_df):
        """Test parsing first consumption row."""
        cons_dict = consumption_df.iloc[0].to_dict()
        consumption = Consumption(**cons_dict)

        assert consumption.power_draw >= 0
        assert consumption.energy_usage >= 0
        assert isinstance(consumption.timestamp, datetime)

    def test_parse_all_consumption(self, consumption_df):
        """Test parsing all consumption records."""
        errors = []
        for idx, row in consumption_df.iterrows():
            try:
                Consumption(**row.to_dict())
            except Exception as e:
                errors.append(f"Row {idx}: {e}")

        assert len(errors) == 0, f"Failed to parse {len(errors)} records:\n" + "\n".join(errors[:5])

    def test_consumption_properties(self, consumption_df):
        """Test computed properties."""
        consumption = Consumption(**consumption_df.iloc[0].to_dict())

        assert consumption.power_draw_kw == consumption.power_draw / 1000.0
        assert consumption.energy_usage_kwh == consumption.energy_usage / 3_600_000.0


class TestAggregation:
    """Test task-fragment aggregation logic."""

    def test_fragments_match_tasks(self, tasks_df, fragments_df):
        """Test that fragment IDs match task IDs."""
        task_ids = set(tasks_df["id"].unique())
        fragment_ids = set(fragments_df["id"].unique())

        assert fragment_ids.issubset(task_ids), "Found fragments with non-existent task IDs"

    def test_full_aggregation(self, tasks_df, fragments_df):
        """Test full aggregation process."""
        fragments_by_task = fragments_df.groupby("id")

        tasks = []
        for _, task_row in tasks_df.iterrows():
            task_dict = task_row.to_dict()
            task_id = task_dict["id"]

            if task_id in fragments_by_task.groups:
                task_fragments = fragments_by_task.get_group(task_id)
                task_dict["fragments"] = [
                    Fragment(**row.to_dict()) for _, row in task_fragments.iterrows()
                ]

            tasks.append(Task(**task_dict))

        assert len(tasks) == len(tasks_df)
        total_fragments = sum(t.fragment_count for t in tasks)
        assert total_fragments == len(fragments_df)


class TestSerializationDeserialization:
    """Test JSON serialization/deserialization."""

    def test_task_json_roundtrip(self, tasks_df):
        """Test task JSON serialization."""
        task = Task(**tasks_df.iloc[0].to_dict())
        json_str = task.model_dump_json()
        task_dict = task.model_dump()

        assert isinstance(json_str, str)
        assert isinstance(task_dict, dict)
        assert task_dict["id"] == task.id

    def test_fragment_json_roundtrip(self, fragments_df):
        """Test fragment JSON serialization."""
        fragment = Fragment(**fragments_df.iloc[0].to_dict())
        json_str = fragment.model_dump_json()
        fragment_dict = fragment.model_dump()

        assert isinstance(json_str, str)
        assert isinstance(fragment_dict, dict)

    def test_consumption_json_roundtrip(self, consumption_df):
        """Test consumption JSON serialization."""
        consumption = Consumption(**consumption_df.iloc[0].to_dict())
        json_str = consumption.model_dump_json()
        cons_dict = consumption.model_dump()

        assert isinstance(json_str, str)
        assert isinstance(cons_dict, dict)
