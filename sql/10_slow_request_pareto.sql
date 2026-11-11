-- Where are the requests that do not close within 7 days? Ranked by number of slow requests (volume x slow rate),
-- so a large type with a moderate slow rate can outrank a small type that is always slow.
create or replace table r10_slow_request_pareto as
with slow as (
    select
        agency,
        complaint_type,
        count(*) as requests,
        count(*) filter (where not closed_within_7d) as slow_requests
    from requests
    where observable_7d
    group by 1, 2
)

select
    row_number() over (order by slow_requests desc, complaint_type asc, agency asc) as slow_rank,
    agency,
    complaint_type,
    requests,
    slow_requests,
    round(100.0 * slow_requests / requests, 1) as slow_rate_pct,
    round(100.0 * slow_requests / sum(slow_requests) over (), 2) as pct_of_all_slow,
    round(
        100.0 * sum(slow_requests) over (order by slow_requests desc, complaint_type asc, agency asc rows between unbounded preceding and current row)
        / sum(slow_requests) over (),
        1
    ) as cumulative_pct_of_slow
from slow
order by slow_rank;
