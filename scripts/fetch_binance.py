#!/usr/bin/env python3
"""Fetch SOLUSDT 1h OHLCV from Binance public market data (no key).
Source: https://data-api.binance.vision/api/v3/klines
  (Binance global public data endpoint; api.binance.com returns 451 from this VM,
   api.binance.us works but has ~100x lower SOL volume, so .vision is the
   representative global spot price.)
Rate limit: klines weight 2 / request, limit 6000/min. We sleep 0.3s/request.
Range: 2025-11-17 00:00 UTC through last closed hourly candle before fetch time.
Output: partitioned CSVs ~/workspace/solana/dataset/year=YYYY/month=MM/sol_ohlcv_YYYY-MM-DD.csv
Columns: timestamp,open,high,low,close,volume,source
timestamp = candle open, UTC ISO 8601 with Z.
"""
import csv, json, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "SOLUSDT"
INTERVAL = "1h"
SOURCE = "Binance data-api.binance.vision SOLUSDT 1h"
OUT = Path.home() / "workspace/solana/dataset"

START = datetime(2025, 11, 17, 0, 0, tzinfo=timezone.utc)
# last closed hour: floor fetch time to the hour, that candle is still open, so stop before it
now = datetime.now(timezone.utc)
LAST_OPEN = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

def fetch(start_ms, limit=1000):
    url = f"{BASE}?symbol={SYMBOL}&interval={INTERVAL}&startTime={start_ms}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "muse-solana-dataset/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

rows = []
start_ms = int(START.timestamp() * 1000)
last_open_ms = int(LAST_OPEN.timestamp() * 1000)
calls = 0
while start_ms <= last_open_ms:
    data = fetch(start_ms)
    calls += 1
    if not data:
        break
    for k in data:
        # k: [open_time, open, high, low, close, volume, close_time, ...]
        rows.append(k)
    print(f"call {calls}: got {len(data)} rows, {datetime.fromtimestamp(data[0][0]/1000, timezone.utc)} .. {datetime.fromtimestamp(data[-1][0]/1000, timezone.utc)}", flush=True)
    if len(data) < 1000:
        break
    start_ms = data[-1][0] + 3600_000
    time.sleep(0.3)

print(f"total rows fetched: {len(rows)} in {calls} calls")
print(f"first: {datetime.fromtimestamp(rows[0][0]/1000, timezone.utc)}  last: {datetime.fromtimestamp(rows[-1][0]/1000, timezone.utc)}")

# de-dupe by open_time, sort, drop any still-open candle past LAST_OPEN
seen = {}
for k in rows:
    seen[k[0]] = k
rows = [seen[t] for t in sorted(seen) if t <= last_open_ms]
print(f"after dedupe: {len(rows)}")

# partition by UTC day
from collections import defaultdict
by_day = defaultdict(list)
for k in rows:
    dt = datetime.fromtimestamp(k[0]/1000, timezone.utc)
    by_day[dt.date()].append(k)

for day in sorted(by_day):
    d = by_day[day]
    p = OUT / f"year={day.year}" / f"month={day.month:02d}" / f"sol_ohlcv_{day.isoformat()}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume", "source"])
        for k in d:
            ts = datetime.fromtimestamp(k[0]/1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            w.writerow([ts, k[1], k[2], k[3], k[4], k[5], SOURCE])

# daily aggregate
daily_dir = OUT / "daily"
daily_dir.mkdir(parents=True, exist_ok=True)
with open(daily_dir / "sol_ohlcv_daily.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp", "open", "high", "low", "close", "volume", "source"])
    for day in sorted(by_day):
        d = sorted(by_day[day], key=lambda k: k[0])
        ts = datetime.fromtimestamp(d[0][0]/1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        w.writerow([ts, d[0][1], f"{max(float(x[2]) for x in d):.8f}", f"{min(float(x[3]) for x in d):.8f}", d[-1][4],
                    f"{sum(float(x[5]) for x in d):.3f}", SOURCE + " (daily aggregate of 1h)"])

print(f"days written: {len(by_day)}")
print(f"expected hours 2025-11-17 00:00 to {LAST_OPEN}: {int((LAST_OPEN - START).total_seconds()//3600)+1}")
