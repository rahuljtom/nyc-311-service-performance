-- Inside the five HPD complaint types that produce the most slow requests, which specific problems (descriptors) are slow?
-- Up to four descriptors per type, ranked by number of slow requests.
create or replace table r17_hpd_descriptors as
with top_types as (
    select complaint_type
    from requests
    where agency = 'HPD' and observable_7d and not closed_within_7d
    group by complaint_type
    order by count(*) desc, complaint_type asc
    limit 5
),

by_descriptor as (
    select
        complaint_type,
        coalesce(descriptor, '(blank)') as descriptor,
        count(*) as requests,
        count(*) filter (where not closed_within_7d) as slow_requests
    from requests
    where agency = 'HPD' and observable_7d and complaint_type in (select complaint_type from top_types)
    group by complaint_type, coalesce(descriptor, '(blank)')
)

select
    complaint_type,
    descriptor,
    requests,
    slow_requests,
    round(100.0 * slow_requests / requests, 1) as slow_rate_pct,
    round(100.0 * slow_requests / sum(slow_requests) over (partition by complaint_type), 1) as pct_of_type_slow,
    row_number() over (partition by complaint_type order by slow_requests desc, descriptor asc) as rank_in_type
from by_descriptor
qualify rank_in_type <= 4
order by complaint_type asc, rank_in_type asc;
