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
4. `sql/03` to `sql/18` build the result tables (`sql/12` loads the ZIP-level reference table from `data/reference/`). `src/pipeline.py` runs them in order inside DuckDB and exports each to CSV.
5. `tests/` runs the real SQL on a small dataset whose answers were worked out by hand, including regression tests for the
   mistakes found while reviewing real results (see below).
6. `src/build_site.py` turns the result tables into the one-page decision write-up in `docs/index.html`; every number in its text is computed from the tables.
7. `scripts/audit_headlines.py` recomputes 29 headline numbers from the raw CSVs in pandas and fails if any differs.

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

- **Closed with no close date is unknown, not slow.** 27,563 requests (27,553 of them DHS) are marked CLOSED without a close date.
  They are left out of every closure measure and out of the survival curves. Counting them as open would add 27,563 slow
  requests and make DHS's slow rate read 3.8 times too high.
- **Survival curves handle open requests properly.** `sql/13` computes a Kaplan-Meier curve per agency and per HPD complaint type:
  a request still open at the extract date is censored at its age, so it is neither dropped nor counted as finished.
- **What explains "slow".** `sql/14` predicts slow/not slow from each set of facts using group rates fitted on even keys and scored
  on odd keys, and reports the share of squared error removed. Fitting and scoring on separate halves stops many small groups
  from flattering a predictor.
- **Neighbourhood comparison.** `sql/15` joins ZIP to the NYC Health Department Heat Vulnerability Index (1 to 5). The expected slow
  rate for a group is the average of each request's citywide rate for its complaint type (and, separately, for its type in its own
  borough); the margin is 1.96 times the standard error of actual minus expected.
- **Recoverable slow requests.** `sql/16` counts slow requests above the citywide rate for the same complaint type minus a 95%
  chance margin, so noise in small cells is not counted. Option C (a quarter off the five biggest HPD types) is a scenario, not a
  forecast. The index is a published composite that includes income and race; it is used as a grouping only, never as an explanation.

## Mistakes caught during review (each now has a test)

- The first backlog table grew all year; this was the empty start of the file, not a worsening backlog.
- A borough baseline that mixed agencies reported a 211-fold gap for DHS Encampment; the correct figure is 7.9-fold.
- The same baseline included requests with no borough while the borough figures excluded them.
- Requests marked closed without a close date were counted as slow, inflating the slow total by 4% and DHS's rate 3.8 times. Found when the new decision write-up asked who the worst agency really was; covered by `tests/test_decision_queries.py`.
- Tied rows came out in a different order on each run; every final `ORDER BY` now has explicit tie-breakers and the outputs are identical across runs.
