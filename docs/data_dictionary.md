# Data dictionary

## Source

NYC Open Data, "311 Service Requests from 2010 to Present" (`erm2-nwe9`), pulled through the public Socrata API one
creation day at a time. Extract: 7 November 2026, requests created 1 January to 31 December 2024. The latest close date in the
file (4 November 2026) is used as the extract date. The raw files (about 416 MB) are not committed; `make download` recreates them.
The same dataset keeps changing as requests close, so a later pull can give slightly different figures.

## Columns used

| Column | Meaning | Cleaning |
|---|---|---|
| `unique_key` | Request id | Duplicates keep the earliest row (none found). |
| `created_date`, `closed_date`, `due_date` | Timestamps | Unparseable values become NULL. A close date before the create date is kept out of every duration. |
| `agency` | Responsible agency code | Upper-cased and trimmed. |
| `complaint_type` | Category chosen at intake | Trimmed. Some types are handled by more than one agency (for example Encampment: DHS and NYPD), so analysis uses agency and type together. |
| `borough` | Borough | Only the five boroughs are kept; "Unspecified" becomes NULL. |
| `incident_zip` | ZIP | Kept only when it starts with five digits. |
| `status`, `open_data_channel_type` | Request status and intake channel | Upper-cased. |

## Derived fields (`requests` table)

| Field | Definition |
|---|---|
| `resolution_hours` | Hours from creation to close; NULL if open or if the close date is earlier than the create date. |
| `observable_7d`, `observable_30d` | The request is at least 7 (30) days older than the extract date and has a valid close date or is open, and is not `close_unknown`. Only these requests are judged on a 7 (30) day target. |
| `close_unknown` | Status is CLOSED but there is no close date. Excluded from every closure measure and from the survival curves. |
| `closed_within_7d`, `closed_within_30d` | Closed within 7 (30) days of creation. Open requests count as not closed. |

## Result tables (`outputs/tables/`)

`r02_data_quality`, `r03_monthly_volume`, `r04_agency_performance`, `r05_complaint_pareto`, `r06_backlog` (one row per creation
month cohort), `r07_due_date_misses`, `r08_borough_gaps`, `r09_channel_mix`, `r10_slow_request_pareto`, `r11_zip_deciles`.

| Table | Columns that need explaining |
|---|---|
| `r13_survival_curves` | `pct_still_open` = Kaplan-Meier share of requests still open after `days_since_created` days; `n_at_risk` requests observed at least that long; `closed` events that day. Days with no closures are skipped (the curve is flat). |
| `r14_slow_drivers` | `pct_of_variation_explained` out of sample (fit on even keys, score on odd keys); `groups_fitted` distinct groups. |
| `r15_vulnerability_gap` | Per Heat Vulnerability Index group: `gap_pp` = actual slow rate minus rate expected from complaint type; `gap_within_borough_pp` expected from type in the same borough; `*_margin_pp` = 95% margin. |
| `r16_levers`, `r16_recoverable_cells` | Slow requests above the citywide rate for the same complaint type, minus a 95% chance margin; `targets` = number of cells to act on. Lever C is a scenario. |
| `r17_hpd_descriptors` | Up to four descriptors per top slow HPD complaint type. |
| `r18_data_mess` | Each data problem with its row count, what was done and what would have happened if ignored. |

Reference input: `data/reference/hvi_zcta.csv` (ZIP to Heat Vulnerability Index, from NYC Open Data dataset 4mhf-duep, downloaded by `src/download_reference.py`).
