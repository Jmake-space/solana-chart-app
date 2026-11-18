#!/usr/bin/env python3
"""Forecast baseline v3 — drift30 + tunable volatility parameter.
Supersedes v2 (drift30, no vol). v1/v2 code and docs are kept intact.

Tunable vol parameter (config.json — edit it, re-run this script):
  VOL_ALPHA (default 1.0): drift damping strength.
    damp = clamp((VOL_REF / vol30) ** VOL_ALPHA, VOL_DAMP_MIN, VOL_DAMP_MAX)
    vol30 = trailing std of daily log returns over VOL_WINDOW_DAYS (30d),
    VOL_REF = 3.0% (near the full-sample median, 3.03%).
    ALPHA=0  -> damp=1 always -> exactly v2.
    ALPHA=1  -> inverse-vol damping: at vol30 6% damp=0.5, at 3% damp=1.
    High vol -> trust the drift less -> forecast moves toward naive.
    Low vol  -> damp capped at 1, never amplifies the drift.
  Regime (tracking/display only, thresholds in config):
    low <2.5% / normal 2.5-3.5% / high >3.5% trailing vol30.
    Thresholds sit near the full-sample quartiles (p25 2.41%, p75 3.50%).

What the grid actually showed (full backtest in models/baseline_v3.md):
  MAE full year: alpha 0 $2.22 -> 0.5 $2.21 -> 1.0 $2.20 -> 1.5 $2.20 -> 2.0 $2.20
  MAE 90d:      $2.37 -> $2.37 -> $2.36 -> $2.36 -> $2.35
  Direction unchanged (49.6% / 55.6% / 60%). High-vol MAE $3.25 -> $3.20.
  The effect is SMALL (~1% MAE) because drift30 is already small and vol
  only ranges 2-5.5%. ALPHA=1.0 is chosen as the natural inverse-vol scaling,
  not the grid maximum — alpha 2.0 gains nothing more.
  Band scaling by vol was TESTED and REJECTED: 95% band coverage full year
  fixed 94.3% vs vol-scaled 93.4% (90d: 92.2% vs 91.1%). vol30 predicts
  next-day |return| only weakly (corr 0.15), so fixed bands stay.

Forward forecast: drift30 x damp(today) x 0.85^(h-1) damping.
Bands are LOG-SPACE (fixed 2026-11-18 after the user flagged the old dollar
bands): low/high = point x exp(-/+ 1.96 x log-resid-SD x sqrt(h)), log-resid-SD
from the 90d walk-forward backtest (~3.2%/day). The old bands were symmetric
in dollars (+-1.96 x $3.18 x sqrt(h)): at 30d that gave $36-$104, a -52%
downside — implausible, because a dollar SD estimated when SOL was $140
does not scale down as price falls. Log-space bands are multiplicative and
asymmetric in dollars (+30d $50-$99), and coverage is as good or better
(94.3% full-year / 94.4% 90d vs 94.3% / 92.2% for the dollar bands).
Vol series (vol7, vol30, ATR14, volume ratio, regime) is written for every
day so the app can chart volatility — see forecast.json "vol_series".
Inputs: daily closes only. No trading, no orders, no wallet actions.
"""
import csv, json, math, statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

BASE = Path.home() / "workspace/solana"
CFG = json.loads((BASE / "config.json").read_text())
VOL_WINDOW = CFG["vol_window_days"]; VOL_REF = CFG["vol_ref_pct"] / 100
ALPHA = CFG["vol_alpha"]; DAMP_MIN = CFG["vol_damp_min"]; DAMP_MAX = CFG["vol_damp_max"]
DRIFT_W = CFG["drift_window_days"]; REGIME_LOW = CFG["regime_low_pct"] / 100
REGIME_HIGH = CFG["regime_high_pct"] / 100

rows = []
with open(BASE / "dataset/daily/sol_ohlcv_daily.csv") as f:
    for r in csv.DictReader(f):
        rows.append({"date": r["timestamp"][:10], "o": float(r["open"]), "h": float(r["high"]),
                     "l": float(r["low"]), "c": float(r["close"]), "v": float(r["volume"])})
rows.sort(key=lambda x: x["date"])
dates = [r["date"] for r in rows]
closes = [r["c"] for r in rows]
lr = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]

def vol_at(i, window):
    # Trailing vol THROUGH day i (includes day i's return). For display and
    # for the current context (last day, all data known). NOT for prediction.
    s = lr[i-window:i] if i >= window else lr[:i]
    return statistics.pstdev(s) if len(s) > 1 else VOL_REF
def vol_before(i, window):
    # Trailing vol strictly BEFORE day i — the vol known when predicting day i.
    # vol_at(i) includes lr[i-1], the return ON day i: using it in the backtest
    # was a one-day look-ahead leak (fixed 2026-11-17). vol_before(len(closes))
    # == vol_at(len(closes)-1): all returns through the last close.
    s = lr[max(0, i-window-1):i-1] if i >= 2 else lr[:i]
    return statistics.pstdev(s) if len(s) > 1 else VOL_REF
def regime(v):
    return "low" if v < REGIME_LOW else "high" if v > REGIME_HIGH else "normal"
def damp_at(i):
    v = vol_before(i, VOL_WINDOW)
    return min(DAMP_MAX, max(DAMP_MIN, (VOL_REF / v) ** ALPHA)) if v > 0 else 1.0
def drift(hist, w=DRIFT_W):
    return statistics.mean([hist[j]/hist[j-1]-1 for j in range(len(hist)-w+1, len(hist))])
def predict_vol(hist, i):
    return hist[-1] * (1 + drift(hist) * damp_at(i))
def naive(hist): return hist[-1]

def backtest(predict_fn, start_idx):
    errs, ok, n, preds = [], 0, 0, []
    byreg = defaultdict(lambda: {"err": [], "ok": 0, "n": 0})
    for i in range(start_idx, len(closes)):
        pred = predict_fn(closes[:i], i); actual = closes[i]; prev = closes[i-1]
        errs.append(abs(pred - actual))
        rg = regime(vol_before(i, VOL_WINDOW))
        byreg[rg]["err"].append(abs(pred - actual))
        if pred != prev:
            n += 1
            ok += 1 if (pred - prev) * (actual - prev) > 0 else 0
            byreg[rg]["n"] += 1
            byreg[rg]["ok"] += 1 if (pred - prev) * (actual - prev) > 0 else 0
        preds.append({"date": dates[i], "actual": round(actual, 2), "pred": round(pred, 2),
                      "regime": rg, "vol30_pct": round(vol_at(i, VOL_WINDOW)*100, 2)})
    mae = statistics.mean(errs)
    return {"mae_usd": round(mae, 3),
            "mae_pct": round(mae / statistics.mean(closes[start_idx:]) * 100, 2),
            "rmse_usd": round(math.sqrt(statistics.mean([e*e for e in errs])), 3),
            "directional_accuracy_pct": round(100*ok/n, 1) if n else None,
            "n": len(closes) - start_idx, "preds": preds,
            "per_regime": {k: {"mae_usd": round(statistics.mean(v["err"]), 2), "n": len(v["err"]),
                               "directional_accuracy_pct": round(100*v["ok"]/v["n"], 1) if v["n"] else None}
                           for k, v in sorted(byreg.items())}}

# Grid over ALPHA, for the doc (uses the same harness)
def backtest_alpha(alpha, start_idx):
    global ALPHA
    old = ALPHA; ALPHA = alpha
    r = backtest(predict_vol, start_idx)
    ALPHA = old
    return r
grid = {}
for alpha in [0, 0.5, 1.0, 1.5, 2.0]:
    grid[str(alpha)] = {}
    for wname, start in [("last_30d", len(closes)-30), ("last_90d", len(closes)-90),
                         ("full_year", 31)]:
        r = backtest_alpha(alpha, start)
        grid[str(alpha)][wname] = {k: v for k, v in r.items() if k not in ("preds", "per_regime")}
    print(f"alpha {alpha}: " + "; ".join(
        f"{w} MAE ${grid[str(alpha)][w]['mae_usd']}" for w in grid[str(alpha)]))

# Main backtest at the configured ALPHA
extended = {}
for wname, start in [("last_30d", len(closes)-30), ("last_90d", len(closes)-90),
                     ("full_year_from_day_31", 31)]:
    r = backtest(predict_vol, start)
    extended[wname] = {k: v for k, v in r.items() if k != "preds"}
    print(f"{wname}: MAE ${r['mae_usd']} RMSE ${r['rmse_usd']} dir {r['directional_accuracy_pct']}% per-regime {extended[wname]['per_regime']}")

# Vol series for the app (every day, trailing, no look-ahead)
vol_series = []
for i in range(len(rows)):
    v30 = vol_at(i, VOL_WINDOW); v7 = vol_at(i, 7)
    trs = []
    for j in range(max(1, i-13), i+1):
        trs.append(max(rows[j]["h"]-rows[j]["l"], abs(rows[j]["h"]-rows[j-1]["c"]), abs(rows[j]["l"]-rows[j-1]["c"])))
    atr = (statistics.mean(trs) / rows[i]["c"] * 100) if trs else (rows[i]["h"]-rows[i]["l"])/rows[i]["c"]*100
    med = statistics.median([r["v"] for r in rows[max(0, i-30):i]]) if i > 0 else rows[i]["v"]
    vol_series.append({"date": dates[i], "vol7_pct": round(v7*100, 2),
                       "vol30_pct": round(v30*100, 2), "atr14_pct": round(atr, 2),
                       "volume_ratio_30d": round(rows[i]["v"]/med, 2) if med else None,
                       "regime": regime(v30)})

# Forward forecast
last = closes[-1]
d30 = drift(closes)
damp_now = damp_at(len(closes))
v_now = vol_at(len(closes)-1, VOL_WINDOW)  # through the last close: 30 returns (vol_at(len) used 29)
resid = [p["actual"] - p["pred"] for p in backtest(predict_vol, len(closes)-90)["preds"]]
resid_sd = statistics.pstdev(resid)
logresid = [math.log(p["actual"] / p["pred"]) for p in backtest(predict_vol, len(closes)-90)["preds"]]
resid_sd_log = statistics.pstdev(logresid)
print(f"current vol30 {v_now*100:.2f}% regime {regime(v_now)} damp {damp_now:.3f} drift30 {d30*100:.3f}% resid SD ${resid_sd:.2f} log-resid SD {resid_sd_log*100:.2f}%")
forecast_days = []
for h in [1, 2, 3, 7, 14, 30]:
    p = last
    for step in range(1, h+1):
        # damp applies to the day-1 drift; multi-day damping 0.85^(h-1) as in v1/v2
        p *= (1 + d30 * damp_now * (0.85 ** (step-1)))
    # log-space band: multiplicative, asymmetric in dollars, never near zero
    half_log = 1.96 * resid_sd_log * math.sqrt(h)
    lo, hi = p * math.exp(-half_log), p * math.exp(half_log)
    forecast_days.append({"horizon_days": h,
        "date": (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=h)).strftime("%Y-%m-%d"),
        "forecast_close_usd": round(p, 2),
        "low_95_usd": round(lo, 2), "high_95_usd": round(hi, 2)})
    print(f"  +{h}d {forecast_days[-1]['date']}: ${p:.2f} (${lo:.2f}-${hi:.2f})")

out = {
    "model": "baseline_v3_drift30_vol",
    "label": "Experimental baseline — NOT financial advice. No trading, no orders, no wallet actions.",
    "description": "Next-day close = last close x (1 + drift30 x vol-damp), where vol-damp = clamp((3.0% / trailing-30d vol) ^ VOL_ALPHA, 0.25, 1.0). VOL_ALPHA is tunable in config.json (default 1.0; 0 = v2 exactly). Multi-day: same drift damped by 0.85^(h-1)/day. Bands are log-space: point x exp(+-1.96 x log-residual SD x sqrt(h)) — multiplicative, so the downside stays plausible; vol-scaling the bands was tested and rejected (see limits).",
    "supersedes": "baseline_v2_drift30 (scripts/forecast_v2.py, models/baseline_v2.md — kept intact)",
    "config": CFG,
    "inputs": {"source_file": "dataset/daily/sol_ohlcv_daily.csv", "daily_closes": len(rows),
               "first_date": dates[0], "last_date": dates[-1], "last_close_usd": round(last, 2)},
    "context": {"ma7_usd": round(statistics.mean(closes[-7:]), 2),
                "ma30_usd": round(statistics.mean(closes[-30:]), 2),
                "drift_30d_pct_per_day": round(d30*100, 3),
                "drift_14d_pct_per_day": round(drift(closes, 14)*100, 3),
                "drift_3d_pct_per_day": round(drift(closes, 3)*100, 3),
                "vol30_pct": round(v_now*100, 2), "vol7_pct": round(vol_at(len(closes)-1, 7)*100, 2),
                "atr14_pct": round(vol_series[-1]["atr14_pct"], 2),
                "volume_ratio_30d": vol_series[-1]["volume_ratio_30d"],
                "regime": regime(v_now), "vol_damp": round(damp_now, 3),
                "daily_vol_30d_pct": round(v_now*100, 2),
                "resid_sd_90d_usd": round(resid_sd, 2),
                "resid_sd_log_90d_pct": round(resid_sd_log*100, 2)},
    "vol_alpha_grid": grid,
    "backtest": {"method": "1-day-ahead, walk-forward, no look-ahead; vol and damp use only data before the predicted day",
                 "windows": extended},
    "vol_series": vol_series,
    "forecast": forecast_days,
    "limits": [
        "Vol damping helps only a little: MAE full year $2.22 (alpha 0) -> $2.20 (alpha 1.0-2.0); 90d $2.37 -> $2.36; direction unchanged. It is a small, principled tilt, not a breakthrough.",
        "Bands are log-space: point x exp(+-1.96 x log-resid-SD x sqrt(h)); 95% coverage 94.3% full-year / 94.4% 90d. The old symmetric dollar bands implied a -52% downside at 30d ($36) and were replaced 2026-11-18 — a dollar SD estimated when SOL was $140 does not scale down as price falls. Vol-scaling the bands was tested and rejected (coverage 93.4% vs 94.3% for dollar bands).",
        "Regime thresholds (2.5% / 3.5%) sit near full-sample quartiles, so they are descriptive, not discovered out-of-sample; per-regime n is small in the 90d window (high-vol n=10).",
        "Current regime is normal (vol30 3.08%), so damp is ~0.97 and v3 barely differs from v2 today — the parameter matters in high-vol periods, not today.",
        "No drift variant beats naive on MAE over 90d or the full year (naive $2.33 / $2.17 vs v3 $2.36 / $2.20). Treat the point forecast as weak; the band is the honest statement.",
        "Replaceable / tunable: edit config.json (VOL_ALPHA, VOL_WINDOW_DAYS, VOL_REF_PCT, regime thresholds) and re-run forecast_v3.py; the grid is recomputed each run.",
    ],
}
(BASE / "forecast.json").write_text(json.dumps(out, indent=2))
print("wrote forecast.json (v3)")
