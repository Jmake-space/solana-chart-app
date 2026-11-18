#!/usr/bin/env python3
"""Daily OKX SOL ATM implied-vol snapshot collector.

Appends one row per expiry (nearest + next) to ~/workspace/solana/iv_series.csv,
once per UTC day. Called from sync_hourly.sh after the manifest update, before
the Pi sync — so the series rides along to pi5d05 with the rest of the tree.

Design constraints (user decision 2026-11-17, build the free subset, no paid
source): OKX public REST only, no API key. ATM strikes only — deep OTM strikes
run 80-97% IV vs ~70% ATM, so the series must be ATM-only to be comparable
day to day. IV is computed, not quoted: Black-Scholes inversion from bid/ask
mids, r=0, T=days/365 (same method as okx_iv_snapshot.py).

This step MUST NEVER fail the hourly sync: on any error (OKX down/blocked,
empty chain, missing ATM) it logs "IV SKIP: ..." and exits 0. It also no-ops
when today's rows already exist, so repeated hourly runs are safe.
Use --dry-run to fetch live and print the ATM IVs without writing anything.
"""
import csv, json, math, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path.home() / "workspace/solana"
SERIES = BASE / "iv_series.csv"
SNAP_DIR = BASE / "iv_snapshots"
HEADER = ["date", "snapshot_ts_utc", "spot_usd", "expiry", "days_to_expiry",
          "rank", "atm_call_strike", "atm_call_iv_pct", "atm_call_mid",
          "atm_put_strike", "atm_put_iv_pct", "atm_put_mid"]
OKX = "https://www.okx.com/api/v5"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, sigma, cp):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * N(d1) - K * N(d2) if cp == "C" else K * N(-d2) - S * N(-d1)


def iv(S, K, T, px, cp):
    lo, hi = 0.01, 5.0
    if bs(S, K, T, hi, cp) < px:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if bs(S, K, T, mid, cp) < px:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def collect():
    """Fetch the live chain, return (spot, ts, rows) where rows are the
    nearest + next expiry ATM dicts. Raises on any fetch/parse problem."""
    idx = get(f"{OKX}/market/index-tickers?instId=SOL-USD")
    S = float(idx["data"][0]["idxPx"])
    tick = get(f"{OKX}/market/tickers?instType=OPTION&uly=SOL-USD")
    inst = get(f"{OKX}/public/instruments?instType=OPTION&uly=SOL-USD")
    exp = {x["instId"]: int(x["expTime"]) / 1000 for x in inst["data"]}
    stk = {x["instId"]: float(x["stk"]) for x in inst["data"]}
    typ = {x["instId"]: x["optType"] for x in inst["data"]}
    now = datetime.now(timezone.utc).timestamp()
    ts = datetime.now(timezone.utc).isoformat()

    # full-chain rows (same shape as okx_iv_snapshot_2026-11-18.json)
    chain = []
    by_expiry = {}
    for t in tick["data"]:
        iid = t["instId"]
        if iid not in exp or not t.get("bidPx") or not t.get("askPx"):
            continue
        mid = (float(t["bidPx"]) + float(t["askPx"])) / 2
        T = (exp[iid] - now) / 86400
        if T <= 0:
            continue
        v = iv(S, stk[iid], T / 365, mid, typ[iid])
        if v is None:
            continue
        chain.append([iid, typ[iid], stk[iid], round(T, 2), round(mid, 3),
                      round(v * 100, 1)])
        expiry = datetime.fromtimestamp(exp[iid], timezone.utc).strftime("%Y-%m-%d")
        by_expiry.setdefault(expiry, []).append(
            (typ[iid], stk[iid], round(T, 2), round(mid, 3), round(v * 100, 1)))
    if not chain:
        raise RuntimeError("empty option chain (no usable bid/ask)")
    chain.sort(key=lambda r: (r[3], abs(r[2] - S)))

    rows = []
    for rank, expiry in zip(("nearest", "next"), sorted(by_expiry)):
        legs = by_expiry[expiry]
        call = min((l for l in legs if l[0] == "C"), key=lambda l: abs(l[1] - S),
                   default=None)
        put = min((l for l in legs if l[0] == "P"), key=lambda l: abs(l[1] - S),
                  default=None)
        if call is None or put is None:
            continue
        rows.append({"expiry": expiry, "days_to_expiry": call[2], "rank": rank,
                     "atm_call_strike": call[1], "atm_call_iv_pct": call[4],
                     "atm_call_mid": call[3],
                     "atm_put_strike": put[1], "atm_put_iv_pct": put[4],
                     "atm_put_mid": put[3]})
    if not rows:
        raise RuntimeError("no expiry with both an ATM call and an ATM put")
    return S, ts, chain, rows


def main():
    dry_run = "--dry-run" in sys.argv
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not dry_run and SERIES.exists():
        with open(SERIES) as fh:
            if any(r["date"] == today for r in csv.DictReader(fh)):
                print(f"IV already collected for {today}, skipping")
                return 0
    try:
        S, ts, chain, rows = collect()
    except Exception as e:  # never fail the hourly sync
        print(f"IV SKIP: {type(e).__name__}: {e}")
        return 0
    for r in rows:
        print(f"IV {today} {r['rank']} expiry {r['expiry']} "
              f"({r['days_to_expiry']}d) spot ${S:.2f} "
              f"ATM call IV {r['atm_call_iv_pct']}% (K {r['atm_call_strike']}) "
              f"/ put IV {r['atm_put_iv_pct']}% (K {r['atm_put_strike']})")
    if dry_run:
        print("IV dry-run: nothing written")
        return 0
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    snap = {"checked_utc": ts, "spot_usd": S,
            "source": "OKX public REST tickers + instruments, Black-Scholes "
                      "inversion from bid/ask mids, r=0, T=days/365",
            "full_chain_rows": chain}
    (SNAP_DIR / f"okx_iv_{today}.json").write_text(json.dumps(snap, indent=1))
    new_file = not SERIES.exists()
    with open(SERIES, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({"date": today, "snapshot_ts_utc": ts, "spot_usd": S,
                        **r})
    print(f"IV appended {len(rows)} row(s) to {SERIES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
