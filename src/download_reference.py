"""Download the small reference table that is joined to the 311 requests by ZIP code.

Source: NYC Department of Health and Mental Hygiene, Heat Vulnerability Index by ZIP code tabulation area
(NYC Open Data dataset 4mhf-duep). Each ZIP is scored 1 (least vulnerable) to 5 (most vulnerable) from surface
temperature, green space, home air-conditioning access, and the share of residents who are low-income or non-Latinx Black.
It is used here only as a published neighbourhood-vulnerability grouping, not as a measure of any one factor.

Usage:
    python src/download_reference.py
Writes data/reference/hvi_zcta.csv (about 180 rows; committed because it is small).
"""
import csv
import io
import sys
import urllib.request
from pathlib import Path

URL = "https://data.cityofnewyork.us/resource/4mhf-duep.csv?$limit=1000"
OUT = Path(__file__).resolve().parent.parent / "data" / "reference" / "hvi_zcta.csv"


def main():
    with urllib.request.urlopen(URL, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["zip", "hvi"])
        for row in sorted(rows, key=lambda r: r["zcta20"]):
            writer.writerow([row["zcta20"], row["hvi"]])
    print("wrote", OUT, len(rows), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
