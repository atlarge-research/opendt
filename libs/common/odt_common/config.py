"""Configuration of OpenDT's services: the YAML file read at the start, and the runtime settings the
control panel changes through Kafka (sys.config); plus the files of a workload."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    """A part of the config file; an unknown key is an error, so a typo fails at the start."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class KafkaTopicConfig(Strict):
    """Configuration for a single Kafka topic."""

    name: str = Field(..., description="The actual topic name")
    partitions: int = Field(default=1, description="Number of partitions", gt=0)
    replication_factor: int = Field(default=1, description="Replication factor", gt=0)
    config: dict[str, str] = Field(
        default_factory=dict, description="Key-value pairs for topic properties"
    )


class KafkaConfig(Strict):
    """Kafka infrastructure configuration."""

    topics: dict[str, KafkaTopicConfig] = Field(
        default_factory=dict, description="Topic configurations keyed by logical name"
    )


class GlobalConfig(Strict):
    """Global configuration parameters."""

    speed_factor: float = Field(
        default=10.0, description="Simulation speed: 1.0 = realtime, -1 = max speed, >1 = faster"
    )
    calibration_enabled: bool = Field(default=False, description="Enable power model calibration")

    @field_validator("speed_factor")
    @classmethod
    def validate_speed_factor(cls, v: float) -> float:
        """Validate speed factor is either -1 or positive."""
        if v != -1 and v <= 0:
            raise ValueError("speed_factor must be positive or -1 (max speed)")
        return v


class DcMockConfig(Strict):
    """DC-Mock service configuration."""

    workload: str = Field(..., description="Workload name (e.g., 'SURF')")
    heartbeat_frequency_minutes: int = Field(
        default=1,
        description="Frequency in simulation minutes for workload heartbeat messages",
        gt=0,
    )


class SimulatorConfig(Strict):
    """Simulator service configuration."""

    simulation_frequency_minutes: int = Field(
        default=15, description="Simulation frequency in minutes (simulated time)", gt=0
    )


class CalibratorConfig(Strict):
    """Calibrator service configuration."""

    calibrated_property: str = Field(
        default="cpuPowerModel.calibrationFactor",
        description="Dot-notation path to topology property to calibrate",
    )
    min_value: float = Field(default=3, description="Lowest value of the property to test", gt=0)
    max_value: float = Field(default=9, description="Highest value of the property to test", gt=0)
    linspace_points: int = Field(default=7, description="Number of linspace points to test", gt=1)
    max_parallel_workers: int = Field(
        default=4, description="Maximum number of parallel OpenDC simulations", gt=0
    )
    mape_window_minutes: int = Field(
        default=1440,  # 24 hours in minutes
        description="Rolling time window in minutes for MAPE calculation",
        gt=0,
    )


class ServicesConfig(Strict):
    """Configuration for all services."""

    dc_mock: DcMockConfig = Field(alias="dc-mock")
    simulator: SimulatorConfig
    calibrator: CalibratorConfig | None = Field(
        None, description="Calibrator config (only required if calibration_enabled=true)"
    )


class WorkloadMetadata(BaseModel):
    """Workload-specific metadata and configuration."""

    name: str = Field(..., description="Workload name")
    description: str | None = Field(default=None, description="Workload description")
    consumption_offset_ms: int = Field(
        default=0, description="Offset in ms to add to consumption timestamps"
    )

    @classmethod
    def load(cls, path: Path) -> "WorkloadMetadata":
        """Load workload metadata from YAML file."""
        if not path.exists():
            # Return default if file doesn't exist
            return cls(name=path.parent.name)

        with open(path) as f:
            data = yaml.safe_load(f)

        # Extract relevant fields
        timestamps = data.get("timestamps", {})
        return cls(
            name=data.get("name", path.parent.name),
            description=data.get("description"),
            consumption_offset_ms=timestamps.get("consumption_offset_ms", 0),
        )


@dataclass
class WorkloadContext:
    """The files of a workload, in its folder (e.g., workload/SURF)."""

    workload_dir: Path

    def __post_init__(self):
        self.consumption_offset_ms = WorkloadMetadata.load(
            self.workload_dir / "workload.yaml"
        ).consumption_offset_ms

    @property
    def tasks_file(self) -> Path:
        return self.workload_dir / "tasks.parquet"

    @property
    def fragments_file(self) -> Path:
        return self.workload_dir / "fragments.parquet"

    @property
    def consumption_file(self) -> Path:
        return self.workload_dir / "consumption.parquet"

    @property
    def topology_file(self) -> Path:
        return self.workload_dir / "topology.json"

    def get_file_status(self) -> dict[str, bool]:
        """Which of the workload's files exist."""
        return {
            "tasks": self.tasks_file.exists(),
            "fragments": self.fragments_file.exists(),
            "consumption": self.consumption_file.exists(),
            "topology": self.topology_file.exists(),
        }


class AppConfig(Strict):
    """Main application configuration."""

    global_config: GlobalConfig = Field(alias="global", default_factory=lambda: GlobalConfig())
    services: ServicesConfig
    kafka: KafkaConfig = Field(default_factory=lambda: KafkaConfig())

    @model_validator(mode="after")
    def validate_calibration_config(self) -> "AppConfig":
        """Calibration needs the calibrator's settings."""
        if self.global_config.calibration_enabled and self.services.calibrator is None:
            raise ValueError(
                "Calibration is enabled (global.calibration_enabled=true) but "
                "services.calibrator configuration is missing. Either disable calibration "
                "or provide calibrator configuration."
            )
        return self

    @property
    def workload(self) -> str:
        """Get workload name from dc-mock config."""
        return self.services.dc_mock.workload

    @property
    def calibration_enabled(self) -> bool:
        """Check if calibration is enabled."""
        return self.global_config.calibration_enabled

    @classmethod
    def load(cls, path: str | Path) -> "AppConfig":
        """Load configuration from YAML file."""
        config_path = Path(path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty or invalid YAML in {config_path}")

        return cls(**data)


# the runtime settings on sys.config, by key: the API sends them, the services follow them
SPEED_FACTOR = "global.speed_factor"
SCHEDULER = "simulator.scheduler"
PARALLEL_RUNS = "calibrator.max_parallel_workers"
CALIBRATION = "calibrator.enabled"
CALIBRATION_MIN = "calibrator.min_value"
CALIBRATION_MAX = "calibrator.max_value"
CALIBRATION_POINTS = "calibrator.linspace_points"
MAPE_WINDOW = "calibrator.mape_window_minutes"


class DynamicConfigEvent(BaseModel):
    """Event model for runtime configuration updates via Kafka.

    Published to topic: sys.config

    Example:
        {
            "setting_key": "simulation.speed_factor",
            "new_value": 5.0,
            "timestamp": "2024-01-01T12:00:00Z",
            "source": "api"
        }
    """

    setting_key: str = Field(
        ..., description="Dot-notation path to setting (e.g., 'simulation.speed_factor')"
    )
    new_value: Any = Field(..., description="New value for the setting")
    timestamp: str | None = Field(None, description="ISO timestamp of when the change was made")
    source: str | None = Field(
        None, description="Source of the configuration change (e.g., 'api', 'admin')"
    )


def load_config_from_env(env_var: str = "CONFIG_FILE") -> AppConfig:
    """Load configuration from path specified in environment variable."""
    config_path = os.getenv(env_var)
    if not config_path:
        raise ValueError(f"Environment variable {env_var} not set")

    return AppConfig.load(config_path)
