-- How do people contact the city, and does the channel change the outcome? Channels receive different complaint types, so
-- the raw closed-in-7-days rate is compared with the rate expected from each channel's own complaint mix (every complaint
-- type closed at its citywide rate). Actual minus expected is the part of the gap the mix does not explain.
-- Requests still open count as not closed.
create or replace table r09_channel_mix as
with type_rate as (
    select
        agency,
        complaint_type,
        avg(closed_within_7d::int) as type_closed_rate
    from requests
    where observable_7d
    group by agency, complaint_type
)

select
    coalesce(r.channel, 'UNKNOWN') as channel,
    count(*) as requests,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_requests,
    round(100.0 * avg(r.closed_within_7d::int), 1) as closed_within_7d_pct,
    round(100.0 * avg(t.type_closed_rate), 1) as expected_given_complaint_mix_pct,
    round(100.0 * (avg(r.closed_within_7d::int) - avg(t.type_closed_rate)), 1) as actual_minus_expected_pp
from requests as r
inner join type_rate as t on r.agency = t.agency and r.complaint_type = t.complaint_type
where r.observable_7d
group by 1
order by requests desc;
