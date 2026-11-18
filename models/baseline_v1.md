# Forecasting agent — baseline v1 (experimental, NOT financial advice)

No trading, no orders, no wallet actions. Forecasting only, from the local CSVs.

## Model: `baseline_v1_drift14`
- **1-day forecast:** `close(t+1) = close(t) × (1 + mean daily return over prior 14 days)`
- **Multi-day:** same daily drift, damped by `0.85^(h-1)` per day, so the trend fades toward flat. Undamped compounding was rejected: the current 14-day drift is -1.93%/day (a -20.8% selloff, Nov 3–17), and compounding it raw implies $41 in 30 days — an artefact of extrapolating a crash, not a forecast.
- **Inputs:** daily closes only, from `dataset/daily/sol_ohlcv_daily.csv` (366 closes, 2025-11-17 → 2026-11-17). No volume, volatility regime, macro, on-chain or order-book inputs.
- **Code:** `scripts/forecast.py` — `predict_fn` is the single swap point. Replace it (e.g. ARIMA/ETS/seasonal) and re-run; the backtest harness is unchanged.

## Backtest (held out, 1-day-ahead, walk-forward, no look-ahead)
Window: **2026-10-19 → 2026-11-17, 30 days**. Each prediction uses only closes before that day.

| model | MAE | MAE % | RMSE | directional accuracy |
|---|---|---|---|---|
| naive (tomorrow = today) | $1.96 | 2.14% | $2.78 | n/a (predicts no move) |
| **drift14 (baseline)** | **$2.02** | **2.20%** | **$2.72** | **60.0%** |
| MA7 (tomorrow = 7-day mean) | $4.35 | 4.74% | $5.20 | 43.3% |
| drift14 + MA7 blend | $2.64 | 2.87% | $3.37 | 40.0% |

**Honest reading:** the baseline does *not* beat naive on MAE ($2.02 vs $1.96) — in a choppy, falling market, "tomorrow ≈ today" is hard to beat on absolute error. Its only edge is direction (60% vs 43–40% for the MA models). Do not use it as if it were a predictive edge.

## Forward forecast (trained on all data to 2026-11-17, last close $73.51)
Context: MA7 $75.90, MA30 $91.78, 14-day drift -1.93%/day, 30-day daily vol 2.96%, backtest residual SD $2.71.

| horizon | date | forecast | ~95% band* |
|---|---|---|---|
| +1d | 2026-11-18 | $72.09 | $66.79 – $77.39 |
| +2d | 2026-11-19 | $70.90 | $63.40 – $78.40 |
| +3d | 2026-11-20 | $69.91 | $60.73 – $79.10 |
| +7d | 2026-11-24 | $67.30 | $53.27 – $81.34 |
| +14d | 2026-12-01 | $65.44 | $45.59 – $85.28 |
| +30d | 2026-12-17 | $64.64 | $35.59 – $93.69 |

\* Band = ±1.96 × residual SD × √h — a rough residual-based interval, not a calibrated probability. It widens fast because daily vol is ~3%.

## Limits
- 30-day backtest, one regime (a falling market). Metrics will not generalise to a different regime.
- A 14-day drift lags reversals by construction; the Nov 14 -10% day (-$7.91) dominates the current drift.
- No seasonality was modelled (daily data shows no strong weekly cycle checked here).
- The 30-day point forecast ($64.64) is a damped-trend extrapolation, not a price target.
