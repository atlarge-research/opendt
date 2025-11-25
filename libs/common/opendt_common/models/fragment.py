"""Fragment model from fragments.parquet."""

from pydantic import BaseModel, Field, field_validator


class Fragment(BaseModel):
    """Represents a workload fragment.

    Schema matches fragments.parquet:
    - task_id: Task ID (foreign key, aliased from 'id' in parquet)
    - duration: Fragment duration in milliseconds
    - cpu_count: Number of CPU cores
    - cpu_usage: MHz usage per CPU core
    """

    task_id: int = Field(..., alias="id", description="Task ID (foreign key)")
    duration: int = Field(..., description="Fragment duration in milliseconds", ge=0)
    cpu_count: int = Field(..., description="Number of CPU cores", ge=0)
    cpu_usage: float = Field(..., description="MHz usage per CPU core", ge=0)

    @field_validator("task_id", mode="before")
    @classmethod
    def parse_id(cls, v: str | int) -> int:
        """Parse task ID from string to int."""
        if isinstance(v, str):
            # Handle "task-123" -> 123
            if "task-" in v:
                return int(v.split("-")[1])
            return int(v)
        return v

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds (convenience property)."""
        return self.duration / 1000.0

    @property
    def total_cpu_usage_mhz(self) -> float:
        """Get total CPU usage in MHz."""
        return self.cpu_count * self.cpu_usage

    class Config:
        populate_by_name = True  # Allow both 'id' and 'task_id'
        json_schema_extra = {
            "example": {
                "id": 123,  # Will be mapped to task_id
                "duration": 5000,
                "cpu_count": 4,
                "cpu_usage": 1800.0,
            }
        }
