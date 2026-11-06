-- Follow each month's requests (the cohort created in that month) instead of a running backlog. A running count of open
-- requests grows all year simply because the file starts empty on 1 January, which would read as a worsening backlog.
-- Per cohort: how many were still open at the end of their own month, and what share closed within 30 days (counted only for
-- requests old enough at the extract date to have had 30 days). Open requests count as not closed.
create or replace table r06_backlog as
select
    date_trunc('month', created_at)::date as created_month,
    count(*) as requests_created,
    count(*) filter (
        where closed_at is null or closed_at >= date_trunc('month', created_at) + interval 1 month
    ) as open_at_end_of_month,
    round(100.0 * count(*) filter (
        where closed_at is null or closed_at >= date_trunc('month', created_at) + interval 1 month
    ) / count(*), 1) as pct_open_at_end_of_month,
    round(100.0 * avg(closed_within_30d::int) filter (where observable_30d), 1) as pct_closed_within_30d,
    round(100.0 * count(*) filter (where closed_at is null) / count(*), 1) as pct_still_open_at_extract
from requests
group by 1
order by 1;
