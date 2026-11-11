-- Where would effort pay off most? For each place-and-type cell, the slow requests above what the citywide rate for that
-- complaint type predicts, minus a 95% chance margin (so noise in small cells is not counted as a problem to fix).
-- Three levers are compared by how many slow requests each could recover and how many targets it needs:
--   A  borough catch-up : bring each borough-and-type cell that is slower than chance allows down to the citywide rate
--   B  ZIP catch-up     : the same for ZIP-and-type cells (top 25 and top 100 cells shown separately)
--   C  type-wide fix    : cut the slow rate of the five biggest slow complaint types by a quarter (a scenario, not a forecast)
create or replace table cells_zip as
select
    agency,
    complaint_type,
    zip,
    count(*) as requests,
    count(*) filter (where not closed_within_7d) as slow
from requests
where observable_7d and zip is not null
group by agency, complaint_type, zip
having count(*) >= 50;

create or replace table cells_borough as
select
    agency,
    complaint_type,
    borough,
    count(*) as requests,
    count(*) filter (where not closed_within_7d) as slow
from requests
where observable_7d and borough is not null
group by agency, complaint_type, borough
having count(*) >= 200;

create or replace table type_rates as
select
    agency,
    complaint_type,
    count(*) filter (where not closed_within_7d)::double / count(*) as city_rate,
    count(*) filter (where not closed_within_7d) as slow_total
from requests
where observable_7d
group by agency, complaint_type;

create or replace table r16_recoverable_cells as
select
    c.agency,
    c.complaint_type,
    c.zip,
    c.requests,
    c.slow,
    round(100.0 * c.slow / c.requests, 1) as slow_rate_pct,
    round(100 * t.city_rate, 1) as city_rate_pct,
    round(greatest(0, c.slow - t.city_rate * c.requests - 1.96 * sqrt(c.requests * t.city_rate * (1 - t.city_rate))), 0)
        as recoverable_slow
from cells_zip as c
inner join type_rates as t on c.agency = t.agency and c.complaint_type = t.complaint_type
order by recoverable_slow desc, c.agency asc, c.complaint_type asc, c.zip asc
limit 100;

create or replace table r16_levers as
with borough_lever as (
    select greatest(0, c.slow - t.city_rate * c.requests - 1.96 * sqrt(c.requests * t.city_rate * (1 - t.city_rate))) as recoverable
    from cells_borough as c
    inner join type_rates as t on c.agency = t.agency and c.complaint_type = t.complaint_type
),

zip_lever as (
    select
        row_number() over (order by greatest(0, c.slow - t.city_rate * c.requests - 1.96 * sqrt(c.requests * t.city_rate * (1 - t.city_rate))) desc, c.agency asc, c.complaint_type asc, c.zip asc) as rnk,
        greatest(0, c.slow - t.city_rate * c.requests - 1.96 * sqrt(c.requests * t.city_rate * (1 - t.city_rate))) as recoverable
    from cells_zip as c
    inner join type_rates as t on c.agency = t.agency and c.complaint_type = t.complaint_type
),

top_types as (
    select slow_total
    from type_rates
    where agency = 'HPD'
    order by slow_total desc, complaint_type asc
    limit 5
),

all_slow as (
    select sum(slow_total) as n from type_rates
),

levers as (
    select
        'A: borough catch-up (all slower-than-chance borough-type cells)' as lever,
        1 as sort_order,
        count(*) filter (where recoverable > 0) as targets,
        round(sum(recoverable), 0) as recoverable_slow
    from borough_lever
    union all
    select
        'B: ZIP catch-up, top 25 ZIP-type cells' as lever,
        2 as sort_order,
        count(*) filter (where recoverable > 0) as targets,
        round(sum(recoverable), 0) as recoverable_slow
    from zip_lever
    where rnk <= 25
    union all
    select
        'B: ZIP catch-up, top 100 ZIP-type cells' as lever,
        3 as sort_order,
        count(*) filter (where recoverable > 0) as targets,
        round(sum(recoverable), 0) as recoverable_slow
    from zip_lever
    where rnk <= 100
    union all
    select
        'B: ZIP catch-up, every slower-than-chance ZIP-type cell' as lever,
        4 as sort_order,
        count(*) filter (where recoverable > 0) as targets,
        round(sum(recoverable), 0) as recoverable_slow
    from zip_lever
    union all
    select
        'C: type-wide, cut slow rate of top 5 HPD types by 25% (scenario)' as lever,
        5 as sort_order,
        count(*) as targets,
        round(0.25 * sum(slow_total), 0) as recoverable_slow
    from top_types
)

select
    lever,
    targets,
    recoverable_slow,
    round(100.0 * recoverable_slow / (select n from all_slow), 1) as pct_of_all_slow
from levers
order by sort_order;
