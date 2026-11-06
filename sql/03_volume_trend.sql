-- Monthly request volume with month-on-month change and a trailing three-month average.
create or replace table r03_monthly_volume as
with monthly as (
    select
        date_trunc('month', created_at) as month_start,
        count(*) as requests
    from requests
    group by 1
)

select
    month_start,
    requests,
    requests - lag(requests) over w as mom_change,
    round(100.0 * (requests - lag(requests) over w) / lag(requests) over w, 1) as mom_pct,
    round(avg(requests) over (order by month_start rows between 2 preceding and current row), 0) as rolling_3m_avg
from monthly
window w as (order by month_start)
order by month_start;
