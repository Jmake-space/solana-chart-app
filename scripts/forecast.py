#!/usr/bin/env python3
"""Forecast baseline v1 — explainable, local-CSV only, no trading.
Model (baseline): 14-day drift.
  forecast(t+1) = close(t) * (1 + mean daily simple return over prior 14 days)
  Multi-day: compound the same drift, capped by recent volatility.
Comparators (same held-out window): naive (tomorrow = today) and MA7 (tomorrow = 7d mean close).
Held-out: last 30 daily closes, 2026-10-19 .. 2026-11-17 (30 predictions, 1-day ahead,
  each using only data available before that day — no look-ahead).
Inputs: ~/workspace/solana/dataset/daily/sol_ohlcv_daily.csv only.
Output: ~/workspace/solana/forecast.json  +  ~/workspace/solana/models/baseline_v1.md
"""
import csv, json, math, statistics
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "workspace/solana"
daily = []
with open(BASE / "dataset/daily/sol_ohlcv_daily.csv") as f:
    for r in csv.DictReader(f):
        daily.append((r["timestamp"][:10], float(r["close"])))
daily.sort()
dates = [d for d, _ in daily]
closes = [c for _, c in daily]
print(f"daily closes: {len(daily)}  {dates[0]} .. {dates[-1]}  last ${closes[-1]:.2f}")

def backtest(predict_fn, holdout_n=30):
    """predict_fn(history_closes) -> next-day forecast. history excludes target day."""
    errs, dirs_ok, dirs_n, preds = [], 0, 0, []
    start = len(closes) - holdout_n
    for i in range(start, len(closes)):
        hist = closes[:i]
        pred = predict_fn(hist)
        actual = closes[i]
        errs.append(abs(pred - actual))
        # directional: predicted move vs actual move from previous close.
        # A model that predicts no move (naive) has no direction — recorded as None.
        prev = closes[i-1]
        if pred != prev:
            dirs_n += 1
            if (pred - prev) * (actual - prev) > 0:
                dirs_ok += 1
        preds.append({"date": dates[i], "actual": round(actual, 2), "pred": round(pred, 2)})
    mae = statistics.mean(errs)
    rmse = math.sqrt(statistics.mean([e*e for e in errs]))
    return {"mae_usd": round(mae, 3), "mae_pct": round(mae / statistics.mean(closes[start:]) * 100, 2),
            "rmse_usd": round(rmse, 3),
            "directional_accuracy_pct": round(100*dirs_ok/dirs_n, 1) if dirs_n else None,
            "n": holdout_n, "preds": preds}

def naive(hist): return hist[-1]
def ma7(hist): return statistics.mean(hist[-7:])
def drift14(hist):
    rets = [(hist[i]/hist[i-1] - 1) for i in range(len(hist)-13, len(hist))]
    return hist[-1] * (1 + statistics.mean(rets))
def drift14_ma7_blend(hist):
    return 0.5*drift14(hist) + 0.5*ma7(hist)

holdout_start = dates[len(dates)-30]
results = {
    "naive (tomorrow = today)": backtest(naive),
    "MA7 (tomorrow = 7-day mean)": backtest(ma7),
    "drift14 (baseline)": backtest(drift14),
    "drift14+MA7 blend": backtest(drift14_ma7_blend),
}
for k, v in results.items():
    print(f"{k}: MAE ${v['mae_usd']} ({v['mae_pct']}%) RMSE ${v['rmse_usd']} dir {v['directional_accuracy_pct']}% n={v['n']}")

# --- forward forecast with the baseline (drift14), trained on ALL data ---
last = closes[-1]
rets14 = [(closes[i]/closes[i-1]-1) for i in range(len(closes)-13, len(closes))]
drift = statistics.mean(rets14)
# residual std from backtest (1-day errors) as interval width; daily vol over last 30d
resid = [p["actual"]-p["pred"] for p in results["drift14 (baseline)"]["preds"]]
resid_sd = statistics.pstdev(resid) if len(resid) > 1 else 1.0
daily_vol = statistics.pstdev([(closes[i]/closes[i-1]-1) for i in range(len(closes)-30, len(closes))])
print(f"14d mean daily return (drift): {drift*100:.3f}%/day  resid SD ${resid_sd:.2f}  30d daily vol {daily_vol*100:.2f}%")

forecast_days = []
price = last
# Damped drift for multi-day horizons: undamped compounding of the current
# -1.93%/day selloff would imply $41 in 30 days, which is not a credible
# forecast — it extrapolates a 14-day crash linearly. So the daily drift is
# damped by 0.85^(h-1): the trend fades toward flat. Day 1 is undamped.
for h in [1, 2, 3, 7, 14, 30]:
    p = last
    for step in range(1, h + 1):
        p *= (1 + drift * (0.85 ** (step - 1)))
    half = 1.96 * resid_sd * math.sqrt(h)
    forecast_days.append({
        "horizon_days": h,
        "date": (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=h)).strftime("%Y-%m-%d"),
        "forecast_close_usd": round(p, 2),
        "low_95_usd": round(max(p-half, 0), 2),
        "high_95_usd": round(p+half, 2),
    })
    print(f"  +{h}d {forecast_days[-1]['date']}: ${p:.2f}  (95% ~ ${max(p-half,0):.2f}–${p+half:.2f})")

ma7 = statistics.mean(closes[-7:]); ma30 = statistics.mean(closes[-30:])
out = {
    "model": "baseline_v1_drift14",
    "label": "Experimental baseline — NOT financial advice. No trading, no orders, no wallet actions.",
    "description": "Next-day close = last close x (1 + mean daily return over prior 14 days). Multi-day: same drift compounded with damping 0.85^(h-1) per day, so the trend fades toward flat instead of extrapolating a crash linearly. Inputs: daily closes from the local dataset only.",
    "inputs": {"source_file": "dataset/daily/sol_ohlcv_daily.csv", "daily_closes": len(daily),
               "first_date": dates[0], "last_date": dates[-1], "last_close_usd": round(last, 2)},
    "context": {"ma7_usd": round(ma7, 2), "ma30_usd": round(ma30, 2),
                "drift_14d_pct_per_day": round(drift*100, 3),
                "daily_vol_30d_pct": round(daily_vol*100, 2),
                "resid_sd_1d_usd": round(resid_sd, 2)},
    "backtest": {"held_out_window": f"{holdout_start} .. {dates[-1]}", "n_days": 30,
                 "method": "1-day-ahead, walk-forward, no look-ahead",
                 "models": {k: {kk: vv for kk, vv in v.items() if kk != "preds"} for k, v in results.items()},
                 "baseline_preds": results["drift14 (baseline)"]["preds"]},
    "forecast": forecast_days,
    "limits": [
        "SOL fell 47% over this 12-month window; a 14-day drift extrapolates the recent trend and will lag reversals.",
        "Backtest is 30 days only, in one regime — MAE/directional accuracy will not generalise to a different regime.",
        "No volume, volatility regime, macro, on-chain or order-book inputs; no seasonality (daily data has no strong weekly cycle checked).",
        "95% band is a rough residual-based interval, not a calibrated probability.",
        "Replaceable: see models/baseline_v1.md — swap predict_fn in forecast.py with e.g. ARIMA/ETS and re-run the same backtest harness.",
    ],
}
(BASE / "forecast.json").write_text(json.dumps(out, indent=2))
print("wrote forecast.json")
