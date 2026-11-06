"""Draw the README charts from the exported result tables in outputs/tables.

Usage:
    python src/charts.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "outputs" / "tables"
CHARTS = ROOT / "outputs" / "charts"
BLUE, GREY, RED = "#2f6f9f", "#9aa5b1", "#c0504d"


def save(fig, name):
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=140)
    plt.close(fig)


def volume_and_backlog():
    vol = pd.read_csv(TABLES / "r03_monthly_volume.csv", parse_dates=["month_start"])
    cohort = pd.read_csv(TABLES / "r06_backlog.csv", parse_dates=["created_month"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    axes[0].bar(vol["month_start"].dt.strftime("%b"), vol["requests"] / 1000, color=BLUE)
    axes[0].set_title("Requests created per month (thousands)")
    months = cohort["created_month"].dt.strftime("%b")
    axes[1].plot(months, cohort["pct_closed_within_30d"], color=BLUE, marker="o", label="closed within 30 days")
    axes[1].plot(months, 100 - cohort["pct_still_open_at_extract"], color=GREY, marker="o", label="closed by extract date")
    axes[1].set_ylim(0, 100)
    axes[1].set_title("Share of each month's requests that closed (%)")
    axes[1].legend(frameon=False, loc="lower left")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    save(fig, "volume_and_backlog.png")


def slow_pareto():
    df = pd.read_csv(TABLES / "r10_slow_request_pareto.csv").head(12).iloc[::-1]
    labels = df["agency"] + " | " + df["complaint_type"].str.slice(0, 32)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(labels, df["slow_requests"] / 1000, color=RED)
    for y, (n, rate) in enumerate(zip(df["slow_requests"], df["slow_rate_pct"])):
        ax.text(n / 1000, y, f"  {rate:.0f}% slow", va="center", fontsize=8)
    ax.set_title("Requests not closed within 7 days, top 12 complaint types (thousands)")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "slow_request_pareto.png")


def zip_deciles():
    df = pd.read_csv(TABLES / "r11_zip_deciles.csv")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(df["slow_decile"].astype(str), df["pct_of_slow_requests"], color=BLUE)
    ax.set_xlabel("ZIP-code decile by slow-request rate (1 = slowest)")
    ax.set_title("Share of all slow requests in each ZIP decile (%)")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "zip_deciles.png")


def main():
    volume_and_backlog()
    slow_pareto()
    zip_deciles()
    return 0


if __name__ == "__main__":
    sys.exit(main())
