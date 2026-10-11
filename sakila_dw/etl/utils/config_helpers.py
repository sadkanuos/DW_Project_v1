"""Global config singleton helpers."""

from etl.config import EtlConfig, load_config
from typing import Optional


_config: Optional[EtlConfig] = None


def get_config() -> EtlConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
