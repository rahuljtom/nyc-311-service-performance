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
    ok_order = df["closed_date"].isna() | (df["closed_date"] >= df["created_date"])
    df["hours"] = (df["closed_date"] - df["created_date"]).dt.total_seconds() / 3600
    df.loc[df["closed_date"] < df["created_date"], "hours"] = pd.NA
    df["obs7"] = (df["created_date"] <= snapshot - pd.Timedelta(days=7)) & ok_order
    df["obs30"] = (df["created_date"] <= snapshot - pd.Timedelta(days=30)) & ok_order
    df["c7"] = df["closed_date"].notna() & (df["closed_date"] >= df["created_date"]) & (df["closed_date"] <= df["created_date"] + pd.Timedelta(days=7))
    df["c30"] = df["closed_date"].notna() & (df["closed_date"] >= df["created_date"]) & (df["closed_date"] <= df["created_date"] + pd.Timedelta(days=30))
    return df


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
    check("HPD share of all slow requests %", 100 * slow.loc["HPD"].sum() / slow.sum(), 39.2)

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

    print("\nALL CHECKS PASSED" if not failures else f"\nFAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
