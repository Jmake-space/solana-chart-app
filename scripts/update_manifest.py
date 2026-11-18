#!/usr/bin/env python3
"""Recompute MANIFEST.json from the CSVs on disk after a refresh.
Updates: last_timestamp_closed, hourly_rows, per-month rows, summary
(first/last close, change %, min/max close, total volume), fetch date,
refresh_history (append one line, keep last 10).
Also patches the matching numbers in dataset/README.md.
Run after fetch_binance.py + verify_dataset.py pass.
"""
import csv, json, re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

BASE = Path.home() / "workspace/solana"
DATA = BASE / "dataset"
rows = []
for f in sorted(DATA.glob("year=*/month=*/sol_ohlcv_*.csv")):
    with open(f) as fh:
        rows.extend(csv.DictReader(fh))
rows.sort(key=lambda x: x["timestamp"])
closes = [float(r["close"]) for r in rows]
times = [r["timestamp"] for r in rows]
per_month = dict(sorted(Counter(t[:7] for t in times).items()))
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
manifest_path = DATA / "MANIFEST.json"
m = json.loads(manifest_path.read_text())
m["fetch_date_utc"] = now
m["last_timestamp_closed"] = times[-1]
# next hour is the still-open candle
from datetime import timedelta
last_dt = datetime.strptime(times[-1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
m["excluded"] = f"{(last_dt + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')} candle was still open at fetch time"
m["hourly_rows"] = len(rows)
m["daily_files"] = len(set(t[:10] for t in times))
m["per_month_rows"] = per_month
m["summary"] = {
    "first_close_usd": round(closes[0], 2),
    "last_close_usd": round(closes[-1], 2),
    "change_pct": round((closes[-1] / closes[0] - 1) * 100, 1),
    "close_min_usd": round(min(closes), 2),
    "close_max_usd": round(max(closes), 2),
    "total_volume_sol": round(sum(float(r["volume"]) for r in rows)),
}
hist = m.get("refresh_history", [])
hist.append(f"{now}: {len(rows)} rows, last {times[-1]} close ${closes[-1]:.2f}")
m["refresh_history"] = hist[-10:]
manifest_path.write_text(json.dumps(m, indent=2))

# README patches (best-effort, only lines that match)
readme = DATA / "README.md"
t = readme.read_text()
t = re.sub(r"\*\*Last candle \(closed\):\*\* [^\n]*",
           f"**Last candle (closed):** {times[-1]}, close ${closes[-1]:.2f} (refreshed {now})", t)
t = re.sub(r"\*\*Rows:\*\* [\d,]+ hourly candles",
           f"**Rows:** {len(rows):,} hourly candles", t)
t = re.sub(r"first close \$[\d.]+ → last close \$[\d.]+ \(\*[\-0-9.]+%\* over the window\)",
           f"first close ${closes[0]:.2f} → last close ${closes[-1]:.2f} (**{(closes[-1]/closes[0]-1)*100:.1f}%** over the window)", t)
t = re.sub(r"\*\*Total volume:\*\* [\d,]+ SOL",
           f"**Total volume:** {m['summary']['total_volume_sol']:,} SOL", t)
t = re.sub(r"\*\*Fetch date:\*\* [^\n]*",
           f"**Fetch date:** {now}. The next hourly candle was still open at fetch time and is **excluded** — every row in this dataset is a closed candle.", t)
readme.write_text(t)
print(f"manifest updated: {len(rows)} rows, last {times[-1]} close ${closes[-1]:.2f}")
