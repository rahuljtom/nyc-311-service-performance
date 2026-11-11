# NYC 311: where is housing-repair capacity worth adding?

3.4 million New York City 311 requests from 2024, cleaned and analysed in SQL (DuckDB), ending in one decision.

**[Read the one-page decision brief](https://rahuljtom.github.io/nyc-311-service-performance/)**

![Recommendation and headline numbers](docs/img/decision.jpg)

## The answer

> **Fix the process behind the five biggest housing-maintenance complaint types** (unsanitary condition, plumbing, paint/plaster,
> door/window, water leak). Do not spend on borough or ZIP targeting, or on changing how people contact 311.

## Why

| Question | Finding |
|---|---|
| How many requests are slow? | **19.4%** (665,424 of 3,428,219) were not closed within 7 days. |
| Who holds them? | The housing agency (HPD) holds **40.8%**; its five types alone hold **29.0%**. |
| What explains slowness? | Complaint type: **52%** of the variation, scored on data not used to fit it. Borough 0.3%, month 0.1%, ZIP 2.7%. |
| What would help most? | A quarter off the slow rate of the five types recovers about **48,200** requests with 5 targets. Fixing every slow borough-and-type cell recovers 27,500 but needs 118 targets. |
| Do poorer or hotter neighbourhoods wait longer? | Not once complaint mix is allowed for: gaps are within 2.5 points, in both directions. |
| How long is the tail? | 37% of HPD requests are still open at 7 days, 12% at 30, 3.6% at 89 (survival analysis). |

![How long requests stay open](docs/img/survival.jpg)
![What each option recovers](docs/img/options.jpg)

## The messy part

The data looks tidy and is not. Seven problems were found and counted before any result was trusted ([`r18_data_mess.csv`](outputs/tables/r18_data_mess.csv)). The one that changes the answer:

- **27,563 requests are marked Closed with no close date**, 27,553 of them Homeless Services. Counted as still open they inflate slow requests by 4% and make that agency look 3.8 times worse than it is. They are now treated as unknown and left out.
- 988 close dates earlier than creation (excluded, not repaired), 34,346 malformed ZIPs and 2,638 unspecified boroughs (left empty, not guessed), 35,632 requests genuinely still open (handled as censored).

## Method

- **Pipeline:** daily API pulls → raw text → typed, de-duplicated DuckDB tables → 18 numbered SQL files → result tables → the brief.
- **SQL used:** window functions, Kaplan-Meier survival curves, out-of-sample variance decomposition, expected-versus-actual standardisation joined to a second source (NYC Health Department heat index by ZIP), recoverable-effort sizing with a chance margin.
- **Checks:** 27 tests on hand-computed answers with a regression test for each mistake found; 29 headline numbers recomputed independently in pandas; SQL lint and tests on every push.

## Sources

NYC Open Data 311 Service Requests (`erm2-nwe9`), 2024, pulled 7 November 2026; NYC Health Department Heat Vulnerability Index (`4mhf-duep`). Raw data is not committed.

## Limits

One year, one city. "Closed" is an agency decision, so slow closure may mean enforcement rather than capacity. Seven days is an arbitrary yardstick (some types are slow by design). Findings are associations; the recovered-requests figure is a scenario, not a forecast.

## Reproduce

```bash
make setup && make download   # about an hour, resumable
make run site check audit
```

Details: [methodology](docs/methodology.md) · [data dictionary](docs/data_dictionary.md)
