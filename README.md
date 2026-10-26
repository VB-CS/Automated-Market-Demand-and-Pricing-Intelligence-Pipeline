# Automated Market Demand and Pricing Intelligence Pipeline

A Python ETL pipeline that collects Google Shopping prices for a small basket of DDR5 RAM products, validates and normalizes the returned listings, and loads clean observations into PostgreSQL for market-trend analysis.

The business goal is to replace repeated manual price checks with a repeatable data-collection process. Once observations are stored over time, SQL analysis can summarize prices by period and surface week-over-week changes.

## Pipeline architecture

```text
SerpApi / Google Shopping
          │
          ▼
  1. Extract listings
          │
          ▼
  2. Transform and validate
     • Skip missing titles or prices
     • Parse prices into numeric values
     • Apply a minimum-price floor
     • Normalize product identifiers
     • Remove duplicate title/price pairs within a run
          │
          ▼
  3. Load into PostgreSQL
     • Parameterized batch insert
     • Commit on success; rollback on failure
          │
          ▼
  SQL analytics: CTE aggregation → LAG comparison
```

### 1. Extract

`market_tracker.py` uses the SerpApi Python client with the Google Shopping engine to request listings for three configured DDR5 RAM products. The current script specifies Austin, Texas as the search location. API credentials are read from environment variables rather than being hard-coded into the source.

### 2. Transform and validate

The script applies guard clauses before writing data:

- Skip listings without a product title or price.
- Parse price strings into numeric values and skip unparseable values.
- Apply `MIN_PRICE_FLOOR` to remove low-priced accessories and likely outliers from the target basket.
- Create a normalized product identifier for grouping.
- Use an in-memory `(normalized_title, price)` fingerprint to avoid duplicate pairs within the current run.

This makes the data written to the database more consistent, but the in-memory deduplication set resets on each execution; it does not deduplicate observations across separate runs.

### 3. Load

The pipeline connects to PostgreSQL using `psycopg2` and uses a parameterized `executemany` insert into `market_pricing`. Parameterized SQL avoids building an insert statement by concatenating listing data. The script commits a successful batch, attempts a rollback if the transaction fails, and closes the cursor and connection in the cleanup path.

The ingestion script explicitly inserts `display_title`, `normalized_title`, and `price`. The database table/schema is maintained separately from this repository, so confirm its full definition before relying on fields not shown in the Python insert.

## Analytical design: aggregate before `LAG`

The pricing analysis uses a common sequence:

1. **Aggregate raw observations to the analysis grain** (for example, one average price per normalized product per week) in a common table expression (CTE).
2. **Apply `LAG` to that aggregated result**, partitioning by product and ordering by the period.
3. Calculate the difference from the prior period and, when useful, the percentage change.

The reason for this order is data grain. A raw listing table can contain multiple observations for the same product and period. Applying `LAG` directly to those rows can compare one listing with another listing rather than comparing period-level metrics. Aggregating first gives the window function one row per product-period to compare.

### Illustrative PostgreSQL query

> **Schema check before using this example:** `market_tracker.py` does not name a timestamp column in its `INSERT`. This example assumes the `market_pricing` table has a capture timestamp called `captured_at` (for example, supplied by a database default). Replace that identifier with the actual timestamp field in your schema. The query is an example of the aggregation-then-window pattern, not a verified copy of a production query.

```sql
WITH weekly_prices AS (
    SELECT
        normalized_title,
        DATE_TRUNC('week', captured_at)::date AS week_start,
        AVG(price)::numeric(12, 2) AS avg_weekly_price,
        COUNT(*) AS observation_count
    FROM market_pricing
    GROUP BY
        normalized_title,
        DATE_TRUNC('week', captured_at)::date
),
week_over_week AS (
    SELECT
        normalized_title,
        week_start,
        avg_weekly_price,
        observation_count,
        LAG(avg_weekly_price) OVER (
            PARTITION BY normalized_title
            ORDER BY week_start
        ) AS prior_week_avg
    FROM weekly_prices
)
SELECT
    normalized_title,
    week_start,
    avg_weekly_price,
    prior_week_avg,
    ROUND(avg_weekly_price - prior_week_avg, 2) AS price_delta,
    ROUND(
        100.0 * (avg_weekly_price - prior_week_avg)
        / NULLIF(prior_week_avg, 0),
        2
    ) AS percent_change,
    observation_count
FROM week_over_week
ORDER BY normalized_title, week_start;
```

## Scheduling and operational limitation

The current workflow is intended to run on a local CRON schedule. CRON is external to `market_tracker.py`; the repository does not currently contain a portable scheduler configuration. A local scheduled run depends on the host being available and the required environment variables being present when the job starts. A planned improvement is to move execution to a managed cloud scheduler and hosted worker so runs are not tied to a personal machine.

## Tech stack

- **Language:** Python
- **Collection:** SerpApi Google Shopping engine
- **Data transformation:** guard-clause validation, numeric normalization, in-memory deduplication
- **Database:** PostgreSQL
- **Database access:** `psycopg2`
- **Environment configuration:** `python-dotenv`
- **Scheduling direction:** local CRON now; managed cloud scheduling planned

## Configuration and running

Set the following values in your local environment or an untracked `.env` file:

| Variable | Purpose |
|---|---|
| `API_KEY` or `SERPAPI_API_KEY` | SerpApi credential; the script checks `API_KEY` first |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password (defaults to an empty string in the script) |
| `DB_HOST` | Database host (defaults to `localhost`) |
| `DB_PORT` | Database port (defaults to `5432`) |

Ensure the required Python packages are installed, PostgreSQL is reachable, and the `market_pricing` table exists with the columns expected by the insert. Then run:

```bash
python market_tracker.py
```

Do not commit API keys, database passwords, or a real `.env` file. Use `.env.example` with placeholder values if you want to document configuration.

## Architecture decisions

The project's existing ADR documents are maintained in Notion and are being migrated into this repository. After adding the original ADR Markdown export at the path below, this link will document the in-memory duplicate-fingerprinting decision:

- [ADR-001: In-memory attribute fingerprinting](docs/ADR-001-in-memory-attribute-fingerprinting.md)

## Current scope and limitations

- The target basket and location are configured in the script rather than supplied through command-line arguments or a configuration file.
- The minimum-price floor is a heuristic and may need adjustment for different products or markets.
- Deduplication is in memory for one run only.
- A reliable historical trend analysis requires a timestamp or period field in the database schema; verify that field and its default before using the weekly query above.
- Scheduling and database DDL are not currently defined in this repository.
