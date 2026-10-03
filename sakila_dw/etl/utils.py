"""
Shared utilities: database connections, logging setup, a retry
decorator for transient failures, and helpers for writing to the
etl.batch / etl.load_log / etl.dq_results audit tables.

All functions include full type hints.
"""

import functools
import logging
import os
import time
from typing import (
    Any,
    Callable,
    Optional,
    Type,
    TypeVar,
    Tuple,
    Union,
    cast,
)

import psycopg2
import psycopg2.extensions
from psycopg2.pool import SimpleConnectionPool as PgPool
import pymysql
import pymysql.connections

from dotenv import load_dotenv

from etl.config import load_config, EtlConfig

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sakila_dw")

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])

# Global config instance
_config: Optional[EtlConfig] = None


def get_config() -> EtlConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# ---------------------------------------------------------------
# Connections
# ---------------------------------------------------------------


def get_mysql_connection() -> pymysql.connections.Connection:
    """Open a connection to the Sakila source database."""
    config = get_config()
    return pymysql.connect(
        host=config.mysql.host,
        port=config.mysql.port,
        user=config.mysql.user,
        password=config.mysql.password,
        database=config.mysql.database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_pg_connection() -> psycopg2.extensions.connection:
    """Open a connection to the Postgres warehouse database."""
    config = get_config()
    return psycopg2.connect(
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        password=config.postgres.password,
        dbname=config.postgres.database,
    )


# --------------------------------------------------------------
# Connection Pooling
# --------------------------------------------------------------
_pg_pool: Optional[PgPool] = None


def get_pg_connection_pool() -> PgPool:
    """Get or create PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None:
        config = get_config()
        _pg_pool = cast(
            PgPool,
            PgPool(
                minconn=1,
                maxconn=5,
                host=config.postgres.host,
                port=config.postgres.port,
                user=config.postgres.user,
                password=config.postgres.password,
                dbname=config.postgres.database,
            ),
        )
    return _pg_pool


def release_pg_connection(conn: psycopg2.extensions.connection) -> None:
    """Release a PostgreSQL connection back to the pool."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.putconn(conn)


# ---------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------


def retry(
    func: Optional[F] = None,
    *,
    max_attempts: Optional[int] = None,
    backoff_seconds: Optional[int] = None,
    exceptions: Optional[Tuple[Type[Exception], ...]] = None,
) -> F:
    """
    Retry a function on transient failures with linear backoff.
    Configuration can be overridden via kwargs or sourced from global config.

    Args:
        func: The function to decorate
        max_attempts: Override max retry attempts (default from config)
        backoff_seconds: Override backoff seconds (default from config)
        exceptions: Override retryable exceptions (default from config)

    Returns:
        Decorated function with retry logic
    """
    if func is not None:
        # Called as @retry without parentheses
        return _make_retry_decorator(func, max_attempts, backoff_seconds, exceptions)  # type: ignore

    # Called as @retry(max_attempts=5, ...)
    def decorator(f: F) -> F:
        return _make_retry_decorator(f, max_attempts, backoff_seconds, exceptions)  # type: ignore

    return decorator  # type: ignore


def _resolve(override: Optional[Any], default: Any) -> Any:
    """Resolve a value, using override if provided, otherwise default."""
    return override if override is not None else default


def _make_retry_decorator(
    func: F,
    max_attempts: Optional[int],
    backoff_seconds: Optional[int],
    exceptions: Optional[Tuple[Type[Exception], ...]],
) -> F:
    """Create the actual retry wrapper function."""
    config = get_config()
    actual_max = _resolve(max_attempts, config.retry.max_attempts)
    actual_backoff = _resolve(backoff_seconds, config.retry.backoff_seconds)
    actual_exceptions = _resolve(exceptions, config.retry.retryable_exceptions)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(1, actual_max + 1):
            try:
                return func(*args, **kwargs)
            except actual_exceptions as exc:
                last_exc = exc
                if attempt == actual_max:
                    logger.error(
                        "%s failed after %d attempts: %s",
                        func.__name__,
                        actual_max,
                        exc,
                    )
                    raise
                wait = actual_backoff * attempt
                logger.warning(
                    "%s failed (attempt %d/%d): %s -- retrying in %ds",
                    func.__name__,
                    attempt,
                    actual_max,
                    exc,
                    wait,
                )
                time.sleep(wait)
        raise last_exc  # pragma: no cover - unreachable safeguard

    return wrapper  # type: ignore


# ---------------------------------------------------------------
# Audit helpers (etl.batch / etl.load_log / etl.dq_results)
# ---------------------------------------------------------------
def start_batch(pg_conn: psycopg2.extensions.connection) -> int:
    """Insert a new etl.batch row and return its batch_id."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO etl.batch (status) VALUES ('running') RETURNING batch_id;"
        )
        batch_id = cur.fetchone()[0]
    pg_conn.commit()
    logger.info("Started batch %s", batch_id)
    return batch_id


def finish_batch(
    pg_conn: psycopg2.extensions.connection, batch_id: int, status: str
) -> None:
    """Update etl.batch row with final status."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl.batch
            SET status = %s, finished_at = now()
            WHERE batch_id = %s;
            """,
            (status, batch_id),
        )
    pg_conn.commit()
    logger.info("Finished batch %s: %s", batch_id, status)


def start_step(
    pg_conn: psycopg2.extensions.connection, batch_id: int, step_name: str
) -> int:
    """Insert a 'running' etl.load_log row and return its log_id."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl.load_log (batch_id, step_name, status)
            VALUES (%s, %s, 'running')
            RETURNING log_id;
            """,
            (batch_id, step_name),
        )
        log_id = cur.fetchone()[0]
    pg_conn.commit()
    return log_id


def finish_step(
    pg_conn: psycopg2.extensions.connection,
    log_id: int,
    status: str,
    row_count: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update etl.load_log row with final status."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl.load_log
            SET status = %s, row_count = %s, finished_at = now(), error_message = %s
            WHERE log_id = %s;
            """,
            (status, row_count, error_message, log_id),
        )
    pg_conn.commit()


def run_step(
    audit_conn: psycopg2.extensions.connection,
    batch_id: int,
    step_name: str,
    func: Callable[..., int],
    *args: Any,
    **kwargs: Any,
) -> int:
    """
    Run `func(*args, **kwargs)` as an audited step: logs start/finish
    to etl.load_log, records the row count `func` returns, and
    re-raises any exception after logging it as a failure.

    `audit_conn` is the connection used for the etl.load_log writes
    themselves; it's kept out of `func`'s kwargs (which may need
    their own `pg_conn`, `mysql_conn`, etc.) to avoid a name clash.

    Args:
        audit_conn: Connection for audit logging
        batch_id: Current batch ID
        step_name: Name of the step being executed
        func: Function to execute (must return int row count)
        *args: Arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Row count returned by func

    Raises:
        Exception: Re-raises any exception from func after logging
    """
    log_id = start_step(audit_conn, batch_id, step_name)
    logger.info("Step '%s' starting", step_name)
    try:
        row_count = func(*args, **kwargs)
        finish_step(audit_conn, log_id, "success", row_count=row_count)
        logger.info("Step '%s' succeeded (%s rows)", step_name, row_count)
        return row_count
    except Exception as exc:
        finish_step(audit_conn, log_id, "failed", error_message=str(exc))
        logger.error("Step '%s' failed: %s", step_name, exc)
        raise


def record_dq_result(
    pg_conn: psycopg2.extensions.connection,
    batch_id: int,
    check_name: str,
    passed: bool,
    severity: str = "critical",
    details: Optional[str] = None,
) -> None:
    """Record a data quality check result to etl.dq_results."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl.dq_results (batch_id, check_name, status, severity, details)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (batch_id, check_name, "pass" if passed else "fail", severity, details),
        )
    pg_conn.commit()
