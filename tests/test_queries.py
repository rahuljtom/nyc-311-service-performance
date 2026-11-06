"""Tests run the real SQL files against a tiny hand-built dataset whose answers are worked out by hand.

Fixture (8 raw rows; snapshot date = latest close date = 2024-02-17):
  1 NYPD Noise, Bronx, closed after 2h              5 duplicate of key 1 (dropped)
  2 NYPD Noise, Bronx, closed after 4h              6 DOT Pothole, close date BEFORE create date (bad), borough Unspecified
  3 HPD Heat, Brooklyn, closed after 360h (15 d)    7 DOT Pothole, Queens, closed after 48h, due 1 day in, so late
  4 HPD Heat, Brooklyn, still open, past due        8 NYPD Noise, Manhattan, closed after 3h
"""
import csv
import datetime

import duckdb
import pytest

import pipeline

HEADER = [
    "unique_key", "created_date", "closed_date", "due_date", "agency", "complaint_type",
    "descriptor", "borough", "incident_zip", "status", "open_data_channel_type",
]
ROWS = [
    ["1", "2024-01-01T00:00:00.000", "2024-01-01T02:00:00.000", "", "NYPD", "Noise", "x", "BRONX", "10451", "Closed", "ONLINE"],
    ["2", "2024-01-02T00:00:00.000", "2024-01-02T04:00:00.000", "", "NYPD", "Noise", "x", "BRONX", "10451", "Closed", "ONLINE"],
    ["3", "2024-01-05T00:00:00.000", "2024-01-20T00:00:00.000", "", "HPD", "Heat", "x", "BROOKLYN", "11201", "Closed", "ONLINE"],
    ["4", "2024-01-25T00:00:00.000", "", "2024-02-01T00:00:00.000", "HPD", "Heat", "x", "BROOKLYN", "11201", "Open", "ONLINE"],
    ["1", "2024-01-01T00:00:00.000", "2024-01-01T02:00:00.000", "", "NYPD", "Noise", "x", "BRONX", "10451", "Closed", "ONLINE"],
    ["6", "2024-02-10T00:00:00.000", "2024-02-09T00:00:00.000", "", "DOT", "Pothole", "x", "Unspecified", "N/A", "Closed", "PHONE"],
    ["7", "2024-02-15T00:00:00.000", "2024-02-17T00:00:00.000", "2024-02-16T00:00:00.000", "DOT", "Pothole", "x", "QUEENS", "11375", "Closed", "PHONE"],
    ["8", "2024-01-10T00:00:00.000", "2024-01-10T03:00:00.000", "", "NYPD", "Noise", "x", "MANHATTAN", "10001", "Closed", "PHONE"],
]


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw") / "311_test.csv"
    with open(raw, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(ROWS)
    conn = duckdb.connect(":memory:")
    pipeline.build(conn, str(raw))
    yield conn
    conn.close()


def rows(con, sql):
    return con.execute(sql).fetchall()


def test_staging_drops_duplicate_keys(con):
    assert rows(con, "select count(*) from requests") == [(7,)]


def test_resolution_hours_and_bad_dates(con):
    got = dict(rows(con, "select unique_key, resolution_hours from requests"))
    assert got[1] == 2.0 and got[3] == 360.0
    assert got[4] is None  # still open
    assert got[6] is None  # close before create: left NULL, not repaired


def test_unspecified_borough_and_bad_zip_become_null(con):
    assert rows(con, "select borough, zip from requests where unique_key = 6") == [(None, None)]


def test_snapshot_date_comes_from_the_data(con):
    assert str(rows(con, "select snapshot_at from meta")[0][0]) == "2024-02-17 00:00:00"


def test_observable_excludes_recent_and_impossible_rows(con):
    keys = [r[0] for r in rows(con, "select unique_key from requests where observable_7d order by 1")]
    assert keys == [1, 2, 3, 4, 8]  # 7 is too recent, 6 has an impossible close date


def test_data_quality_counts(con):
    got = dict((r[0], r[1]) for r in rows(con, "select check_name, n from r02_data_quality"))
    assert got["raw_rows"] == 8
    assert got["distinct_key_rows"] == 7
    assert got["usable_rows"] == 7
    assert got["close_before_create"] == 1
    assert got["borough_missing_or_unspecified"] == 1
    assert got["zip_missing_or_malformed"] == 1
    assert got["still_open"] == 1


def test_monthly_volume_and_mom_change(con):
    got = rows(con, "select requests, mom_change, mom_pct from r03_monthly_volume order by month_start")
    assert got == [(5, None, None), (2, -3, -60.0)]


def test_agency_scorecard_applies_minimum_volume(con):
    assert rows(con, "select count(*) from r04_agency_performance") == [(0,)]


def test_complaint_pareto_ranks_and_cumulates(con):
    got = rows(con, "select complaint_type, requests, cumulative_pct from r05_complaint_pareto order by volume_rank")
    assert got == [("Noise", 3, 42.9), ("Heat", 2, 71.4), ("Pothole", 2, 100.0)]


def test_backlog_follows_each_creation_month(con):
    got = rows(con, "select created_month, requests_created, open_at_end_of_month, pct_closed_within_30d, "
                    "pct_still_open_at_extract from r06_backlog order by created_month")
    # January: 5 created, request 4 still open; the 4 requests old enough to judge all closed within 30 days.
    # February: 2 created; request 6 has an impossible close date and request 7 is too recent, so nothing can be judged.
    assert got == [(datetime.date(2024, 1, 1), 5, 1, 100.0, 20.0), (datetime.date(2024, 2, 1), 2, 0, None, 0.0)]


def test_due_date_misses_with_threshold_lowered(con):
    sql = (pipeline.SQL_DIR / "07_due_date_misses.sql").read_text().replace("having count(*) >= 1000", "having count(*) >= 1")
    con.execute(sql)
    got = dict((r[0], (r[1], r[2])) for r in rows(con, "select agency, requests_with_due_date, late from r07_due_date_misses"))
    assert got == {"DOT": (1, 1), "HPD": (1, 1)}  # 7 closed late, 4 is open and past due


def test_slow_request_pareto(con):
    got = rows(con, "select complaint_type, requests, slow_requests, cumulative_pct_of_slow from r10_slow_request_pareto order by slow_rank")
    assert got == [("Heat", 2, 2, 100.0), ("Noise", 3, 0, 100.0)]


def test_channel_mix_and_mix_adjusted_expectation(con):
    got = rows(con, "select channel, requests, pct_of_requests, closed_within_7d_pct, expected_given_complaint_mix_pct, "
                    "actual_minus_expected_pp from r09_channel_mix order by channel")
    # ONLINE: Noise 100% x2 and Heat 0% x2 -> expected 50%, actual 50%. PHONE: one Noise request -> 100% both.
    assert got == [("ONLINE", 4, 80.0, 50.0, 50.0, 0.0), ("PHONE", 1, 20.0, 100.0, 100.0, 0.0)]


def test_borough_comparison_uses_the_same_rows_as_the_city(con):
    """A fast request with no borough must not drag the citywide median down: that was the original bug."""
    frame = con.execute("select * from requests").df()
    local = duckdb.connect(":memory:")
    local.register("frame", frame)
    local.execute("create table requests as select * from frame")
    local.execute("insert into requests select * replace (9 as unique_key, null as borough, 0.5 as resolution_hours) "
                  "from requests where unique_key = 1")
    # The same complaint type handled by a different agency must not leak into this agency's baseline.
    local.execute("insert into requests select * replace (10 as unique_key, 'XYZ' as agency, 100.0 as resolution_hours) "
                  "from requests where unique_key = 1")
    sql = (pipeline.SQL_DIR / "08_borough_gaps.sql").read_text()
    sql = sql.replace("having count(*) >= 2000", "having count(*) >= 1").replace("having count(*) >= 200", "having count(*) >= 1")
    local.execute(sql)
    got = local.execute("select borough, closed_requests, median_hours, city_median_hours, ratio_to_city from r08_borough_gaps "
                        "where complaint_type = 'Noise' and agency = 'NYPD' order by borough").fetchall()
    # NYPD with a borough: Bronx 2h and 4h, Manhattan 3h -> citywide 3h. Counting the 0.5h request or the other agency would change it.
    assert got == [("Bronx", 2, 3.0, 3.0, 1.0), ("Manhattan", 1, 3.0, 3.0, 1.0)]


def test_export_writes_one_csv_per_result_table(con, tmp_path):
    names = pipeline.export(con, tmp_path)
    assert "r10_slow_request_pareto" in names
    assert (tmp_path / "r03_monthly_volume.csv").exists()
