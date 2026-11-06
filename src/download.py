"""Download NYC 311 service requests for one calendar year from NYC Open Data.

Source: https://data.cityofnewyork.us/resource/erm2-nwe9 (Socrata SODA API, no key needed,
but unauthenticated requests are throttled, so pages are retried with back-off).

Usage:
    python src/download.py --year 2024
Fetches one day at a time (four in parallel) into data/raw/311_<date>.csv (git-ignored); reruns resume.
"""
import argparse
import csv
import datetime
import io
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://data.cityofnewyork.us/resource/erm2-nwe9.csv"
COLUMNS = [
    "unique_key", "created_date", "closed_date", "due_date", "agency",
    "complaint_type", "descriptor", "borough", "incident_zip", "status",
    "open_data_channel_type",
]
LIMIT = 100000
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch(params, retries=8):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504):
                raise
        except OSError:  # URLError, socket.timeout and connection resets are all OSError subclasses
            pass
        time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError("giving up on " + url)


def days_in_month(year, month):
    first = datetime.date(year, month, 1)
    nxt = datetime.date(year + (month == 12), month % 12 + 1, 1)
    return [first + datetime.timedelta(days=i) for i in range((nxt - first).days)]


def download_day(day):
    """One small query per day: avoids the server errors that large sorted, offset-paged queries trigger."""
    start = day.isoformat() + "T00:00:00"
    end = (day + datetime.timedelta(days=1)).isoformat() + "T00:00:00"
    text = fetch({
        "$select": ",".join(COLUMNS),
        "$where": f"created_date >= '{start}' and created_date < '{end}'",
        "$limit": LIMIT,
    })
    parsed = list(csv.reader(io.StringIO(text)))
    header, body = parsed[0], parsed[1:]
    if len(body) >= LIMIT:
        raise RuntimeError(f"{day}: hit the row limit, raise LIMIT")
    return header, body


def download_day_file(day):
    """Save one day to data/raw/311_<date>.csv; days already on disk are skipped so a rerun resumes."""
    out = RAW_DIR / f"311_{day.isoformat()}.csv"
    if out.exists():
        return 0
    header, body = download_day(day)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(body)
    tmp.rename(out)
    print(f"{out.name}: {len(body)} rows", flush=True)
    return len(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    days = [d for month in range(1, 13) for d in days_in_month(args.year, month)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        total = sum(pool.map(download_day_file, days))
    print("new rows this run:", total, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
