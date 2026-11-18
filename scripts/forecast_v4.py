#!/usr/bin/env python3
"""Forecast baseline v4 — v3 (drift30 + tunable vol) + OKX open-interest term.
Supersedes v3. v1/v2/v3 code and docs are kept intact.

The OI term (adopted 2026-11-18, verified independently of the research
that proposed it):
  pred = v3_pred x (1 + OI_K x dOI%),  OI_K = 0.2 (config.json),
  dOI% = previous-day change in OKX SOL-USDT-SWAP open interest (USD
  notional), i.e. the OI change ending on the last completed day before
  the day being predicted. Previous-day alignment only — a same-day
  feature would be look-ahead (the research's first draft made exactly
  that mistake and was corrected).

Evidence (OKX OI history, 100 rows max, 2026-08-10 -> 2026-11-17):
  corr(prev-day dOI%, next-day return) = +0.486 (Spearman +0.328, n=98);
  same-day +0.313 — the peak is at 1-day lead.
  Walk-forward 99d MAE: naive $2.28, v3 $2.31, v4 (k=0.2) $2.08,
  direction 57%. Out-of-sample (k frozen from the fit half): $1.76 vs
  naive $1.86, direction 60%. High-vol slice: $2.51 vs v3 $2.94.
  First signal in this project that beats naive — but on 99 days only
  (the API caps history at 100 rows), margin ~$0.20/day. Re-verify after
  30 fresh days of collection (scripts/okx_oi_daily.py).

The OI term applies to the DAY-1 step only in the multi-day forecast
(the signal is a 1-day lead; compounding it 30x would be wrong), then
the usual damped drift continues. If the OI series is missing or stale
(>3 days), the term is 0 and v4 == v3 exactly, and a warning is printed.
The L/S ratio is collected alongside OI but NOT used: best in-sample
numbers in the project (corr -0.506) yet fails out-of-sample ($2.19 vs
naive $1.86) — re-test in 30 days.

Bands stay log-space (v3 method), now from v4's own 90d log-residuals.
The weekly 12-week analogue outlook (forecast.json "weekly_12w") is
preserved across runs — it is written by scripts/weekly_outlook.py.
Inputs: daily closes + oi_series.csv. No trading, no orders, no wallet actions.
"""
import bisect, csv, json, math, statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

BASE = Path.home() / "workspace/solana"
CFG = json.loads((BASE / "config.json").read_text())
VOL_WINDOW = CFG["vol_window_days"]; VOL_REF = CFG["vol_ref_pct"] / 100
ALPHA = CFG["vol_alpha"]; DAMP_MIN = CFG["vol_damp_min"]; DAMP_MAX = CFG["vol_damp_max"]
DRIFT_W = CFG["drift_window_days"]; REGIME_LOW = CFG["regime_low_pct"] / 100
REGIME_HIGH = CFG["regime_high_pct"] / 100
OI_K = CFG.get("oi_k", 0.2)

rows = []
with open(BASE / "dataset/daily/sol_ohlcv_daily.csv") as f:
    for r in csv.DictReader(f):
        rows.append({"date": r["timestamp"][:10], "o": float(r["open"]), "h": float(r["high"]),
                     "l": float(r["low"]), "c": float(r["close"]), "v": float(r["volume"])})
rows.sort(key=lambda x: x["date"])
dates = [r["date"] for r in rows]
closes = [r["c"] for r in rows]
lr = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]

# OI series (USD notional), collected daily by okx_oi_daily.py
oi_days, oi_vals = [], []
OI_PATH = BASE / "oi_series.csv"
if OI_PATH.exists():
    with open(OI_PATH) as f:
        for r in csv.DictReader(f):
            oi_days.append(r["date"]); oi_vals.append(float(r["oi_usd"]))
OI_STALE = True
if len(oi_days) >= 2:
    last_oi_date = datetime.strptime(oi_days[-1], "%Y-%m-%d")
    last_price_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    OI_STALE = (last_price_date - last_oi_date).days > 3
if OI_STALE:
    print(f"OI WARN: series missing/stale (last {oi_days[-1] if oi_days else 'none'}), OI term = 0 (v4 == v3)")

def doi_prev(i):
    """OI % change ending on the last completed day before day i.
    Returns 0.0 when the series is missing/stale (v4 falls back to v3)."""
    if OI_STALE or len(oi_days) < 2:
        return 0.0
    j = bisect.bisect_right(oi_days, dates[i-1]) - 1
    if j < 1:
        return 0.0
    return (oi_vals[j] - oi_vals[j-1]) / oi_vals[j-1]

def vol_at(i, window):
    s = lr[i-window:i] if i >= window else lr[:i]
    return statistics.pstdev(s) if len(s) > 1 else VOL_REF
def vol_before(i, window):
    s = lr[max(0, i-window-1):i-1] if i >= 2 else lr[:i]
    return statistics.pstdev(s) if len(s) > 1 else VOL_REF
def regime(v):
    return "low" if v < REGIME_LOW else "high" if v > REGIME_HIGH else "normal"
def damp_at(i):
    v = vol_before(i, VOL_WINDOW)
    return min(DAMP_MAX, max(DAMP_MIN, (VOL_REF / v) ** ALPHA)) if v > 0 else 1.0
def drift(hist, w=DRIFT_W):
    return statistics.mean([hist[j]/hist[j-1]-1 for j in range(len(hist)-w+1, len(hist))])
def predict_v3(hist, i):
    return hist[-1] * (1 + drift(hist) * damp_at(i))
def predict_v4(hist, i, k=OI_K):
    return predict_v3(hist, i) * (1 + k * doi_prev(i))
def naive(hist, i=None): return hist[-1]

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

# OI window starts at the first OI date; v3 comparison on the same window
oi_start = next((i for i, d in enumerate(dates) if oi_days and d >= oi_days[0]), 31)
print(f"OI window: {dates[oi_start]} -> {dates[-1]} (n={len(closes)-oi_start})")
for label, fn in [("naive", naive), ("v3", predict_v3), ("v4", predict_v4)]:
    for wname, start in [("oi_window", oi_start), ("last_30d", len(closes)-30),
                         ("last_90d", len(closes)-90), ("full_year", 31)]:
        if start < oi_start and label == "v4":
            continue  # v4 == v3 before the OI series starts; the oi_window is the fair comparison
        r = backtest(fn, start)
        print(f"{label} {wname}: MAE ${r['mae_usd']} dir {r['directional_accuracy_pct']}%")

# OI_K grid on the OI window (for the doc)
grid = {}
for k in [0, 0.1, 0.2, 0.3]:
    r = backtest(lambda h, i, k=k: predict_v4(h, i, k), oi_start)
    grid[str(k)] = {kk: vv for kk, vv in r.items() if kk not in ("preds", "per_regime")}
    print(f"OI_K {k}: oi-window MAE ${r['mae_usd']} dir {r['directional_accuracy_pct']}%")

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

# Forward forecast (OI term on day 1 only)
last = closes[-1]
d30 = drift(closes)
damp_now = damp_at(len(closes))
v_now = vol_at(len(closes)-1, VOL_WINDOW)
doi_now = doi_prev(len(closes))
resid = [p["actual"] - p["pred"] for p in backtest(predict_v4, len(closes)-90)["preds"]]
resid_sd = statistics.pstdev(resid)
logresid = [math.log(p["actual"] / p["pred"]) for p in backtest(predict_v4, len(closes)-90)["preds"]]
resid_sd_log = statistics.pstdev(logresid)
print(f"current vol30 {v_now*100:.2f}% regime {regime(v_now)} damp {damp_now:.3f} drift30 {d30*100:.3f}% "
      f"dOI% {doi_now*100:+.2f}% OI_K {OI_K} resid SD ${resid_sd:.2f} log-resid SD {resid_sd_log*100:.2f}%")
forecast_days = []
for h in [1, 2, 3, 7, 14, 30]:
    p = last
    for step in range(1, h+1):
        p *= (1 + d30 * damp_now * (0.85 ** (step-1)))
        if step == 1:
            p *= (1 + OI_K * doi_now)
    half_log = 1.96 * resid_sd_log * math.sqrt(h)
    lo, hi = p * math.exp(-half_log), p * math.exp(half_log)
    forecast_days.append({"horizon_days": h,
        "date": (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=h)).strftime("%Y-%m-%d"),
        "forecast_close_usd": round(p, 2),
        "low_95_usd": round(lo, 2), "high_95_usd": round(hi, 2)})
    print(f"  +{h}d {forecast_days[-1]['date']}: ${p:.2f} (${lo:.2f}-${hi:.2f})")

extended = {}
for wname, start in [("oi_window", oi_start), ("last_30d", len(closes)-30),
                     ("last_90d", len(closes)-90), ("full_year_from_day_31", 31)]:
    r = backtest(predict_v4, start)
    extended[wname] = {k: v for k, v in r.items() if k != "preds"}
    print(f"v4 {wname}: MAE ${r['mae_usd']} RMSE ${r['rmse_usd']} dir {r['directional_accuracy_pct']}%")

# preserve the weekly 12w outlook written by weekly_outlook.py
weekly_12w = None
try:
    weekly_12w = json.loads((BASE / "forecast.json").read_text()).get("weekly_12w")
except Exception:
    pass

out = {
    "model": "baseline_v4_drift30_vol_oi",
    "label": "Experimental baseline — NOT financial advice. No trading, no orders, no wallet actions.",
    "description": "v3 (drift30 x vol-damp) x (1 + OI_K x prev-day dOI%), OI_K = 0.2 in config.json. dOI% is the previous-day % change in OKX SOL-USDT-SWAP open interest (USD notional). The OI term applies to the day-1 step only; multi-day drift is damped by 0.85^(h-1)/day as in v3. Bands are log-space: point x exp(+-1.96 x log-residual SD x sqrt(h)). If the OI series is missing/stale, the term is 0 and v4 == v3.",
    "supersedes": "baseline_v3_drift30_vol (scripts/forecast_v3.py, models/baseline_v3.md — kept intact)",
    "config": CFG,
    "inputs": {"source_file": "dataset/daily/sol_ohlcv_daily.csv", "daily_closes": len(rows),
               "first_date": dates[0], "last_date": dates[-1], "last_close_usd": round(last, 2),
               "oi_source": "OKX rubik open-interest-history, SOL-USDT-SWAP, 1D (oi_series.csv)",
               "oi_days": len(oi_days), "oi_first_date": oi_days[0] if oi_days else None,
               "oi_last_date": oi_days[-1] if oi_days else None},
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
                "resid_sd_log_90d_pct": round(resid_sd_log*100, 2),
                "oi_k": OI_K, "oi_change_prev_day_pct": round(doi_now*100, 2),
                "oi_usd_millions": round(oi_vals[-1]/1e6, 1) if oi_vals else None,
                "oi_stale": OI_STALE},
    "oi_k_grid": grid,
    "backtest": {"method": "1-day-ahead, walk-forward, no look-ahead; vol, damp and dOI% use only data before the predicted day",
                 "windows": extended},
    "vol_series": vol_series,
    "forecast": forecast_days,
    "limits": [
        "OI evidence is 99 days only (OKX caps history at 100 rows) — no full-year leg exists yet. Margin is modest (~$0.20/day on the 99d window). Re-verify after 30 fresh days of collection.",
        "The L/S ratio is NOT used: best in-sample numbers in the project (corr -0.506, MAE $1.99) but fails out-of-sample ($2.19 vs naive $1.86). It is collected for a 30-day re-test.",
        "Bands are log-space: point x exp(+-1.96 x log-resid-SD x sqrt(h)); coverage to be re-checked on v4 residuals.",
        "v4 still does not beat naive on the full year — the OI series only starts 2026-08-10, so the full-year window is mostly v3. The win is on the 99d OI window.",
        "Replaceable / tunable: edit config.json (OI_K, VOL_ALPHA) and re-run forecast_v4.py; the grid is recomputed each run. OI_K=0 reproduces v3 exactly.",
    ],
}
if weekly_12w:
    out["weekly_12w"] = weekly_12w
(BASE / "forecast.json").write_text(json.dumps(out, indent=2))
print("wrote forecast.json (v4)")
