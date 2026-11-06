-- Which complaint types make up the volume? Running share shows how concentrated demand is.
create or replace table r05_complaint_pareto as
with by_type as (
    select
        complaint_type,
        count(*) as requests
    from requests
    group by 1
)

select
    row_number() over (order by requests desc, complaint_type asc) as volume_rank,
    complaint_type,
    requests,
    round(100.0 * requests / sum(requests) over (), 2) as pct_of_total,
    round(
        100.0 * sum(requests) over (order by requests desc, complaint_type asc rows between unbounded preceding and current row)
        / sum(requests) over (),
        1
    ) as cumulative_pct
from by_type
order by volume_rank;
