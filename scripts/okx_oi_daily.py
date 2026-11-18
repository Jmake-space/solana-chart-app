#!/usr/bin/env python3
"""Daily OKX SOL open-interest + long/short collector (public REST, no key).

Collects, once per UTC day:
- OI history: GET /api/v5/rubik/stat/contracts/open-interest-history
  ?instType=SWAP&instId=SOL-USDT-SWAP&period=1D&limit=100
  Row: [ts_ms, oi_coin, oi_coin, oi_usd] — field 3 is the USD notional.
- L/S account ratio: GET /api/v5/rubik/stat/contracts/long-short-account-ratio-contract
  ?instId=SOL-USDT-SWAP&period=1D&limit=100 (period is case-sensitive: "1D").
  Row: [ts_ms, longShortRatio].

Why: OI daily % change is the first signal that BEATS naive on this
project (verified 2026-11-18, independent re-check of the research):
corr(prev-day dOI%, next-day return) +0.486 (Spearman +0.328, n=98);
v3+OI k=0.2 walk-forward 99d MAE $2.08 vs naive $2.28 / v3 $2.31;
out-of-sample (k frozen from fit half) $1.76 vs naive $1.86; high-vol
slice $2.51 vs v3 $2.94. The L/S ratio is collected for a 30-day re-test
only — it had the best in-sample numbers (corr -0.506, MAE $1.99) but
FAILED out-of-sample ($2.19 vs naive $1.86), so it stays OUT of v4.

The API caps history at 100 rows, so the series only grows if collected
daily — without this, the window never extends past 100 days.

Output: oi_series.csv (one row per day: date, oi_usd, oi_coin,
ls_ratio), raw JSONs under oi_snapshots/. No-ops when today's row exists.
Fail-safe: any error prints "OI SKIP: ..." and exits 0 — this must never
break the hourly sync. NOTE: OKX rejects urllib's default User-Agent
(403), so a browser UA header is required.
"""
import csv, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path.home() / "workspace/solana"
SERIES = BASE / "oi_series.csv"
SNAPS = BASE / "oi_snapshots"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def day_of(ts_ms):
    return datetime.fromtimestamp(int(ts_ms) / 1000, timezone.utc).strftime("%Y-%m-%d")

def main():
    try:
        SNAPS.mkdir(exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = {}
        if SERIES.exists():
            with open(SERIES) as f:
                for r in csv.DictReader(f):
                    existing[r["date"]] = r
        # OI history (100 rows max from the API — backfills on first run)
        oi = get("https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history"
                 "?instType=SWAP&instId=SOL-USDT-SWAP&period=1D&limit=100")
        if oi.get("code") != "0":
            raise RuntimeError(f"OI endpoint code {oi.get('code')}: {oi.get('msg')}")
        oi_rows = {day_of(r[0]): (float(r[3]), float(r[1])) for r in oi["data"]}
        # L/S account ratio (same window)
        ls = get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio-contract"
                 "?instId=SOL-USDT-SWAP&period=1D&limit=100")
        ls_rows = {}
        if ls.get("code") == "0":
            ls_rows = {day_of(r[0]): float(r[1]) for r in ls["data"]}
        else:
            print(f"OI WARN: L/S endpoint code {ls.get('code')}, collecting OI only")
        # raw snapshot (today's fetch, for re-derivation)
        with open(SNAPS / f"okx_oi_{today}.json", "w") as f:
            json.dump({"oi": oi["data"], "ls": ls.get("data", [])}, f)
        # merge: keep existing rows, fill gaps, add new days
        all_days = sorted(set(existing) | set(oi_rows))
        new_rows = 0
        with open(SERIES, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "oi_usd", "oi_coin", "ls_ratio"])
            for d in all_days:
                if d in existing and d not in oi_rows:
                    r = existing[d]
                    w.writerow([d, r["oi_usd"], r["oi_coin"], r.get("ls_ratio", "")])
                else:
                    usd, coin = oi_rows[d]
                    w.writerow([d, f"{usd:.2f}", f"{coin:.4f}",
                                f"{ls_rows[d]:.4f}" if d in ls_rows else existing.get(d, {}).get("ls_ratio", "")])
                    if d not in existing:
                        new_rows += 1
        print(f"OI OK: {len(all_days)} days in series ({min(all_days)} -> {max(all_days)}), +{new_rows} new")
        if today in existing and today in oi_rows:
            print(f"OI already collected for {today}, appended nothing new")
    except Exception as e:
        print(f"OI SKIP: {type(e).__name__}: {e}")
        return 0
    return 0

if __name__ == "__main__":
    sys.exit(main())
