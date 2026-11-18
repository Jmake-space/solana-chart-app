# Forecasting agent — baseline v3 (experimental, NOT financial advice)

Supersedes v2 (`baseline_v2.md`, kept intact). No trading, no orders, no wallet actions.

## What changed: a tunable volatility parameter
- **Parameter (in `config.json`, tunable):** `VOL_ALPHA` (default **1.0**).
  `vol-damp = clamp((VOL_REF / vol30) ^ VOL_ALPHA, 0.25, 1.0)`, where
  `vol30` = trailing 30-day std of daily log returns, `VOL_REF` = 3.0%
  (near the full-sample median, 3.03%).
- **Forecast:** `close(t+1) = close(t) × (1 + drift30 × vol-damp)`.
  High vol → damp < 1 → forecast moves toward naive (trust the drift less).
  Low vol → damp capped at 1, never amplifies the drift.
  `VOL_ALPHA = 0` gives exactly v2. Multi-day damping `0.85^(h-1)`/day kept.
- **Tracking:** every day now carries `vol7`, `vol30`, `ATR14`, volume ratio
  vs trailing-30d median, and a regime label (`low <2.5% / normal 2.5–3.5% /
  high >3.5%` trailing vol30 — thresholds sit near the full-sample quartiles,
  p25 2.41% / p75 3.50%). The full 366-day series is in `forecast.json`
  (`vol_series`) and charted in the app.
- **To retune:** edit `config.json` (`VOL_ALPHA`, `VOL_WINDOW_DAYS`,
  `VOL_REF_PCT`, regime thresholds), re-run `scripts/forecast_v3.py`.
  The alpha grid below is recomputed on every run.
- **Correction 2026-11-17 ~23:35 UTC:** the first v3 run had a one-day
  look-ahead leak — the backtest's vol used the return *of* the day being
  predicted, and the context vol used 29 returns instead of 30 (hence
  context vol30 3.11% vs series 3.08%). Fixed with `vol_before()` (vol
  strictly before the predicted day) for prediction and `vol_at(last day)`
  for context. Overall MAE barely moved ($2.204 → $2.205 full year), but
  per-regime attribution changed materially — the numbers below are the
  corrected ones; the hosted app's first v3 build still shows the pre-fix
  per-regime table and is being corrected.

## Current vol state (2026-11-17, last close $74.07)
vol30 **3.08%** (normal regime), vol7 4.53%, ATR14 6.73%, volume ratio 1.66×
trailing-30d median, damp **0.974**. So v3 barely differs from v2 today —
the parameter matters in high-vol periods, not today.

## Alpha grid (1-day-ahead, walk-forward, no look-ahead)

| VOL_ALPHA | 30d MAE | 90d MAE | full-year MAE | 90d direction |
|---|---|---|---|---|
| 0 (= v2) | $1.93 | $2.37 | $2.22 | 55.6% |
| 0.5 | $1.93 | $2.37 | $2.21 | 55.6% |
| **1.0 (v3)** | **$1.93** | **$2.37** | **$2.21** | **55.6%** |
| 1.5 | $1.93 | $2.36 | $2.20 | 55.6% |
| 2.0 | $1.93 | $2.36 | $2.20 | 55.6% |

Per regime, full year (MAE, v3): high-vol **$2.74** (n=68, dir 54.4%),
low-vol $2.00 (n=109, 48.6%), normal $2.12 (n=158, 48.1%).
90d per regime (v3): high $2.94 (n=10, 60.0%), low $2.01 (n=29, 65.5%),
normal $2.45 (n=51, 49.0%).
Direction is unchanged at every alpha (49.6% full year, 55.6% 90d, 60.0% 30d).

**Reading:** the effect is small (~1% MAE) because drift30 is already small
(-1.15%/day) and vol only ranges 2–5.5%. α=1.0 is chosen as the natural
inverse-vol scaling, not the grid maximum — α=2.0 gains nothing more.
Vol damping helps a touch where it should (high-vol days) and nowhere else.

## Bands: log-space (changed 2026-11-18)
The old bands were symmetric in dollars, ±1.96 × residual SD ($3.15, 90d) ×
√h, and at 30d implied a -52% downside ($35) — the user rightly flagged the
cone as too broad. A dollar SD estimated when SOL was $140 does not scale
down as price falls. Bands are now **log-space**: low/high = point ×
exp(∓/± 1.96 × log-resid-SD × √h), log-resid-SD 3.19%/day from the 90d
walk-forward backtest. The cone is multiplicative and asymmetric in dollars,
and coverage is as good or better: **94.3%** full year / **94.4%** 90d
(dollar bands: 94.3% / 92.2%).

Vol-scaling the bands was tested and rejected: 95% coverage, 1-day-ahead,
drift30 point forecast: fixed dollar band 94.3% full year / 92.2% 90d;
vol-scaled band 93.4% / 91.1%, at a similar mean width. vol30 predicts
next-day |return| only weakly (corr 0.15, n=335), so scaling bands by vol
makes calibration slightly worse.

## Forward forecast (from last close $75.19, 2026-11-17)
| horizon | date | forecast | ~95% band |
|---|---|---|---|
| +1d | 2026-11-18 | $74.41 | $69.89 – $79.21 |
| +2d | 2026-11-19 | $73.75 | $67.50 – $80.58 |
| +3d | 2026-11-20 | $73.19 | $65.67 – $81.58 |
| +7d | 2026-11-24 | $71.71 | $60.77 – $84.63 |
| +14d | 2026-12-01 | $70.64 | $55.89 – $89.28 |
| +30d | 2026-12-17 | $70.17 | $49.80 – $98.87 |

Context: MA7 $75.98, MA30 $91.80, drift30 -1.10%/day, vol30 3.16% (normal),
damp 0.948. The +1d point ($74.41) is still below the Nov 17 close — same
caveat as v2: daily model says down, last 24h says up, backtest says no edge.

## Limits
- No drift variant (vol-damped or not) beats naive on MAE over 90d or the
  full year (naive $2.33 / $2.17 vs v3 $2.36 / $2.20). v3 is a small,
  principled tilt, not a breakthrough.
- Regime thresholds are descriptive (full-sample quartiles), not discovered
  out-of-sample; per-regime n is small in the 90d window (high-vol n=10).
- Bands are rough residual intervals, not calibrated probabilities.
- Code: `scripts/forecast_v3.py`, config in `config.json`.

## Tuning from the 3y weekly data (tested 2026-11-18, NOT adopted)

A weekly mean-reversion term, pred *= (1 + k * (MA50w/close - 1)), was
tested on the daily walk-forward backtest (k = 0.002..0.02). The weekly
signal is real (distance below the 50w MA correlates -0.41 with forward
12w returns), but it does not improve the 1-day forecast: full-year MAE
k=0.01 $2.25 / k=0.02 $2.39 vs v3 $2.20 (naive $2.17); post-spike days
worse at every k. The 12-week analogue outlook (median +3.0%, p25 -13.8%,
p75 +20.9%) is published separately in forecast.json as `weekly_12w`
(scripts/weekly_outlook.py) and does not change v3's daily points.
