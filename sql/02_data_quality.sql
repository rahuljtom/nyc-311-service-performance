-- Data quality profile. Counts here explain every exclusion made in the staging step.
create or replace table r02_data_quality as
with profile as (
    select
        (select count(*) from raw_requests) as raw_rows,
        (select count(*) from requests_typed) as distinct_key_rows,
        count(*) as usable_rows,
        count(*) filter (where closed_at < created_at) as close_before_create,
        count(*) filter (where status = 'CLOSED' and closed_at is null) as closed_status_no_close_date,
        count(*) filter (where closed_at is not null and status <> 'CLOSED') as close_date_not_closed_status,
        count(*) filter (where borough is null) as borough_missing_or_unspecified,
        count(*) filter (where zip is null) as zip_missing_or_malformed,
        count(*) filter (where due_at is null) as no_due_date,
        count(*) filter (where closed_at is null) as still_open
    from requests
)

select
    check_name,
    n,
    round(100.0 * n / max(n) filter (where check_name = 'raw_rows') over (), 2) as pct_of_raw_rows
from profile
unpivot (n for check_name in (
    raw_rows,
    distinct_key_rows,
    usable_rows,
    close_before_create,
    closed_status_no_close_date,
    close_date_not_closed_status,
    borough_missing_or_unspecified,
    zip_missing_or_malformed,
    no_due_date,
    still_open
));
