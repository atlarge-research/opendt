"""Task model from tasks.parquet."""

from datetime import UTC, datetime

# Import Fragment for type hints (avoiding circular import)
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from .fragment import Fragment


class Task(BaseModel):
    """Represents a computational task from the workload trace.

    This is the AGGREGATE ROOT for workload events.

    Schema matches tasks.parquet:
    - id: Task identifier (parsed from string to int)
    - submission_time: Task submission timestamp (epoch ms)
    - duration: Task duration in milliseconds
    - cpu_count: Number of CPU cores
    - cpu_capacity: MHz per CPU core
    - mem_capacity: Memory in MB
    - fragments: List of child fragments (aggregated, not in parquet)
    """

    id: int = Field(..., description="Unique task identifier")
    submission_time: datetime = Field(..., description="Task submission timestamp (epoch ms)")
    duration: int = Field(..., description="Task duration in milliseconds", ge=0)
    cpu_count: int = Field(..., description="Number of CPU cores", ge=0)
    cpu_capacity: float = Field(..., description="MHz per CPU core", ge=0)
    mem_capacity: int = Field(..., description="Memory capacity in MB", ge=0)

    # AGGREGATION FIELD: Not in Parquet, populated by producer
    fragments: list["Fragment"] = Field(default_factory=list, description="Child fragments")

    @field_validator("id", mode="before")
    @classmethod
    def parse_id(cls, v: str | int) -> int:
        """Parse task ID from string to int."""
        if isinstance(v, str):
            # Handle "task-123" -> 123
            if "task-" in v:
                return int(v.split("-")[1])
            return int(v)
        return v

    @field_validator("submission_time", mode="before")
    @classmethod
    def parse_submission_time(cls, v: datetime | int | float | str) -> datetime:
        """Parse submission time from epoch milliseconds to datetime (UTC-aware).
        
        Args:
            v: Timestamp as milliseconds (int/float), datetime object, or ISO string
            
        Returns:
            UTC-aware datetime object
        """
        if isinstance(v, (int, float)):
            # Convert milliseconds to seconds for datetime, make it UTC-aware
            return datetime.fromtimestamp(v / 1000.0, tz=UTC)
        elif isinstance(v, str):
            # Parse ISO format string
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            # Ensure UTC if not already timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        elif isinstance(v, datetime):
            # If already datetime but naive, make it UTC
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v
        return v

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds (convenience property)."""
        return self.duration / 1000.0

    @property
    def total_cpu_mhz(self) -> float:
        """Get total CPU capacity in MHz."""
        return self.cpu_count * self.cpu_capacity

    @property
    def mem_capacity_gb(self) -> float:
        """Get memory capacity in GB (convenience property)."""
        return self.mem_capacity / 1024.0

    @property
    def fragment_count(self) -> int:
        """Get number of fragments."""
        return len(self.fragments)

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "submission_time": "2024-01-01T00:00:00Z",
                "duration": 120500,
                "cpu_count": 4,
                "cpu_capacity": 2400.0,
                "mem_capacity": 4096,
                "fragments": [],
            }
        }
