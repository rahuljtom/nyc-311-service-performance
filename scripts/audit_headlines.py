"""Independent recomputation of headline numbers, straight from the raw CSV files with pandas.

It does not use the DuckDB warehouse or any analysis SQL: it re-reads the downloaded files, applies the stated rules
again, and fails if a number differs from outputs/tables.

    python scripts/audit_headlines.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
failures = []


def check(name, mine, theirs, tol=0.051):
    ok = abs(mine - theirs) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {name}: pandas {mine:.2f} vs sql {theirs:.2f}")
    if not ok:
        failures.append(name)


def load():
    files = sorted((ROOT / "data" / "raw").glob("311_2024-*.csv"))
    df = pd.concat((pd.read_csv(f, dtype=str) for f in files), ignore_index=True)
    df = df.drop_duplicates("unique_key")
    for col in ("created_date", "closed_date"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["agency"] = df["agency"].str.upper().str.strip()
    df["borough"] = df["borough"].str.upper().str.strip()
    df.loc[~df["borough"].isin(["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"]), "borough"] = pd.NA
    df["channel"] = df["open_data_channel_type"].str.upper().str.strip().fillna("UNKNOWN")
    snapshot = df["closed_date"].max()
    df["unknown"] = df["status"].str.upper().str.strip().eq("CLOSED") & df["closed_date"].isna()
    ok_order = (df["closed_date"].isna() | (df["closed_date"] >= df["created_date"])) & ~df["unknown"]
    df["hours"] = (df["closed_date"] - df["created_date"]).dt.total_seconds() / 3600
    df.loc[df["closed_date"] < df["created_date"], "hours"] = pd.NA
    df["obs7"] = (df["created_date"] <= snapshot - pd.Timedelta(days=7)) & ok_order
    df["obs30"] = (df["created_date"] <= snapshot - pd.Timedelta(days=30)) & ok_order
    df["c7"] = df["closed_date"].notna() & (df["closed_date"] >= df["created_date"]) & (df["closed_date"] <= df["created_date"] + pd.Timedelta(days=7))
    df["c30"] = df["closed_date"].notna() & (df["closed_date"] >= df["created_date"]) & (df["closed_date"] <= df["created_date"] + pd.Timedelta(days=30))
    return df


def kaplan_meier(durations_days, closed, horizon):
    """Share still open after `horizon` days, by the textbook product-limit formula, written out with plain loops."""
    surv = 1.0
    order = pd.DataFrame({"d": durations_days, "e": closed})
    for day in range(0, horizon):
        at_risk = (order.d >= day).sum()
        events = ((order.d == day) & order.e).sum()
        if at_risk:
            surv *= 1 - events / at_risk
    return 100 * surv


def audit_decision_tables(df, obs):
    snapshot = df["closed_date"].max()
    valid = df[~df.unknown & (df.closed_date.isna() | (df.closed_date >= df.created_date))]

    surv = pd.read_csv(TABLES / "r13_survival_curves.csv")
    hpd = valid[valid.agency == "HPD"]
    dur = ((hpd.closed_date.fillna(snapshot) - hpd.created_date).dt.total_seconds() // 86400).astype(int)
    for horizon in (7, 30):
        sql_val = surv[(surv.series == "HPD") & (surv.days_since_created <= horizon)].iloc[-1].pct_still_open
        check(f"HPD still open after {horizon} days (Kaplan-Meier) %", kaplan_meier(dur.values, hpd.closed_date.notna().values, horizon), sql_val)
    naive = 100 * (1 - obs[obs.agency == "HPD"].c7.mean())
    km7 = surv[(surv.series == "HPD") & (surv.days_since_created <= 7)].iloc[-1].pct_still_open
    check("HPD 7-day open share: naive vs Kaplan-Meier agree", naive, km7, tol=0.5)

    # Share of variation explained by complaint type, fitted on even keys and scored on odd keys.
    work = obs.assign(y=(~obs.c7).astype(int), key=pd.to_numeric(obs.unique_key), grp=obs.agency + "|" + obs.complaint_type)
    train, test = work[work.key % 2 == 0], work[work.key % 2 == 1]
    rate = train.groupby("grp").y.mean()
    pred = test.grp.map(rate).fillna(train.y.mean())
    r2 = 100 * (1 - ((test.y - pred) ** 2).sum() / ((test.y - train.y.mean()) ** 2).sum())
    drivers = pd.read_csv(TABLES / "r14_slow_drivers.csv").set_index("predictors")
    check("Variation in slow explained by complaint type %", r2, drivers.loc["Complaint type", "pct_of_variation_explained"])

    # Vulnerability: slow rate and gap for index group 5 across all agencies.
    hvi = pd.read_csv(ROOT / "data" / "reference" / "hvi_zcta.csv", dtype=str)
    zips = obs.assign(zip=obs.incident_zip.str.strip().str[:5]).merge(hvi, on="zip", how="inner")
    zips = zips[zips.borough.notna()].assign(y=lambda x: (~x.c7).astype(int))
    expected = zips.groupby(["agency", "complaint_type"]).y.transform("mean")
    vul = pd.read_csv(TABLES / "r15_vulnerability_gap.csv")
    row = vul[(vul.scope == "All agencies") & (vul.hvi == 5)].iloc[0]
    sel = zips.hvi == "5"
    check("HVI 5 requests", sel.sum(), row.requests, tol=0)
    check("HVI 5 slow rate %", 100 * zips[sel].y.mean(), row.slow_rate_pct)
    check("HVI 5 gap vs complaint-type expectation (pp)", 100 * (zips[sel].y.mean() - expected[sel].mean()), row.gap_pp, tol=0.011)

    # Levers: the type-wide scenario is a quarter of the slow requests in the five biggest slow HPD types.
    slow_hpd = obs[(obs.agency == "HPD") & ~obs.c7].groupby("complaint_type").size().sort_values(ascending=False).head(5)
    levers = pd.read_csv(TABLES / "r16_levers.csv")
    lever_c = levers[levers.lever.str.startswith("C:")].iloc[0]
    check("Lever C recoverable (25% of top five HPD types)", 0.25 * slow_hpd.sum(), lever_c.recoverable_slow, tol=0.51)

    # Data mess: rows marked closed with no close date.
    mess = pd.read_csv(TABLES / "r18_data_mess.csv").set_index("issue")
    check("Closed without close date (rows)", df.unknown.sum(), mess.loc["Marked CLOSED but no close date", "rows_affected"], tol=0)


def main():
    df = load()
    obs = df[df.obs7]

    agency = pd.read_csv(TABLES / "r04_agency_performance.csv").set_index("agency")
    for a in ("HPD", "NYPD", "DPR"):
        d = obs[obs.agency == a]
        check(f"{a} observable requests", len(d), agency.loc[a, "requests"], tol=0)
        check(f"{a} closed within 7 days %", 100 * d.c7.mean(), agency.loc[a, "closed_within_7d_pct"])
        check(f"{a} median hours (closed)", d.hours.median(), agency.loc[a, "median_hours_closed"])
        check(f"{a} p90 hours (closed)", d.hours.quantile(0.9), agency.loc[a, "p90_hours_closed"])

    slow = obs[~obs.c7].groupby(["agency", "complaint_type"]).size().sort_values(ascending=False)
    pareto = pd.read_csv(TABLES / "r10_slow_request_pareto.csv")
    top = pareto.iloc[0]
    check("top slow type count", slow.iloc[0], top.slow_requests, tol=0)
    check("HPD share of all slow requests %", 100 * slow.loc["HPD"].sum() / slow.sum(),
          100 * pareto[pareto.agency == "HPD"].slow_requests.sum() / pareto.slow_requests.sum())

    chan = pd.read_csv(TABLES / "r09_channel_mix.csv").set_index("channel")
    for ch in ("MOBILE", "PHONE", "ONLINE"):
        check(f"{ch} closed within 7 days %", 100 * obs[obs.channel == ch].c7.mean(), chan.loc[ch, "closed_within_7d_pct"])

    vol = pd.read_csv(TABLES / "r03_monthly_volume.csv")
    check("December volume", (df.created_date.dt.month == 12).sum(), vol.iloc[-1].requests, tol=0)

    cohort = pd.read_csv(TABLES / "r06_backlog.csv")
    jan = df[(df.created_date.dt.month == 1) & df.obs30]
    check("January cohort closed within 30 days %", 100 * jan.c30.mean(), cohort.iloc[0].pct_closed_within_30d)

    gaps = pd.read_csv(TABLES / "r08_borough_gaps.csv")
    row = gaps[(gaps.agency == "DHS") & (gaps.complaint_type == "Encampment") & (gaps.borough == "Bronx")].iloc[0]
    base = df[(df.agency == "DHS") & (df.complaint_type == "Encampment") & df.borough.notna() & df.hours.notna()]
    mine = base[base.borough == "BRONX"].hours.median() / base.hours.median()
    check("DHS Encampment Bronx ratio to city", mine, row.ratio_to_city, tol=0.011)


    audit_decision_tables(df, obs)
    print("\nALL CHECKS PASSED" if not failures else f"\nFAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
