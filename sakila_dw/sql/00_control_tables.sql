-- ============================================================
-- 00_control_tables.sql
-- ETL metadata: run log and data-quality check results.
-- Run this first, before any staging/mart DDL.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS etl;

-- One row per pipeline execution.
CREATE TABLE IF NOT EXISTS etl.batch (
    batch_id     BIGSERIAL PRIMARY KEY,
    started_at   TIMESTAMP NOT NULL DEFAULT now(),
    finished_at  TIMESTAMP,
    status       TEXT NOT NULL DEFAULT 'running'  -- running | success | failed
        CHECK (status IN ('running', 'success', 'failed'))
);

-- One row per step per batch (extract, transform, load, etc.).
CREATE TABLE IF NOT EXISTS etl.load_log (
    log_id        BIGSERIAL PRIMARY KEY,
    batch_id      BIGINT NOT NULL REFERENCES etl.batch(batch_id),
    step_name     TEXT NOT NULL,
    status        TEXT NOT NULL
        CHECK (status IN ('running', 'success', 'failed')),
    row_count     BIGINT,
    started_at    TIMESTAMP NOT NULL DEFAULT now(),
    finished_at   TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_load_log_batch ON etl.load_log(batch_id);

-- One row per data-quality check per batch.
CREATE TABLE IF NOT EXISTS etl.dq_results (
    dq_id        BIGSERIAL PRIMARY KEY,
    batch_id     BIGINT NOT NULL REFERENCES etl.batch(batch_id),
    check_name   TEXT NOT NULL,
    status       TEXT NOT NULL
        CHECK (status IN ('pass', 'fail')),
    severity     TEXT NOT NULL DEFAULT 'critical'
        CHECK (severity IN ('critical', 'warning')),
    details      TEXT,
    checked_at   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dq_results_batch ON etl.dq_results(batch_id);
