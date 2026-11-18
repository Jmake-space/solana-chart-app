#!/usr/bin/env python3
"""Build ~/workspace/solana/chart-data.json for the chart app:
compact arrays, no live calls needed at render time.
hourly: [ts_ms, open, high, low, close, volume] for all 8,782 rows
daily:  [ts_ms, open, high, low, close, volume] for all 366 days
forecast: copied from forecast.json
"""
import csv, json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path.home() / "workspace/solana"
def load_hourly():
    rows = []
    for f in sorted((BASE / "dataset").glob("year=*/month=*/sol_ohlcv_*.csv")):
        with open(f) as fh:
            for r in csv.DictReader(fh):
                ts = int(datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
                rows.append([ts, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])])
    rows.sort()
    return rows
def load_daily():
    rows = []
    with open(BASE / "dataset/daily/sol_ohlcv_daily.csv") as fh:
        for r in csv.DictReader(fh):
            ts = int(datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
            rows.append([ts, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])])
    rows.sort()
    return rows

def load_weekly():
    rows = []
    with open(BASE / "dataset/weekly/sol_ohlcv_weekly.csv") as fh:
        for r in csv.DictReader(fh):
            ts = int(datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
            rows.append([ts, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])])
    rows.sort()
    return rows

hourly = load_hourly()
daily = load_daily()
weekly = load_weekly()
# Macro summary, derived from the weekly candles where computable; the
# analogue / RSI figures are from macro_3y_note.md (2026-11-18, 160 weeks).
_wcloses = [r[4] for r in weekly]
_macro = {
    "weekly_rows": len(weekly),
    "first_week": datetime.fromtimestamp(weekly[0][0] / 1000, timezone.utc).strftime("%Y-%m-%d"),
    "last_week": datetime.fromtimestamp(weekly[-1][0] / 1000, timezone.utc).strftime("%Y-%m-%d"),
    "last_weekly_close_usd": round(_wcloses[-1], 2),
    "ath_close_usd": round(max(_wcloses), 2),
    "ath_high_usd": round(max(r[2] for r in weekly), 2),
    "drawdown_from_ath_close_pct": round((_wcloses[-1] / max(_wcloses) - 1) * 100, 1),
    "ma50w_usd": round(sum(_wcloses[-50:]) / 50, 2),
    "ma100w_usd": round(sum(_wcloses[-100:]) / 100, 2),
    "weeks_below_70_close": sum(1 for c in _wcloses if c < 70),
    "weekly_rsi14": 53.1,
    "floor_69_70_is_artefact": True,
    "levels_above_usd": [93.62, 100.0],
    "levels_below_usd": [66.5, 59.0, 51.0],
    "analogues_n": 21,
    "fwd4w": {"median_pct": -3.5, "positive": "10/21", "gt_plus33pct": "3/21", "lt_minus20pct": "3/21"},
    "fwd8w": {"median_pct": 3.7, "positive": "13/21", "gt_plus33pct": "3/21", "lt_minus20pct": "2/21"},
    "back_to_100_pct_needed": 33,
    "back_to_100_probability": "about 1-in-7 by year-end",
    "nov_dec_read": "Flat-to-slightly-down into year-end, very wide dispersion: v3 ~$70 by mid-Dec; analogue medians ~$72 in 4 weeks, ~$78 in 8 weeks.",
    "source_note": "macro_3y_note.md",
}
forecast = json.loads((BASE / "forecast.json").read_text())
out = {
    "symbol": "SOLUSDT",
    "source": "Binance data-api.binance.vision SOLUSDT 1h",
    "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "first": datetime.fromtimestamp(hourly[0][0] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "last": datetime.fromtimestamp(hourly[-1][0] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "hourly_rows": len(hourly), "daily_rows": len(daily),
    "weekly_rows": len(weekly),
    "hourly": hourly, "daily": daily, "weekly": weekly, "macro": _macro, "forecast": forecast,
}
(BASE / "chart-data.json").write_text(json.dumps(out, separators=(",", ":")))
print(f"hourly {len(hourly)} daily {len(daily)} weekly {len(weekly)} bytes {(BASE/'chart-data.json').stat().st_size:,}")
