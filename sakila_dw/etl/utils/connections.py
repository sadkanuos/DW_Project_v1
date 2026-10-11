"""Database connections and connection pooling."""

from enum import auto
from typing import Optional, cast

import psycopg2
import psycopg2.extensions
from psycopg2.pool import SimpleConnectionPool as PgPool
import pymysql
import pymysql.connections

from etl.utils.config_helpers import get_config


def get_mysql_connection() -> pymysql.connections.Connection:
    """Open a connection to the Sakila source database"""
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
    """Open a connection to the Postgres warehouse database"""
    config = get_config()
    return psycopg2.connect(
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        password=config.postgres.password,
        dbname=config.postgres.database,
    )


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
