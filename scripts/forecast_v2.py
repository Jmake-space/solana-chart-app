#!/usr/bin/env python3
"""Forecast baseline v2 — drift30, chosen by extended backtest, not by today's move.
Replaces v1 (drift14) as the live baseline. v1 code/doc are kept intact
(scripts/forecast.py, models/baseline_v1.md) for comparison.

Why the change (2026-11-17, live $75.12 vs v1 +1d $72.68):
- v1 predicted Nov 17 close $70.21; actual $74.07 (error -$3.86, worse than
  naive -$2.49). Nov 17 was a +3.5% bounce day (open $71.58 -> close $74.07)
  after the Nov 14 crash to $70.28. A 14-day drift cannot catch a 1-day
  reversal: it still averages in the crash.
- $75.12 is the OPEN 23:00 UTC hourly candle, not a daily close — the Nov 18
  daily-close forecast cannot be scored yet. But the direction miss is real.
- Extended backtest (below): NO drift window beats naive on MAE over 90d or
  the full year. drift30 is the least-bad drift in every window and the ONLY
  drift that beats naive anywhere (last 30d: $1.93 vs $1.98). drift3 — the
  window that would "catch" today (+0.92%/day, +1d $74.75) — is the WORST on
  MAE ($2.75 full year, $3.07 90d). Switching to drift3 would be curve-fitting
  to one day. So v2 = drift30, and the fast 3-day drift is shown only as a
  secondary momentum indicator, not as the point forecast.

Model v2: next-day close = last close x (1 + mean daily return over prior
30 days). Multi-day: same drift damped by 0.85^(h-1)/day (v1 rule, kept).
Bands: +-1.96 x residual SD x sqrt(h), residual SD from the drift30 90-day
walk-forward backtest.
Inputs: daily closes only, dataset/daily/sol_ohlcv_daily.csv. No trading.
"""
import csv, json, math, statistics
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "workspace/solana"
rows = []
with open(BASE / "dataset/daily/sol_ohlcv_daily.csv") as f:
    for r in csv.DictReader(f):
        rows.append({"date": r["timestamp"][:10], "o": float(r["open"]), "h": float(r["high"]),
                     "l": float(r["low"]), "c": float(r["close"]), "v": float(r["volume"])})
rows.sort(key=lambda x: x["date"])
dates = [r["date"] for r in rows]
closes = [r["c"] for r in rows]

def drift_fn(w):
    return lambda hist: hist[-1] * (1 + statistics.mean(
        [hist[i] / hist[i-1] - 1 for i in range(len(hist) - w + 1, len(hist))]))
def naive(hist): return hist[-1]
def ma7(hist): return statistics.mean(hist[-7:])

def backtest(predict, start_idx):
    errs, ok, n, preds = [], 0, 0, []
    for i in range(start_idx, len(closes)):
        pred = predict(closes[:i]); actual = closes[i]; prev = closes[i-1]
        errs.append(abs(pred - actual))
        if pred != prev:
            n += 1
            ok += 1 if (pred - prev) * (actual - prev) > 0 else 0
        preds.append({"date": dates[i], "actual": round(actual, 2), "pred": round(pred, 2)})
    mae = statistics.mean(errs)
    return {"mae_usd": round(mae, 3),
            "mae_pct": round(mae / statistics.mean(closes[start_idx:]) * 100, 2),
            "rmse_usd": round(math.sqrt(statistics.mean([e*e for e in errs])), 3),
            "directional_accuracy_pct": round(100*ok/n, 1) if n else None,
            "n": len(closes) - start_idx, "preds": preds}

MODELS = {"naive (tomorrow = today)": naive, "drift3": drift_fn(3),
          "drift7": drift_fn(7), "drift14 (v1)": drift_fn(14),
          "drift30 (v2 baseline)": drift_fn(30), "MA7": ma7}
WINDOWS = {"last_30d": len(closes) - 30, "last_90d": len(closes) - 90,
           "full_year_from_day_31": 31}
extended = {}
for wname, start in WINDOWS.items():
    extended[wname] = {}
    for mname, fn in MODELS.items():
        r = backtest(fn, start)
        extended[wname][mname] = {k: v for k, v in r.items() if k != "preds"}
    print(f"{wname}: " + "; ".join(
        f"{m} MAE ${extended[wname][m]['mae_usd']} dir {extended[wname][m]['directional_accuracy_pct']}%"
        for m in MODELS))

# 30-day blocks over the last 90d, drift30 vs drift14 vs naive (MAE)
blocks = []
for s in range(len(closes) - 90, len(closes), 30):
    block = {"window": f"{dates[s]}..{dates[min(s+29, len(closes)-1)]}"}
    for mname, fn in [("naive", naive), ("drift14 (v1)", drift_fn(14)),
                      ("drift30 (v2)", drift_fn(30))]:
        errs = [abs(fn(closes[:i]) - closes[i]) for i in range(s, min(s+30, len(closes)))]
        block[mname] = round(statistics.mean(errs), 2)
    blocks.append(block)
print("blocks:", blocks)

# Miss log: v1 prediction for Nov 17 vs actual
i17 = dates.index("2026-11-17")
v1_pred_nov17 = round(drift_fn(14)(closes[:i17]), 2)
miss = {"date": "2026-11-17", "v1_pred_close_usd": v1_pred_nov17,
        "actual_close_usd": closes[i17], "error_usd": round(v1_pred_nov17 - closes[i17], 2),
        "naive_pred_close_usd": closes[i17-1],
        "naive_error_usd": round(closes[i17-1] - closes[i17], 2),
        "note": "Bounce day: open $71.58, low $71.07, high $74.34, close $74.07 (+3.5% on the day) after Nov 14 crash close $70.28."}

# Fast indicators (not the point forecast)
def drift_w(w):
    rets = [closes[i]/closes[i-1]-1 for i in range(len(closes)-w+1, len(closes))]
    return statistics.mean(rets)
hrows = []
for fp in sorted((BASE / "dataset").glob("year=*/month=*/sol_ohlcv_*.csv")):
    with open(fp) as fh:
        for r in csv.DictReader(fh):
            hrows.append((r["timestamp"], float(r["close"])))
hrows.sort()
chg_24h = hrows[-1][1] / hrows[-25][1] - 1
lr = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]
vol30 = statistics.pstdev(lr[-30:]) * 100
vol7 = statistics.pstdev(lr[-7:]) * 100
# ATR14 %
trs = []
for j in range(len(rows)-14, len(rows)):
    trs.append(max(rows[j]["h"]-rows[j]["l"], abs(rows[j]["h"]-rows[j-1]["c"]), abs(rows[j]["l"]-rows[j-1]["c"])))
atr14 = statistics.mean(trs) / closes[-1] * 100

# Forward forecast, drift30, damped
last = closes[-1]
drift30 = drift_w(30)
resid = [p["actual"] - p["pred"] for p in backtest(drift_fn(30), len(closes)-90)["preds"]]
resid_sd = statistics.pstdev(resid)
print(f"drift30 {drift30*100:.3f}%/day resid SD (90d) ${resid_sd:.2f} vol30 {vol30:.2f}% vol7 {vol7:.2f}% ATR14 {atr14:.2f}% 24h hourly {chg_24h*100:+.2f}%")
forecast_days = []
for h in [1, 2, 3, 7, 14, 30]:
    p = last
    for step in range(1, h+1):
        p *= (1 + drift30 * (0.85 ** (step-1)))
    half = 1.96 * resid_sd * math.sqrt(h)
    forecast_days.append({"horizon_days": h,
        "date": (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=h)).strftime("%Y-%m-%d"),
        "forecast_close_usd": round(p, 2),
        "low_95_usd": round(max(p-half, 0), 2), "high_95_usd": round(p+half, 2)})
    print(f"  +{h}d {forecast_days[-1]['date']}: ${p:.2f} (${max(p-half,0):.2f}-${p+half:.2f})")

out = {
    "model": "baseline_v2_drift30",
    "label": "Experimental baseline — NOT financial advice. No trading, no orders, no wallet actions.",
    "description": "Next-day close = last close x (1 + mean daily return over prior 30 days). Multi-day: same drift damped by 0.85^(h-1)/day. Chosen by extended backtest (see backtest_extended), not by today's move. Fast 3-day drift is shown only as a momentum indicator.",
    "supersedes": "baseline_v1_drift14 (scripts/forecast.py, models/baseline_v1.md — kept intact for comparison)",
    "inputs": {"source_file": "dataset/daily/sol_ohlcv_daily.csv", "daily_closes": len(rows),
               "first_date": dates[0], "last_date": dates[-1], "last_close_usd": round(last, 2)},
    "context": {"ma7_usd": round(statistics.mean(closes[-7:]), 2),
                "ma30_usd": round(statistics.mean(closes[-30:]), 2),
                "drift_30d_pct_per_day": round(drift30*100, 3),
                "drift_14d_pct_per_day": round(drift_w(14)*100, 3),
                "drift_3d_pct_per_day": round(drift_w(3)*100, 3),
                "daily_vol_30d_pct": round(vol30, 2), "daily_vol_7d_pct": round(vol7, 2),
                "atr14_pct": round(atr14, 2),
                "hourly_change_24h_pct": round(chg_24h*100, 2),
                "resid_sd_90d_usd": round(resid_sd, 2)},
    "miss_log": miss,
    "backtest": {"method": "1-day-ahead, walk-forward, no look-ahead",
                 "windows": extended, "blocks_last_90d": blocks},
    "backtest_extended": extended,
    "forecast": forecast_days,
    "limits": [
        "No drift window beats naive on MAE over 90 days or the full year (naive $2.33 / $2.17; drift30 $2.37 / $2.22). v2 is the least-bad drift, not a proven edge.",
        "drift30 still lags reversals — it predicted down for Nov 18 while the last 24h hourly is +3.28% and live price is $75.12. The 3-day drift (+0.92%/day) shows the turn; it is the worst backtest performer, so it is an indicator only.",
        "Live $75.12 is an open hourly candle, not a daily close; the Nov 18 forecast can only be scored at the Nov 18 daily close.",
        "30-day backtest window is one regime (falling market); 90-day and full-year windows are broader but still one asset, one year.",
        "No volume, macro, on-chain or order-book inputs; bands are rough residual intervals, not calibrated probabilities.",
        "Replaceable: swap predict_fn in forecast_v2.py (or forecast.py for v1) and re-run the same backtest harness.",
    ],
}
(BASE / "forecast.json").write_text(json.dumps(out, indent=2))
print("wrote forecast.json (v2)")
