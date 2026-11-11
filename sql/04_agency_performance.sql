-- Agency scorecard. Share closed in 7 days counts requests still open as misses, so it is not biased by
-- slow cases being missing. Median and p90 hours use closed requests only and are therefore optimistic.
-- Agencies with fewer than 1,000 observable requests are left out (too few to compare).
create or replace table r04_agency_performance as
select
    agency,
    count(*) as requests,
    round(100.0 * count(closed_at) / count(*), 1) as closed_pct,
    round(100.0 * avg(closed_within_7d::int), 1) as closed_within_7d_pct,
    round(quantile_cont(resolution_hours, 0.5), 1) as median_hours_closed,
    round(quantile_cont(resolution_hours, 0.9), 1) as p90_hours_closed
from requests
where observable_7d
group by agency
having count(*) >= 1000
order by requests desc, agency asc;
