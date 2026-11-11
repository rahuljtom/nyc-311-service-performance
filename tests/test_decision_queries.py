"""Tests for the queries that support the decision write-up (survival, drivers, vulnerability, levers, data-mess catalogue).

They reuse the hand-built dataset from test_queries.py and add one request, key 9: DHS, Bronx, status CLOSED but no close date.
Reference table used for the ZIP join: 10451 -> 5, 11201 -> 1, 10001 -> 2, 11375 -> 3.
"""
import csv

import duckdb
import pytest

import pipeline
from test_queries import HEADER, ROWS

EXTRA = ["9", "2024-01-03T00:00:00.000", "", "", "DHS", "Homeless", "x", "BRONX", "10451", "Closed", "PHONE"]


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    base = tmp_path_factory.mktemp("decision")
    raw = base / "311_test.csv"
    with open(raw, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(ROWS + [EXTRA])
    ref = base / "ref"
    ref.mkdir()
    with open(ref / "hvi_zcta.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["zip", "hvi"])
        writer.writerows([["10451", "5"], ["11201", "1"], ["10001", "2"], ["11375", "3"]])
    conn = duckdb.connect(":memory:")
    pipeline.build(conn, str(raw), ref_dir=ref)
    yield conn
    conn.close()


def rows(con, sql):
    return con.execute(sql).fetchall()


def test_closed_without_close_date_is_unknown_not_a_miss(con):
    got = rows(con, "select close_unknown, observable_7d, closed_within_7d from requests where unique_key = 9")
    assert got == [(True, False, False)]
    assert rows(con, "select count(*) from requests where close_unknown") == [(1,)]


def test_unknown_outcome_is_left_out_of_the_slow_pareto(con):
    assert rows(con, "select count(*) from r10_slow_request_pareto where agency = 'DHS'") == [(0,)]


def test_survival_curve_censors_open_requests(con):
    """HPD Heat: request 3 closes on day 15 (the 16th day); request 4 is still open and is censored at day 23.
    At day 15 two requests are at risk and one closes, so 50% remain open, then nothing more can change."""
    got = rows(con, "select days_since_created, n_at_risk, closed, pct_still_open from r13_survival_curves "
                    "where series = 'HPD' order by days_since_created")
    assert got == [(16, 2, 1, 50.0), (24, 1, 0, 50.0)]


def test_survival_curve_reaches_zero_when_everyone_closes(con):
    got = rows(con, "select days_since_created, pct_still_open from r13_survival_curves where series = 'NYPD'")
    assert got == [(1, 0.0)]  # all three noise requests close within the first day


def test_survival_excludes_unknown_outcomes(con):
    assert rows(con, "select count(*) from r13_survival_curves where series = 'DHS'") == [(0,)]


def test_drivers_reports_every_predictor_set_with_bounded_scores(con):
    got = rows(con, "select predictors, pct_of_variation_explained from r14_slow_drivers")
    assert len(got) == 8
    assert all(score is None or score <= 100 for _, score in got)


def test_vulnerability_join_counts_requests_by_index_group(con):
    # Observable requests with a borough and a mapped ZIP: key 3 and 4 (index 1), key 8 (index 2), keys 1 and 2 (index 5).
    # Key 7 is too recent, key 6 has no valid ZIP, key 9 has an unknown outcome.
    got = dict(rows(con, "select hvi, requests from r15_vulnerability_gap where scope = 'All agencies'"))
    assert got == {1: 2, 2: 1, 5: 2}


def test_vulnerability_gap_is_zero_when_a_group_matches_its_type_rate(con):
    got = rows(con, "select hvi, slow_rate_pct, expected_given_type_pct, gap_pp from r15_vulnerability_gap "
                    "where scope = 'HPD only'")
    assert got == [(1, 100.0, 100.0, 0.0)]


def test_levers_report_the_type_wide_scenario(con):
    got = rows(con, "select targets from r16_levers where lever like 'C:%'")
    assert got == [(1,)]  # only one HPD type (Heat) has slow requests in the fixture


def test_data_mess_catalogue_counts_the_closed_without_date_row(con):
    got = rows(con, "select rows_affected from r18_data_mess where issue = 'Marked CLOSED but no close date'")
    assert got == [(1,)]
