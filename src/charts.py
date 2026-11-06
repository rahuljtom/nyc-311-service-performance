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
    back = pd.read_csv(TABLES / "r06_backlog.csv", parse_dates=["month_end"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    axes[0].bar(vol["month_start"].dt.strftime("%b"), vol["requests"] / 1000, color=BLUE)
    axes[0].set_title("Requests created per month (thousands)")
    axes[1].plot(back["month_end"].dt.strftime("%b"), back["open_at_month_end"] / 1000, color=GREY, marker="o",
                 label="open at month end")
    axes[1].plot(back["month_end"].dt.strftime("%b"), back["open_over_30d"] / 1000, color=RED, marker="o",
                 label="open longer than 30 days")
    axes[1].set_title("Open backlog of 2024-created requests (thousands)")
    axes[1].legend(frameon=False)
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
