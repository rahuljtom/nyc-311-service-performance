# Methodology

## Question

Where is New York City's 311 service slowest to close requests, which complaint types and agencies account for most of the slow
requests, and is anything getting worse during 2024?

## Pipeline

1. `src/download.py` fetches each creation day separately (one small query per day; large sorted, paged queries were
   rejected with server errors) and saves one CSV per day. Reruns skip days already on disk.
2. `sql/01_staging.sql` reads every column as text, types it with `try_cast`, removes duplicate keys and derives the fields in the
   data dictionary. The extract date is the latest close date in the file.
3. `sql/02_data_quality.sql` counts every exclusion and oddity.
4. `sql/03` to `sql/11` build the result tables. `src/pipeline.py` runs them in order inside DuckDB and exports each to CSV.
5. `tests/` runs the real SQL on a small dataset whose answers were worked out by hand, including regression tests for the
   mistakes found while reviewing real results (see below).
6. `scripts/audit_headlines.py` recomputes 20 headline numbers from the raw CSVs in pandas and fails if any differs.

## Choices that change results

- **Open requests count as not closed.** Shares closed within 7 or 30 days use all observable requests, open ones included, so
  slow cases are never missing from the denominator. Median and 90th-percentile hours use closed requests only and are
  therefore optimistic.
- **"Slow" means not closed within 7 days.** An arbitrary yardstick: some request types are slow by design (new tree requests).
  It shows where time goes, not who is failing.
- **Cohorts, not a running backlog.** Each month's requests are followed on their own. A running count of open requests grows all
  year simply because the file starts empty on 1 January.
- **Like-for-like baselines.** A borough is compared with the citywide median for the same agency and complaint type, computed on
  the same rows (requests with a borough).
- **Channel compared with its own mix.** Channels receive different complaint types, so the actual closed-in-7-days rate is
  compared with the rate expected if every complaint type closed at its citywide rate.
- **Small cells are not shown.** Agencies and ZIPs below 1,000 and 500 observable requests, and borough cells below 200 closed
  requests, are left out.

## Mistakes caught during review (each now has a test)

- The first backlog table grew all year; this was the empty start of the file, not a worsening backlog.
- A borough baseline that mixed agencies reported a 211-fold gap for DHS Encampment; the correct figure is 7.9-fold.
- The same baseline included requests with no borough while the borough figures excluded them.
