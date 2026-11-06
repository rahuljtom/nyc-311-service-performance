-- For each complaint type, how does each borough's median time to close compare with the citywide median?
-- Ratio above 1 means slower than the city. Only closed requests, and only cells with at least 200 closed
-- requests in the borough and 2,000 in the city.
create or replace table r08_borough_gaps as
with by_borough as (
    select
        agency,
        complaint_type,
        borough,
        count(*) as closed_requests,
        quantile_cont(resolution_hours, 0.5) as median_hours
    from requests
    where resolution_hours is not null and borough is not null
    group by 1, 2, 3
    having count(*) >= 200
),

citywide as (
    select
        complaint_type,
        count(*) as city_closed,
        quantile_cont(resolution_hours, 0.5) as city_median_hours
    from requests
    where resolution_hours is not null
    group by 1
    having count(*) >= 2000
)

select
    b.agency,
    b.complaint_type,
    b.borough,
    b.closed_requests,
    round(b.median_hours, 1) as median_hours,
    round(c.city_median_hours, 1) as city_median_hours,
    round(b.median_hours / nullif(c.city_median_hours, 0), 2) as ratio_to_city,
    rank() over (partition by b.complaint_type order by b.median_hours desc) as slowest_rank
from by_borough as b
inner join citywide as c on b.complaint_type = c.complaint_type
order by ratio_to_city desc;
