-- Share of requests that missed their own due date. A request is late if it closed after its due date, or is still
-- open and the extract date is past its due date. Only requests that carry a due date are included, and agencies
-- set due dates differently, so compare an agency with its own history rather than agencies with each other.
create or replace table r07_due_date_misses as
select
    r.agency,
    count(*) as requests_with_due_date,
    count(*) filter (
        where (r.closed_at is not null and r.closed_at > r.due_at)
        or (r.closed_at is null and m.snapshot_at > r.due_at)
    ) as late,
    round(100.0 * count(*) filter (
        where (r.closed_at is not null and r.closed_at > r.due_at)
        or (r.closed_at is null and m.snapshot_at > r.due_at)
    ) / count(*), 1) as late_pct
from requests as r
cross join meta as m
where r.due_at is not null
group by r.agency
having count(*) >= 1000
order by late_pct desc, agency asc;
