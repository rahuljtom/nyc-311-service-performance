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
| `observable_7d`, `observable_30d` | The request is at least 7 (30) days older than the extract date and has a valid close date, or is open. Only these requests are judged on a 7 (30) day target. |
| `closed_within_7d`, `closed_within_30d` | Closed within 7 (30) days of creation. Open requests count as not closed. |

## Result tables (`outputs/tables/`)

`r02_data_quality`, `r03_monthly_volume`, `r04_agency_performance`, `r05_complaint_pareto`, `r06_backlog` (one row per creation
month cohort), `r07_due_date_misses`, `r08_borough_gaps`, `r09_channel_mix`, `r10_slow_request_pareto`, `r11_zip_deciles`.
