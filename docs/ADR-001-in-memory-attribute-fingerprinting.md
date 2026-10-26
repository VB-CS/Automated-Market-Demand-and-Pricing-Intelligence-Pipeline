## 1. Context & Problem Statement

- **Background:** The 3-layer Python ETL pipeline ingests live market pricing for DDR5 RAM listings harvested via SerpAPI prior to database commitment.
- **Problem:** Vendor listings lack standardized MPNs (Manufacturer Part Numbers) and exhibit raw string variations (e.g., spacing, casing, brand abbreviations), causing duplicate record insertions during automated ingestion.
- **Scope:** Data hygiene, database write efficiency, and downstream SQL window function (`LAG`) accuracy.
- **Constraints:** Deduplication must occur prior to PostgreSQL writes to prevent unnecessary database transactions and lock overhead.

---

## 2. Options Considered

### Option A: PostgreSQL DB Constraints (`ON CONFLICT DO NOTHING`)

- **Description:** Rely on unique composite keys on the PostgreSQL table level to drop duplicates upon `INSERT`
- **Pros:** Simple implementation with zero application-side state tracking.
- **Cons:** High database write overhead; fails on minor string mismatches (e.g., "16GB DDR5" vs. "16 GB DDR5").
- **Performance Trade-offs:** Increased database CPU utilization during batch commits.

### Option B: Application-Side In-Memory Fingerprinting (Chosen)

- **Description:** Normalize string attributes (brand, capacity, speed, CAS latency) into a deterministic canonical hash string stored in-memory during execution.
- **Pros:** Filters unneeded payload items in microseconds before opening a database connection; handles minor string variance through normalization rules.
- **Cons:** Requires in-memory state management during pipeline runs.
- **Performance Trade-offs:** Negligible RAM footprint in Python in exchange for substantial reduction in DB IOPS.

---

## 3. Decision & Technical Rationale

**Chosen Option:** Option B (Application-Side In-Memory Fingerprinting).

- Normalizing and fingerprinting listings in Python memory before writing to PostgreSQL protects database integrity. Preventing duplicate record insertions ensures that downstream SQL queries using `LAG` window functions compute accurate week-over-week price deltas rather than zero-delta intra-day duplicates.

---

## 4. Consequences & Trade-offs

### ✅ Positive System Impacts

- Reduced database write load and clean longitudinal pricing trends.

### ⚠️ Potential Failure Points

- Overly aggressive normalization could accidentally collapse two distinctly spec'd SKUs into the same hash key.

### 🔧 Operational & Maintenance Costs

- Requires maintaining regex normalization rules when new vendor title structures are introduced.
