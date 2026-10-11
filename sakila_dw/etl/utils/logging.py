"""
Logging setup for the ETL pipeline. Structure JSON output lands later
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sakila_dw")


def setup_structured_logging(*args, **kwargs) -> None:  # Phase 2 replaces this
    """Placeholder until structured logging lands (Phase 2)."""
