"""Task model, as in tasks.parquet."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, BaseModel, Field

if TYPE_CHECKING:
    from .fragment import Fragment

# a naive time, as the workload's parquet files hold them, is UTC
UtcDatetime = Annotated[
    datetime, AfterValidator(lambda t: t if t.tzinfo else t.replace(tzinfo=UTC))
]


class Task(BaseModel):
    """A job of the workload, as in tasks.parquet, with its fragments once dc-mock joins them."""

    id: int = Field(..., description="Unique task identifier")
    submission_time: UtcDatetime = Field(..., description="Task submission time")
    duration: int = Field(..., description="Task duration in milliseconds", ge=0)
    cpu_count: int = Field(..., description="Number of CPU cores", ge=0)
    cpu_capacity: float = Field(..., description="MHz per CPU core", ge=0)
    mem_capacity: int = Field(..., description="Memory capacity in MB", ge=0)
    fragments: list["Fragment"] = Field(default_factory=list, description="The task's fragments")
