-- What explains whether a request is slow? Each row predicts "not closed within 7 days" from one set of facts alone
-- (the average slow rate of requests sharing those facts), fitted on half of the requests (even keys) and scored on the
-- other half (odd keys), so groups with few requests cannot flatter the result. The score is the share of the variation in
-- slow/not-slow that the facts account for (like R squared, using squared error). Groups unseen in the fitting half
-- fall back to the overall rate.
create or replace table r14_slow_drivers as
with base as (
    select
        unique_key % 2 as fold,
        agency || ' | ' || complaint_type as k_type,
        coalesce(borough, '?') as k_borough,
        coalesce(channel, '?') as k_channel,
        strftime(created_at, '%Y-%m') as k_month,
        coalesce(zip, '?') as k_zip,
        (not closed_within_7d)::integer as y
    from requests
    where observable_7d
),

sets as (
    select
        'Complaint type' as predictors,
        1 as sort_order,
        fold,
        y,
        k_type as k
    from base
    union all
    select
        'Borough' as predictors,
        2 as sort_order,
        fold,
        y,
        k_borough as k
    from base
    union all
    select
        'Intake channel' as predictors,
        3 as sort_order,
        fold,
        y,
        k_channel as k
    from base
    union all
    select
        'Month created' as predictors,
        4 as sort_order,
        fold,
        y,
        k_month as k
    from base
    union all
    select
        'ZIP code' as predictors,
        5 as sort_order,
        fold,
        y,
        k_zip as k
    from base
    union all
    select
        'Complaint type + borough' as predictors,
        6 as sort_order,
        fold,
        y,
        k_type || k_borough as k
    from base
    union all
    select
        'Type + borough + channel + month' as predictors,
        7 as sort_order,
        fold,
        y,
        k_type || k_borough || k_channel || k_month as k
    from base
    union all
    select
        'Borough + channel + month + ZIP (no type)' as predictors,
        8 as sort_order,
        fold,
        y,
        k_borough || k_channel || k_month || k_zip as k
    from base
),

fitted as (
    select
        predictors,
        k,
        avg(y) as p
    from sets
    where fold = 0
    group by predictors, k
),

overall as (
    select avg(y) as p from base
    where fold = 0
),

scored as (
    select
        s.predictors,
        s.sort_order,
        power(s.y - coalesce(f.p, o.p), 2) as squared_error,
        power(s.y - o.p, 2) as baseline_error
    from sets as s
    cross join overall as o
    left join fitted as f on s.predictors = f.predictors and s.k = f.k
    where s.fold = 1
),

group_counts as (
    select
        predictors,
        count(*) as groups_fitted
    from fitted
    group by predictors
)

select
    sc.predictors,
    g.groups_fitted,
    round(100 * (1 - sum(sc.squared_error) / sum(sc.baseline_error)), 1) as pct_of_variation_explained
from scored as sc
inner join group_counts as g on sc.predictors = g.predictors
group by sc.predictors, sc.sort_order, g.groups_fitted
order by sc.sort_order asc;
