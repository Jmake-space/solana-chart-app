# Forecasting agent — baseline v2 (experimental, NOT financial advice)

Supersedes v1 (`baseline_v1.md`, kept intact). No trading, no orders, no wallet actions.

## Why v2 — the Nov 17 miss
- Live price at 23:17 UTC on 2026-11-17 was **$75.12**; v1's +1d forecast was **$72.68**.
- Fair scoring: v1 predicted the Nov 17 daily close at **$70.21**; actual close was **$74.07** — error **-$3.86**, worse than naive (-$2.49). Nov 17 was a bounce day (open $71.58, low $71.07, high $74.34, close $74.07, +3.5%) after the Nov 14 crash close of $70.28.
- $75.12 is the **open 23:00 UTC hourly candle**, not a daily close. The Nov 18 daily-close forecast can only be scored at the Nov 18 close. But the direction miss is real: a 14-day drift averages in the crash and cannot catch a 1-day reversal.
- Last 24h hourly: **+3.28%** ($71.72 → $74.07, 22:00 UTC Nov 16 → 22:00 UTC Nov 17), last 6 hours steadily up $72.38 → $74.07.

## Model: `baseline_v2_drift30`
- **1-day forecast:** `close(t+1) = close(t) × (1 + mean daily return over prior 30 days)`
- **Multi-day:** same drift, damped by `0.85^(h-1)`/day (v1 rule, kept).
- **Bands:** ±1.96 × residual SD × √h, residual SD $3.16 from the 90-day drift30 backtest (wider than v1's $2.73 — the longer window includes more volatile days).
- **Inputs:** daily closes only, from `dataset/daily/sol_ohlcv_daily.csv` (366 closes, 2025-11-17 → 2026-11-17, last close $74.07).
- **Code:** `scripts/forecast_v2.py` — `predict_fn` / `drift_fn(w)` is the swap point. v1 code (`scripts/forecast.py`) is unchanged for comparison.
- **Fast indicator only:** 3-day drift is **+0.92%/day** (would give +1d $74.75, closest to live $75.12) and 24h hourly is +3.28% — shown in the app as momentum context, NOT as the point forecast, because of the backtest below.

## Extended backtest (1-day-ahead, walk-forward, no look-ahead)

| model | 30d MAE | 90d MAE | full-year MAE (335 preds) | 90d direction |
|---|---|---|---|---|
| naive (tomorrow = today) | $1.98 | $2.33 | **$2.17** | n/a |
| drift3 | $2.47 | $3.07 | $2.75 | 47.8% |
| drift7 | $2.13 | $2.64 | $2.34 | 51.1% |
| drift14 (v1) | $2.04 | $2.50 | $2.26 | 55.6% |
| **drift30 (v2)** | **$1.93** | **$2.37** | **$2.22** | **55.6%** |
| MA7 | $4.33 | $4.66 | $3.85 | 51.1% |

Blends tested and rejected: 7d/30d 50/50 ($2.23 full year, $2.46 90d), 3d/30d 50/50 ($2.37 / $2.63), 3d/30d 25/75 ($2.25 / $2.47) — none beats naive on MAE.

**Reading:** no drift window beats naive on MAE over 90 days or the full year. drift30 is the least-bad drift in every window and the only drift that beats naive anywhere (last 30d: $1.93 vs $1.98, RMSE $2.65 vs $2.80, direction 60%). Switching to drift3 to chase today would be curve-fitting to one day — it is the worst performer on MAE.

30-day blocks, last 90 days (MAE): Aug 20–Sep 18 naive $3.11 / drift14 $3.20 / drift30 $3.12; Sep 19–Oct 18 naive $1.91 / drift14 $2.26 / drift30 $2.07; Oct 19–Nov 17 naive $1.98 / drift14 $2.04 / drift30 $1.93. drift30 wins only the last block — the edge is recent and thin.

## Forward forecast (from last close $74.07, 2026-11-17)
Context: MA7 $75.90, MA30 $91.78, drift30 -1.15%/day, drift14 -1.87%/day, drift3 +0.92%/day, vol30 3.08%, vol7 4.53%, ATR14 6.73%.

| horizon | date | forecast | ~95% band* |
|---|---|---|---|
| +1d | 2026-11-18 | $73.22 | $67.03 – $79.41 |
| +2d | 2026-11-19 | $72.50 | $63.75 – $81.25 |
| +3d | 2026-11-20 | $71.90 | $61.18 – $82.62 |
| +7d | 2026-11-24 | $70.29 | $53.91 – $86.67 |
| +14d | 2026-12-01 | $69.12 | $45.96 – $92.28 |
| +30d | 2026-12-17 | $68.62 | $34.72 – $102.52 |

\* Rough residual interval, not a calibrated probability. Note the +1d point ($73.22) is still below live $75.12 — the model still says down, the last 24h says up, and the backtest says the model has no MAE edge. Treat the point as weak; the band ($67–$79) is the honest statement.

## Limits
- v2 is the least-bad drift, not a proven edge. It still lags reversals.
- 30-day edge is one recent block; full-year direction is 49.6% — a coin flip.
- No volume, macro, on-chain or order-book inputs; no seasonality.
- The hourly momentum (+3.28% / 24h) is not in the model — the model is daily-close only. Adding it properly needs an hourly backtest, not a one-day eyeball.
