-- How long do requests really stay open? A Kaplan-Meier survival curve per series: the share of requests still open after
-- N days, where a request that is still open at the extract date is "censored" (we only know it lasted at least that long)
-- instead of being dropped or counted as finished. Requests marked closed with no close date, or with an impossible close
-- date, are left out. Series: the six busiest agencies, and the five complaint types that produce the most slow HPD requests.
create or replace table km_series as
with spans as (
    select
        agency,
        complaint_type,
        closed_at is not null as is_closed,
        floor(date_diff('second', created_at, coalesce(closed_at, (select snapshot_at from meta))) / 86400.0)::integer as age_day
    from requests
    where not close_unknown and (closed_at is null or closed_at >= created_at)
),

top_agencies as (
    select agency from requests
    group by agency
    order by count(*) desc, agency asc limit 6
),

top_hpd_types as (
    select complaint_type
    from requests
    where agency = 'HPD' and observable_7d and not closed_within_7d
    group by complaint_type
    order by count(*) desc, complaint_type asc
    limit 5
)

select
    agency as series,
    age_day,
    is_closed
from spans
where agency in (select agency from top_agencies)
union all
select
    'HPD: ' || complaint_type as series,
    age_day,
    is_closed
from spans
where agency = 'HPD' and complaint_type in (select complaint_type from top_hpd_types);

create or replace table r13_survival_curves as
with per_day as (
    select
        series,
        age_day,
        count(*) as leaving,
        count(*) filter (where is_closed) as closed
    from km_series
    where age_day >= 0
    group by series, age_day
),

at_risk as (
    select
        series,
        age_day,
        closed,
        sum(leaving) over (partition by series order by age_day desc rows between unbounded preceding and current row) as n_at_risk
    from per_day
)

select
    series,
    age_day + 1 as days_since_created,
    n_at_risk,
    closed,
    round(100 * exp(sum(ln(greatest(1 - closed::double / n_at_risk, 1e-12))) over (partition by series order by age_day)), 2)
        as pct_still_open
from at_risk
where age_day <= 89
order by series asc, days_since_created asc;
