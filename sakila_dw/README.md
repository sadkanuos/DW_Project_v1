# Sakila → Postgres → Power BI: Data Warehouse

Extracts Sakila from MySQL, loads it into a Postgres `staging` schema,
transforms it into a star schema (`mart` schema), and connects Power BI
to `mart`. Includes an ETL control/audit layer, retry logic, and data
quality checks, with both a plain cron-friendly orchestrator and an
optional Airflow DAG.

## Architecture

```
MySQL (sakila)                 Postgres (sakila_dw)
┌──────────────┐  full refresh  ┌──────────────────┐   direct load   ┌──────────────────┐
│  OLTP tables │ ─────────────▶ │  staging.*        │ ─────────────▶ │  mart.*           │ ──▶ Power BI
│              │  (truncate +   │  (reloaded each   │  (dims + facts)│  (dims + facts)   │
│              │   reload)      │   run)            │                └──────────────────┘
└──────────────┘                └──────────────────┘                         │
                                                                               ▼
                                                                        etl.load_log
                                                                        etl.dq_results
```

## Project layout

```
sql/
  00_control_tables.sql       ETL metadata: run log, DQ results
  01_staging_ddl.sql          Staging tables
  02_mart_ddl.sql             Star schema: dims, bridge table, facts
etl/
  utils.py                    Connections, logging, retry decorator, audit helpers
  extract_load_staging.py     Full-refresh extract (truncate + reload)
  transform_load_mart.py      Dim loads (overwrite) + fact loads
  data_quality.py             Post-load checks (referential integrity)
orchestrate.py                 Entry point: runs one full batch end-to-end
airflow_dag.py                  Optional: same pipeline as an Airflow DAG
tests/
  test_transform_logic.py     Unit tests for pure-Python logic
requirements.txt
.env.example
```

## Setup

1. **Databases:** create the target Postgres database (e.g. `sakila_dw`).
2. **Run DDL, in order:**
   ```bash
   psql -h localhost -U postgres -d sakila_dw -f sql/00_control_tables.sql
   psql -h localhost -U postgres -d sakila_dw -f sql/01_staging_ddl.sql
   psql -h localhost -U postgres -d sakila_dw -f sql/02_mart_ddl.sql
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure:** `cp .env.example .env` and fill in real credentials.
5. **Run the pipeline:**
   ```bash
   python orchestrate.py
   ```
   Safe to run repeatedly — each run truncates and reloads staging and
   the mart tables from the current state of the source, so the result
   is always consistent with MySQL at the time of the run.

## Design decisions and why

**Full refresh extraction.**
Staging tables are truncated and reloaded from MySQL in full on every
run. The pipeline's output is always simply "the mart, freshly derived
from whatever MySQL has right now" — easy to reason about and easy to
trust.

**Overwrite dimensions.**
Every dimension (`dim_customer`, `dim_film`, `dim_store`, `dim_staff`,
`dim_category`) is loaded with one row per natural key, updated in
place when the underlying source row changes. Surrogate keys equal
the natural key (`customer_sk = customer_id`, etc.) since there is
never more than one row per natural key — this keeps joins simple
while still giving the mart a conventional dims + facts shape.

**`bridge_film_category` for many-to-many.**
A film can have more than one category in Sakila's schema.
`dim_film.primary_category` covers "just let me slice by one category"
for casual use; the bridge table supports correct many-to-many
analysis (e.g. category revenue without accidentally double-counting
films, if you set up the Power BI relationship correctly — see below).

**Two fact tables, not one.**
`fact_rental` (grain: rental) and `fact_payment` (grain: payment) are
separate because a single rental can have multiple payments (e.g. a
late fee charged after the fact), and payment-date-based analysis
("revenue recognized this month") needs its own date key independent
of when the rental itself started.

**Every step is audited.** `etl.load_log` gets a row per step per
batch (status, row counts, timing, error message if failed).
`etl.dq_results` gets a row per check per batch. If a run fails at
2am, you query these tables to see exactly which step failed and why
— no digging through log files on a server you may not have access to.

**Retry with backoff, not silent failure.** Transient issues (a
dropped connection, a lock timeout) are retried with linear backoff
via the `@retry` decorator before the pipeline gives up and marks the
step failed.

## Running tests

```bash
pytest tests/
```

These are unit tests for pure-Python logic (retry behavior, table
config consistency, date-dimension generation) that don't need a live
database. For true integration coverage of the SQL transform logic,
spin up disposable MySQL + Postgres containers, seed the Postgres one
with the DDL, run `orchestrate.py` against them, and assert on row
counts / specific table contents. A `docker-compose.yml` with a MySQL
Sakila image and a Postgres image is the natural next addition here
if you want that automated.

## Orchestration options

- **Cron / systemd timer:** just schedule `python orchestrate.py`.
  Exit code 0 = success, 1 = pipeline failure, 2 = a critical data
  quality check failed after an otherwise successful load — wire your
  monitoring to alert on non-zero.
- **Airflow:** drop `airflow_dag.py` into your DAGs folder. Gets you
  retries per task, email alerting, and a dependency graph for free.
  Update the `email` address in `default_args` first.

## Connecting Power BI

1. **Get Data → PostgreSQL database**, Import mode (Sakila-scale data
   doesn't need DirectQuery).
2. Select only the **mart** schema tables — not `staging` or `etl`,
   which are internal to the pipeline.
3. Relationships Power BI should build (verify/create in Model view):
   - `fact_rental[customer_sk] → dim_customer[customer_sk]`
   - `fact_rental[film_sk] → dim_film[film_sk]`
   - `fact_rental[store_sk] → dim_store[store_sk]`
   - `fact_rental[staff_sk] → dim_staff[staff_sk]`
   - `fact_rental[rental_date_key] → dim_date[date_key]`
   - `fact_payment[customer_sk] → dim_customer[customer_sk]`
   - `fact_payment[payment_date_key] → dim_date[date_key]`
   - `bridge_film_category[film_sk] → dim_film[film_sk]`,
     `bridge_film_category[category_id] → dim_category[category_id]`
     (for the bridge relationships, set cross-filter direction to
     "Both" on at least one side so category slicers filter the fact
     table correctly through the bridge)
4. Mark `dim_date` as a **Date Table** (Model view → right-click →
   Mark as date table → `full_date`) to enable time intelligence
   (YTD, MTD, etc.).
5. `dim_customer` and `dim_film` have one row per natural key, so they
   can be used directly for both the fact relationship *and* any
   standalone "pick a customer/film" slicer.

## Possible next steps

- `docker-compose.yml` with disposable MySQL/Postgres for integration testing
- Partition `fact_rental` by `rental_date_key` if/when it grows large (see comment in `02_mart_ddl.sql`)
- A `fact_inventory_snapshot` for stock/availability reporting, if that becomes a reporting need
- Great Expectations or dbt tests if the DQ layer needs to grow beyond hand-written SQL checks
