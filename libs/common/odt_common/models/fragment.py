"""Fragment model, as in fragments.parquet."""

from pydantic import BaseModel, ConfigDict, Field


class Fragment(BaseModel):
    """A segment of a task's execution, as in fragments.parquet, where `id` is its task's."""

    # the parquet file and dc-mock's messages call it id, the model task_id
    model_config = ConfigDict(populate_by_name=True)

    task_id: int = Field(..., alias="id", description="Task ID (foreign key)")
    duration: int = Field(..., description="Fragment duration in milliseconds", ge=0)
    cpu_count: int = Field(..., description="Number of CPU cores", ge=0)
    cpu_usage: float = Field(..., description="MHz usage per CPU core", ge=0)
