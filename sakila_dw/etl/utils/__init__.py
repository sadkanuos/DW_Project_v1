"""
Shared utilities, split for segregation of duties.

Backward compatibility: every name previously importable from
`etl.utils` is re-exported here, so `from etl.utils import X`
keeps working.
"""

from etl.utils.config_helpers import get_config
from etl.utils.connections import (
    get_mysql_connection,
    get_pg_connection,
    get_pg_connection_pool,
    release_pg_connection,
)
from etl.utils.logging import logger, setup_structured_logging  # noqa: F401
from etl.utils.retry import retry
from etl.utils.audit import (
    start_batch,
    finish_batch,
    start_step,
    finish_step,
    run_step,
    record_dq_result,
)

__all__ = [
    "get_config",
    "get_mysql_connection",
    "get_pg_connection",
    "get_pg_connection_pool",
    "release_pg_connection",
    "logger",
    "setup_structured_logging",
    "retry",
    "start_batch",
    "finish_batch",
    "start_step",
    "finish_step",
    "run_step",
    "record_dq_result",
]
