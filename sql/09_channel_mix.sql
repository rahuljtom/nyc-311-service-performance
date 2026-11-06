-- How do people contact the city, and does the channel change the outcome? Closed-in-7-days counts open requests as misses.
create or replace table r09_channel_mix as
select
    coalesce(channel, 'UNKNOWN') as channel,
    count(*) as requests,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_requests,
    round(100.0 * avg(closed_within_7d::int), 1) as closed_within_7d_pct
from requests
where observable_7d
group by 1
order by requests desc;
