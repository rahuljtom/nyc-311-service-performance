-- Open backlog at the end of each month among requests created in the file, and how much of it is older than
-- 30 days. Requests created before the file starts are not in the data, so this is the backlog of the cohort
-- created in the period, not the city's full queue.
create or replace table r06_backlog as
with month_ends as (
    select distinct date_trunc('month', created_at) + interval 1 month as boundary
    from requests
)

select
    b.boundary - interval 1 day as month_end,
    count(*) filter (where r.created_at < b.boundary) as created_to_date,
    count(*) filter (
        where r.created_at < b.boundary and (r.closed_at is null or r.closed_at >= b.boundary)
    ) as open_at_month_end,
    count(*) filter (
        where r.created_at < b.boundary - interval 30 day and (r.closed_at is null or r.closed_at >= b.boundary)
    ) as open_over_30d
from month_ends as b
cross join requests as r
group by b.boundary
order by b.boundary;
