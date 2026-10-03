"""
Unit tests for pure-Python logic: the retry decorator, the staging
table config, and the dim_date row generator. None of these need a
live MySQL/Postgres connection.
"""

import datetime

import pytest

from etl.extract_load_staging import _coerce_value, _load_staging_table
from etl.transform_load_mart import generate_date_rows
from etl.utils import retry, get_config


# ---------------------------------------------------------------
# retry decorator
# ---------------------------------------------------------------

def test_retry_succeeds_without_retrying_when_no_error():
    calls = {"count": 0}

    @retry(max_attempts=3, backoff_seconds=0)
    def always_works():
        calls["count"] += 1
        return "ok"

    assert always_works() == "ok"
    assert calls["count"] == 1


def test_retry_recovers_after_transient_failures():
    calls = {"count": 0}

    @retry(max_attempts=3, backoff_seconds=0)
    def fails_twice_then_succeeds():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ConnectionError("transient")
        return "ok"

    assert fails_twice_then_succeeds() == "ok"
    assert calls["count"] == 3


def test_retry_raises_after_exhausting_attempts():
    calls = {"count": 0}

    @retry(max_attempts=2, backoff_seconds=0)
    def always_fails():
        calls["count"] += 1
        raise ConnectionError("still broken")

    with pytest.raises(ConnectionError):
        always_fails()
    assert calls["count"] == 2


def test_retry_only_catches_specified_exceptions():
    @retry(max_attempts=3, backoff_seconds=0, exceptions=(ConnectionError,))
    def raises_value_error():
        raise ValueError("not a transient error")

    with pytest.raises(ValueError):
        raises_value_error()


# ---------------------------------------------------------------
# Staging config consistency (from YAML)
# ---------------------------------------------------------------

def test_staging_config_has_query_and_columns_for_every_table():
    staging_config = get_config().staging_config
    for table_name, config in staging_config.items():
        assert "query" in config, f"{table_name} missing 'query'"
        assert "columns" in config, f"{table_name} missing 'columns'"
        assert len(config["columns"]) > 0, f"{table_name} has no columns"


def test_staging_config_columns_have_no_duplicates():
    staging_config = get_config().staging_config
    for table_name, config in staging_config.items():
        columns = config["columns"]
        assert len(columns) == len(set(columns)), (
            f"{table_name} has duplicate columns: {columns}"
        )


def test_staging_config_queries_reference_every_declared_column():
    # Rough smoke check: every declared column name should appear
    # somewhere in the query text (as a bare word or after AS).
    staging_config = get_config().staging_config
    for table_name, config in staging_config.items():
        query_lower = config["query"].lower()
        for col in config["columns"]:
            assert col.lower() in query_lower, (
                f"{table_name}: column '{col}' not found in its query"
            )


# ---------------------------------------------------------------
# generate_date_rows
# ---------------------------------------------------------------

def test_generate_date_rows_covers_full_inclusive_range():
    start = datetime.date(2005, 5, 24)
    end = datetime.date(2005, 5, 26)
    rows = generate_date_rows(start, end)
    assert len(rows) == 3
    date_keys = [row[0] for row in rows]
    assert date_keys == [20050524, 20050525, 20050526]


def test_generate_date_rows_single_day():
    day = datetime.date(2005, 1, 1)
    rows = generate_date_rows(day, day)
    assert len(rows) == 1
    date_key, full_date, year, quarter, month, month_name, dom, day_name, week, is_weekend = rows[0]
    assert date_key == 20050101
    assert full_date == day
    assert year == 2005
    assert quarter == 1
    assert month == 1
    assert dom == 1

def test_generate_date_rows_flags_weekends_correctly():
    # 2026-07-25 is a Saturday
    saturday = datetime.date(2026, 7, 25)
    rows = generate_date_rows(saturday, saturday)
    is_weekend = rows[0][-1]
    assert is_weekend is True

    # 2026-07-27 is a Monday
    monday = datetime.date(2026, 7, 27)
    rows = generate_date_rows(monday, monday)
    is_weekend = rows[0][-1]
    assert is_weekend is False


def test_generate_date_rows_quarter_boundaries():
    q1_end = datetime.date(2005, 3, 31)
    q2_start = datetime.date(2005, 4, 1)
    rows = generate_date_rows(q1_end, q2_start)
    quarters = [row[3] for row in rows]
    assert quarters == [1, 2]


# ---------------------------------------------------------------
# bool_columns coercion (MySQL 0/1 int -> Postgres boolean)
# ---------------------------------------------------------------

def test_coerce_value_converts_int_to_bool_for_bool_columns():
    assert _coerce_value("active", 1, {"active"}) is True
    assert _coerce_value("active", 0, {"active"}) is False


def test_coerce_value_leaves_non_bool_columns_untouched():
    assert _coerce_value("customer_id", 1, {"active"}) == 1
    assert _coerce_value("customer_id", 0, {"active"}) == 0


def test_coerce_value_passes_through_none():
    assert _coerce_value("active", None, {"active"}) is None


def test_customer_and_staff_configs_declare_active_as_bool_column():
    staging_config = get_config().staging_config
    assert "active" in staging_config["customer"].get("bool_columns", [])
    assert "active" in staging_config["staff"].get("bool_columns", [])


class _FakeCursor:
    """Minimal cursor stand-in that records executed SQL/params."""

    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True


def test_load_staging_table_sends_real_bools_not_ints(monkeypatch):
    captured = {}

    def fake_execute_values(cur, sql, values):
        captured["values"] = values

    monkeypatch.setattr(
        "etl.extract_load_staging.execute_values", fake_execute_values
    )

    conn = _FakeConn()
    rows = [{"customer_id": 1, "active": 1}, {"customer_id": 2, "active": 0}]
    # Create a generator that yields a single batch of rows
    row_generator = (batch for batch in [rows])
    _load_staging_table(
        conn, "staging.customer", ["customer_id", "active"], row_generator,
        bool_columns=["active"],
    )

    active_values = [row[1] for row in captured["values"]]
    assert active_values == [True, False]
    assert all(isinstance(v, bool) for v in active_values)
