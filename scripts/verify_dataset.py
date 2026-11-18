#!/usr/bin/env python3
"""Verify ~/workspace/solana/dataset: counts, dupes, order, gaps, OHLC sanity,
daily-aggregate cross-check, and spot-check 3 closes against Binance live."""
import csv, json, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

BASE = Path.home() / "workspace/solana/dataset"
files = sorted(BASE.glob("year=*/month=*/sol_ohlcv_*.csv"))
rows = []
for f in files:
    with open(f) as fh:
        r = list(csv.DictReader(fh))
        for x in r:
            x["_file"] = f.name
            rows.append(x)
rows.sort(key=lambda x: x["timestamp"])
print(f"files: {len(files)}  rows: {len(rows)}")
print(f"first: {rows[0]['timestamp']} open={rows[0]['open']} close={rows[0]['close']}")
print(f"last:  {rows[-1]['timestamp']} open={rows[-1]['open']} close={rows[-1]['close']}")

# dupes
ts = [x["timestamp"] for x in rows]
dups = [t for t, c in Counter(ts).items() if c > 1]
print(f"duplicate timestamps: {len(dups)} {dups[:5]}")

# chronological + gaps (hourly)
fmt = "%Y-%m-%dT%H:%M:%SZ"
times = [datetime.strptime(t, fmt).replace(tzinfo=timezone.utc) for t in ts]
gaps = []
for a, b in zip(times, times[1:]):
    if b - a != timedelta(hours=1):
        gaps.append((a, b, (b-a).total_seconds()/3600))
print(f"non-1h steps: {len(gaps)} {gaps[:5]}")
print(f"expected hours first..last inclusive: {int((times[-1]-times[0]).total_seconds()//3600)+1}")

# OHLC sanity
bad = [x for x in rows if not (float(x["low"]) <= min(float(x["open"]), float(x["close"])) and float(x["high"]) >= max(float(x["open"]), float(x["close"])) and float(x["volume"]) > 0)]
print(f"OHLC/volume violations: {len(bad)}")
# per-month counts
mc = Counter(t.strftime("%Y-%m") for t in times)
for m in sorted(mc):
    print(f"  {m}: {mc[m]} rows")

# daily aggregate cross-check
daily = {}
with open(BASE / "daily/sol_ohlcv_daily.csv") as fh:
    for x in csv.DictReader(fh):
        daily[x["timestamp"][:10]] = x
print(f"daily rows: {len(daily)} (header excluded)")
mismatch = 0
from collections import defaultdict
by_day = defaultdict(list)
for x in rows:
    by_day[x["timestamp"][:10]].append(x)
for day, d in by_day.items():
    agg = daily.get(day)
    if not agg:
        mismatch += 1; continue
    if not (agg["open"] == d[0]["open"] and agg["close"] == d[-1]["close"]
            and abs(float(agg["high"]) - max(float(y["high"]) for y in d)) < 1e-9
            and abs(float(agg["low"]) - min(float(y["low"]) for y in d)) < 1e-9):
        mismatch += 1
print(f"daily aggregate mismatches: {mismatch}")

# spot-check 3 closes against Binance live klines
checks = [rows[0]["timestamp"], rows[len(rows)//2]["timestamp"], rows[-1]["timestamp"]]
for t in checks:
    dt = datetime.strptime(t, fmt).replace(tzinfo=timezone.utc)
    ms = int(dt.timestamp()*1000)
    url = f"https://data-api.binance.vision/api/v3/klines?symbol=SOLUSDT&interval=1h&startTime={ms}&limit=1"
    with urllib.request.urlopen(url, timeout=30) as r:
        k = json.loads(r.read())[0]
    local = next(x for x in rows if x["timestamp"] == t)
    print(f"spot {t}: local close={local['close']} live close={k[4]} open={k[1]} match={local['close']==k[4] and local['open']==k[1]}")

# summary stats
closes = [float(x["close"]) for x in rows]
print(f"close min ${min(closes):.2f} max ${max(closes):.2f} first ${closes[0]:.2f} last ${closes[-1]:.2f} change {(closes[-1]/closes[0]-1)*100:.1f}%")
print(f"total volume (SOL): {sum(float(x['volume']) for x in rows):,.0f}")
