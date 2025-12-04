"""Configuration management for OpenDT services.

This module provides:
1. Static configuration from YAML files (startup)
2. Dynamic configuration updates via Kafka (runtime)
3. Path resolution based on workload names
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class KafkaTopicConfig(BaseModel):
    """Configuration for a single Kafka topic."""

    name: str = Field(..., description="The actual topic name")
    partitions: int = Field(default=1, description="Number of partitions", gt=0)
    replication_factor: int = Field(default=1, description="Replication factor", gt=0)
    config: dict[str, str] = Field(
        default_factory=dict, description="Key-value pairs for topic properties"
    )


class KafkaConfig(BaseModel):
    """Kafka infrastructure configuration."""

    topics: dict[str, KafkaTopicConfig] = Field(
        default_factory=dict, description="Topic configurations keyed by logical name"
    )


class GlobalConfig(BaseModel):
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


class DcMockConfig(BaseModel):
    """DC-Mock service configuration."""

    workload: str = Field(..., description="Workload name (e.g., 'SURF')")
    heartbeat_frequency_minutes: int = Field(
        default=1,
        description="Frequency in simulation minutes for workload heartbeat messages",
        gt=0,
    )


class SimulatorConfig(BaseModel):
    """Simulator service configuration."""

    simulation_frequency_minutes: int = Field(
        default=15, description="Simulation frequency in minutes (simulated time)", gt=0
    )
    background_load_nodes: int = Field(
        ...,
        description="Number of nodes reserved for background load (not available for simulation)",
        ge=0,
    )


class CalibratorConfig(BaseModel):
    """Calibrator service configuration."""

    calibrated_property: str = Field(
        default="cpuPowerModel.asymUtil",
        description="Dot-notation path to topology property to calibrate",
    )
    min_value: float = Field(
        default=0.1, description="Minimum value to test for calibrated property", gt=0
    )
    max_value: float = Field(
        default=0.9, description="Maximum value to test for calibrated property", gt=0
    )
    linspace_points: int = Field(default=9, description="Number of linspace points to test", gt=1)
    max_parallel_workers: int = Field(
        default=4, description="Maximum number of parallel OpenDC simulations", gt=0
    )
    mape_window_minutes: int = Field(
        default=1440,  # 24 hours in minutes
        description="Rolling time window in minutes for MAPE calculation",
        gt=0,
    )
    
    # Legacy fields for backwards compatibility (mapped to new fields)
    asym_util_min: float | None = Field(None, exclude=True)
    asym_util_max: float | None = Field(None, exclude=True)
    asym_util_points: int | None = Field(None, exclude=True)
    
    @model_validator(mode='after')
    def handle_legacy_fields(self):
        """Map legacy field names to new ones if present."""
        if self.asym_util_min is not None:
            self.min_value = self.asym_util_min
        if self.asym_util_max is not None:
            self.max_value = self.asym_util_max
        if self.asym_util_points is not None:
            self.linspace_points = self.asym_util_points
        return self


class ServicesConfig(BaseModel):
    """Configuration for all services."""

    dc_mock: DcMockConfig = Field(alias="dc-mock")
    simulator: SimulatorConfig
    calibrator: CalibratorConfig | None = Field(
        None, description="Calibrator config (only required if calibration_enabled=true)"
    )

    class Config:
        populate_by_name = True


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


class WorkloadContext(BaseModel):
    """Workload context with resolved file paths."""

    name: str = Field(default="", description="Workload name (e.g., 'SURF')")
    base_path: Path = Field(default=Path("/app/workload"), description="Base workload directory")
    workload_dir: Path | None = Field(None, description="Direct path to workload directory (overrides base_path/name)")
    metadata: WorkloadMetadata | None = Field(None, description="Workload metadata")

    def __init__(self, **data):
        """Initialize and load metadata if not provided."""
        super().__init__(**data)
        if self.metadata is None and self.workload_config_file.exists():
            self.metadata = WorkloadMetadata.load(self.workload_config_file)

    @property
    def _resolved_workload_dir(self) -> Path:
        """Get resolved workload directory path."""
        if self.workload_dir is not None:
            return self.workload_dir
        return self.base_path / self.name

    @property
    def tasks_file(self) -> Path:
        """Path to tasks.parquet file."""
        return self._resolved_workload_dir / "tasks.parquet"

    @property
    def fragments_file(self) -> Path:
        """Path to fragments.parquet file."""
        return self._resolved_workload_dir / "fragments.parquet"

    @property
    def consumption_file(self) -> Path:
        """Path to consumption.parquet file."""
        return self._resolved_workload_dir / "consumption.parquet"

    @property
    def topology_file(self) -> Path:
        """Path to topology.json file."""
        return self._resolved_workload_dir / "topology.json"

    @property
    def workload_config_file(self) -> Path:
        """Path to workload configuration file."""
        return self._resolved_workload_dir / "workload.yaml"

    @property
    def consumption_offset_ms(self) -> int:
        """Get consumption timestamp offset in milliseconds."""
        if self.metadata:
            return self.metadata.consumption_offset_ms
        return 0

    def exists(self) -> bool:
        """Check if workload directory exists."""
        return self._resolved_workload_dir.exists()

    def get_file_status(self) -> dict[str, bool]:
        """Check which workload files exist."""
        return {
            "tasks": self.tasks_file.exists(),
            "fragments": self.fragments_file.exists(),
            "consumption": self.consumption_file.exists(),
            "topology": self.topology_file.exists(),
        }

    class Config:
        arbitrary_types_allowed = True


class AppConfig(BaseModel):
    """Main application configuration."""

    global_config: GlobalConfig = Field(alias="global", default_factory=lambda: GlobalConfig())
    services: ServicesConfig
    kafka: KafkaConfig = Field(default_factory=lambda: KafkaConfig())

    class Config:
        populate_by_name = True

    @model_validator(mode="after")
    def validate_calibration_config(self) -> "AppConfig":
        """Ensure calibrator config is provided when calibration is enabled."""
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

    def get_workload_context(self, base_path: Path) -> WorkloadContext:
        """Get workload context with resolved paths.

        Args:
            base_path: Override the default base path (/app/data)

        Returns:
            WorkloadContext with resolved file paths
        """
        return WorkloadContext(name=self.workload, base_path=base_path)

    @classmethod
    def load(cls, path: str | Path) -> "AppConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Loaded AppConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If YAML is invalid
        """
        config_path = Path(path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty or invalid YAML in {config_path}")

        return cls(**data)

    def save(self, path: str | Path) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save configuration file
        """
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return self.model_dump()


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

    def apply_to_config(self, config: AppConfig) -> AppConfig:
        """Apply this configuration change to an AppConfig instance.

        Args:
            config: The configuration to update

        Returns:
            Updated configuration (new instance)

        Raises:
            ValueError: If setting_key is invalid
        """
        # Parse the setting key (e.g., "simulation.speed_factor")
        parts = self.setting_key.split(".")

        if len(parts) < 2:
            raise ValueError(f"Invalid setting_key: {self.setting_key}")

        # Create a new config with the updated value
        config_dict = config.to_dict()

        # Navigate to the nested setting
        target = config_dict
        for part in parts[:-1]:
            if part not in target:
                raise ValueError(f"Invalid setting path: {self.setting_key}")
            target = target[part]

        # Update the value
        final_key = parts[-1]
        if final_key not in target:
            raise ValueError(f"Invalid setting key: {self.setting_key}")

        target[final_key] = self.new_value

        # Return new config instance
        return AppConfig(**config_dict)


# Convenience function for loading config from environment
def load_config_from_env(env_var: str = "CONFIG_FILE") -> AppConfig:
    """Load configuration from path specified in environment variable.

    Args:
        env_var: Name of environment variable containing config path

    Returns:
        Loaded AppConfig instance

    Raises:
        ValueError: If environment variable not set
        FileNotFoundError: If config file doesn't exist
    """
    import os

    config_path = os.getenv(env_var)
    if not config_path:
        raise ValueError(f"Environment variable {env_var} not set")

    return AppConfig.load(config_path)
