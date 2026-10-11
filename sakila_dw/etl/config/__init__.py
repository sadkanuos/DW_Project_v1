"""
Centralized configuration for ETL pipeline.
Loads from environment variables and optional YAML config files.
"""

import os
import yaml
from dataclasses import dataclass, field
from dotenv import load_dotenv
from etl.config.loader import load_yaml_config
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

load_dotenv()


@dataclass
class DatabaseConfig:
    host: str
    user: str
    password: str
    database: str
    schema: Optional[str] = None
    port: int = 3306

    @classmethod
    def from_env(
        cls: Type["DatabaseConfig"], prefix: str, schema: Optional[str] = None
    ) -> "DatabaseConfig":
        """Load database config from environment variables with given prefix."""
        return cls(
            host=os.environ[f"{prefix}_HOST"],
            port=int(os.environ.get(f"{prefix}_PORT", "3306")),
            user=os.environ[f"{prefix}_USER"],
            password=os.environ[f"{prefix}_PASSWORD"],
            database=os.environ[f"{prefix}_DB"],
            schema=schema,
        )


@dataclass
class RetryConfig:
    """Retry behavior configuration."""

    max_attempts: int = 3
    backoff_seconds: int = 2
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


@dataclass
class BatchConfig:
    """Batch processing configuration."""

    size: int = 10000
    staging_truncate: bool = True


@dataclass
class EtlConfig:
    """Main ETL Configuration container."""

    mysql: DatabaseConfig
    postgres: DatabaseConfig
    retry: RetryConfig = field(default_factory=RetryConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    staging_schema: str = "staging"
    mart_schema: str = "mart"
    etl_schema: str = "etl"
    config_dir: Path = field(default_factory=lambda: Path(__file__).parent)

    @property
    def staging_config_path(self) -> Path:
        """Path to staging.yaml configuration file."""
        return self.config_dir / "staging.yaml"

    @property
    def mart_config_path(self) -> Path:
        """Path to mart.yaml configuration file."""
        return self.config_dir / "mart.yaml"

    @property
    def dq_checks_config_path(self) -> Path:
        """Path to dq_checks.yaml configuration file."""
        return self.config_dir / "dq_checks.yaml"

    @property
    def staging_config(self) -> Dict[str, Any]:
        """Load staging table configurations from YAML."""
        if self.staging_config_path.exists():
            return load_yaml_config(self.staging_config_path)
        return {}

    @property
    def mart_config(self) -> Dict[str, Any]:
        """Load mart dimension & bridge table configurations from YAML."""
        if self.mart_config_path.exists():
            return load_yaml_config(self.mart_config_path)
        return {}

    @property
    def dq_checks(self) -> List[Dict[str, Any]]:
        """Load data quality checks from YAML."""
        if self.dq_checks_config_path.exists():
            with open(self.dq_checks_config_path, encoding="utf-8") as f:
                return yaml.safe_load(f).get("checks", [])
        return []


def load_config() -> EtlConfig:
    """Load the global ETL Configuration from environment variables."""
    return EtlConfig(
        mysql=DatabaseConfig.from_env("MYSQL", schema=None),
        postgres=DatabaseConfig.from_env("PG", schema=None),
    )
