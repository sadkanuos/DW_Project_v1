"""Configuration loading with environment variable support."""

import os
from pathlib import Path

import re

from typing import Any, Dict
import yaml


def resolve_env_vars(value: Any) -> Any:
    """
    Recusrively resolve environment variables in strings.
    Supports: ${VAR_NAME} and ${VAR_NAME:-default}
    """
    if isinstance(value, str):
        # Pattern: ${VAR_NAME:-default} or ${VAR_NAME}
        pattern = r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?::-([^}]*))?\}"

        def replace_env(match: re.Match) -> str:
            var_name = match.group(1)
            default = match.group(2)
            env_value = os.environ.get(var_name)
            if env_value is None:
                if default is None:
                    raise EnvironmentError(
                        f"Environment Variable {var_name} not set and no default provided"
                    )
                return default

            return env_value

        return re.sub(pattern, replace_env, value)

    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]

    return value


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML config with environment variable resolution"""
    if not config_path.exists():
        return {}

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return resolve_env_vars(config)
