-- The mess that had to be handled before any number could be trusted: what was wrong, how many rows, how it was handled, and
-- what would have happened to the answer if it had been ignored. Counts come from the raw text table, not from a hand list.
create or replace table r18_data_mess as
with totals as (
    select count(*) as n from requests
),

dhs as (
    select
        round(
            (
                (count(*) filter (where observable_7d and not closed_within_7d) + count(*) filter (where close_unknown))::double
                / (count(*) filter (where observable_7d) + count(*) filter (where close_unknown))
            )
            / nullif(count(*) filter (where observable_7d and not closed_within_7d)::double / count(*) filter (where observable_7d), 0),
            1
        ) as inflation
    from requests
    where agency = 'DHS'
),

issues as (
    select
        1 as sort_order,
        'Marked CLOSED but no close date' as issue,
        count(*) filter (where close_unknown) as rows_affected,
        'Left out of every closure measure (outcome unknown)' as handling,
        'Counted as misses they would add ' || format('{:,}', count(*) filter (where close_unknown))
        || ' slow requests, ' || format('{:,}', count(*) filter (where close_unknown and agency = 'DHS'))
        || ' of them DHS, whose slow rate would read ' || coalesce((select inflation from dhs)::varchar, 'many')
        || ' times too high' as if_ignored
    from requests
    union all
    select
        2 as sort_order,
        'Close date earlier than create date' as issue,
        count(*) filter (where closed_at < created_at) as rows_affected,
        'Duration left empty and request excluded from closure measures; the dates are not guessed' as handling,
        'Negative durations would pull medians down' as if_ignored
    from requests
    union all
    select
        3 as sort_order,
        'Close date present but status not CLOSED' as issue,
        count(*) filter (where closed_at is not null and status <> 'CLOSED') as rows_affected,
        'Close date trusted' as handling,
        'Little: these requests have a usable close date' as if_ignored
    from requests
    union all
    select
        4 as sort_order,
        'Still open at the extract date (censored)' as issue,
        count(*) filter (where closed_at is null and not close_unknown) as rows_affected,
        'Counted as not closed in 7- and 30-day measures; survival curves treat them as censored' as handling,
        'Dropping them would make every agency look faster than it is' as if_ignored
    from requests
    union all
    select
        5 as sort_order,
        'Borough "Unspecified"' as issue,
        count(*) filter (where borough is null) as rows_affected,
        'Set to empty, never guessed from ZIP' as handling,
        'Would add a sixth, meaningless borough' as if_ignored
    from requests
    union all
    select
        6 as sort_order,
        'ZIP missing or malformed (for example NA, 0000, Unkno)' as issue,
        count(*) filter (where zip is null) as rows_affected,
        'Set to empty; kept in all non-ZIP analysis' as handling,
        'Would break the ZIP join to the vulnerability index' as if_ignored
    from requests
    union all
    select
        7 as sort_order,
        'Intake channel UNKNOWN' as issue,
        count(*) filter (where channel = 'UNKNOWN') as rows_affected,
        'Kept as its own value, not imputed' as handling,
        'Would silently move requests into ONLINE or PHONE' as if_ignored
    from requests
)

select
    issue,
    rows_affected,
    round(100.0 * rows_affected / (select n from totals), 2) as pct_of_requests,
    handling,
    if_ignored
from (
    select
        sort_order,
        issue,
        rows_affected,
        handling,
        if_ignored
    from issues
) as i
order by sort_order;
