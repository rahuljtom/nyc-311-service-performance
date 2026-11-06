-- ZIP codes ranked into deciles by slow-request rate (decile 1 = slowest). ZIPs with fewer than 500
-- observable requests are left out. Shows how much of the slow volume sits in the worst-performing tenth.
create or replace table r11_zip_deciles as
with by_zip as (
    select
        zip,
        count(*) as requests,
        count(*) filter (where not closed_within_7d) as slow_requests,
        round(100.0 * count(*) filter (where not closed_within_7d) / count(*), 1) as slow_rate_pct
    from requests
    where observable_7d and zip is not null
    group by 1
    having count(*) >= 500
),

ranked as (
    select
        *,
        ntile(10) over (order by slow_rate_pct desc, zip asc) as slow_decile
    from by_zip
)

select
    slow_decile,
    count(*) as zip_codes,
    sum(requests) as requests,
    sum(slow_requests) as slow_requests,
    round(100.0 * sum(slow_requests) / sum(requests), 1) as slow_rate_pct,
    round(100.0 * sum(slow_requests) / sum(sum(slow_requests)) over (), 1) as pct_of_slow_requests
from ranked
group by slow_decile
order by slow_decile;
