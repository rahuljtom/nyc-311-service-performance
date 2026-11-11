-- Staging: load the raw CSV export, type it, standardise labels and derive the fields every analysis uses.
-- __RAW_GLOB__ is replaced by src/pipeline.py with the path to the raw CSV files.
-- Every raw column is read as text first so that bad values become NULL (try_cast) instead of stopping the load.
create or replace table raw_requests as
select * from read_csv('__RAW_GLOB__', header = true, all_varchar = true);

-- Duplicate unique_keys keep their earliest row.
create or replace table requests_typed as
select
    try_cast(unique_key as bigint) as unique_key,
    try_cast(created_date as timestamp) as created_at,
    try_cast(closed_date as timestamp) as closed_at,
    try_cast(due_date as timestamp) as due_at,
    upper(trim(agency)) as agency,
    trim(complaint_type) as complaint_type,
    trim(descriptor) as descriptor,
    case upper(trim(borough))
        when 'BRONX' then 'Bronx'
        when 'BROOKLYN' then 'Brooklyn'
        when 'MANHATTAN' then 'Manhattan'
        when 'QUEENS' then 'Queens'
        when 'STATEN ISLAND' then 'Staten Island'
    end as borough,
    case when regexp_matches(trim(incident_zip), '^[0-9]{5}') then left(trim(incident_zip), 5) end as zip,
    upper(trim(status)) as status,
    upper(trim(open_data_channel_type)) as channel
from raw_requests
qualify row_number() over (partition by unique_key order by created_date) = 1;

-- The extract date is taken from the data itself: the latest close date seen anywhere in the file.
create or replace table meta as
select max(closed_at) as snapshot_at
from requests_typed;

create or replace table requests as
select
    t.*,
    -- Marked CLOSED but no close date: the outcome is unknown, so these are kept out of every closure measure
    -- (counting them as open would call them misses; counting them as closed would need a date we do not have).
    (t.status = 'CLOSED' and t.closed_at is null) as close_unknown,
    -- A close date before the create date is a data error: the duration is left NULL, never "fixed".
    case
        when t.closed_at >= t.created_at then date_diff('second', t.created_at, t.closed_at) / 3600.0
    end as resolution_hours,
    -- A request can only be judged on a 7-day target if 7 days have passed since it was created.
    -- Rows with an impossible close date, or marked closed without a close date, are excluded from the closure measures
    -- (neither hit nor miss).
    t.created_at <= m.snapshot_at - interval 7 day
    and (t.closed_at is null or t.closed_at >= t.created_at)
    and not (t.status = 'CLOSED' and t.closed_at is null) as observable_7d,
    t.closed_at is not null and t.closed_at >= t.created_at
    and t.closed_at <= t.created_at + interval 7 day as closed_within_7d,
    t.created_at <= m.snapshot_at - interval 30 day
    and (t.closed_at is null or t.closed_at >= t.created_at)
    and not (t.status = 'CLOSED' and t.closed_at is null) as observable_30d,
    t.closed_at is not null and t.closed_at >= t.created_at
    and t.closed_at <= t.created_at + interval 30 day as closed_within_30d
from requests_typed as t
cross join meta as m
where t.created_at is not null and t.agency is not null and t.complaint_type is not null;
