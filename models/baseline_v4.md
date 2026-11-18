# Baseline v4 — drift30 + vol damp + OKX open-interest term

`scripts/forecast_v4.py`, config in `config.json` (`OI_K`, `VOL_ALPHA`).
Supersedes v3; v1–v3 code and docs kept intact. Experimental, not financial
advice. No trading, no orders, no wallet actions.

## Formula

Next-day close = v3 prediction × (1 + OI_K × dOI%), OI_K = 0.2,
dOI% = previous-day % change in OKX SOL-USDT-SWAP open interest (USD
notional). Previous-day alignment only — a same-day feature would be
look-ahead. The OI term applies to the day-1 step only in the multi-day
forecast (the signal is a 1-day lead); later days use the usual damped
drift. If the OI series is missing or stale (>3 days), the term is 0 and
v4 == v3 exactly. OI_K = 0 reproduces v3 exactly.

## Why OI — the evidence

Source: OKX public REST, `rubik/stat/contracts/open-interest-history`
(SWAP, SOL-USDT-SWAP, 1D, no key; a browser User-Agent header is required
— urllib's default UA gets 403). History capped at 100 rows, so the series
is collected daily by `scripts/okx_oi_daily.py` into `oi_series.csv`
(2026-08-10 → present); without collection the window never extends.

Verified 2026-11-18 (independent re-check of the signals research, which
had caught and fixed its own same-day look-ahead in a first draft):

- corr(prev-day dOI%, next-day return) = **+0.486** (Spearman +0.328,
  n=98); same-day +0.313 — the peak is at 1-day lead.
- Walk-forward 99d MAE: **v4 $2.08 vs naive $2.28, v3 $2.31**,
  direction 57%. k grid: 0.1 → $2.16, 0.2 → $2.08, 0.3 → $2.09.
- Out-of-sample (k frozen from the fit half, best k=0.2): **$1.76 vs
  naive $1.86**, v3 $1.88, direction 60%.
- High-vol slice (99d window): **$2.51 vs v3 $2.94**.

First signal in this project that beats naive. Caveats: 99 days only, no
full-year leg; margin ~$0.20/day; re-verify after 30 fresh days.

## What is NOT in v4

- **L/S account ratio** (OKX `long-short-account-ratio-contract`, collected
  alongside OI): best in-sample numbers in the project (corr -0.506,
  MAE $1.99, direction 62%) but FAILS out-of-sample ($2.19 vs naive
  $1.86). Collected for a 30-day re-test; stays out of the model.
- **DeFiLlama DEX volume / TVL-in-SOL**: no direction (|r| < 0.08) but
  predicts next-day |return| (+0.226 / +0.206, beating vol30's 0.15) —
  candidate for band-width scaling, not the point. Test pending.
- **Kalshi SOL markets**: exist (series KXSOLE, hourly/daily price-range
  buckets) with retrievable live odds, but no history endpoint — a series
  needs daily snapshots. A market-implied distribution cross-check for
  the bands, not a daily point input.
- **Polymarket**: dead end — 0 live SOL price markets found (2,000+
  scanned); only a closed 2023 market.
- Funding rate, distMA30, weekly-MA mean reversion: tested and rejected
  earlier (see baseline_v3.md and the macro note).

## Bands

Log-space as in v3 (point × exp(±1.96 × log-resid-SD × √h)), now from
v4's own 90d log-residuals. Coverage to be re-checked on v4 residuals.

## Limits

- OI evidence is 99 days only — no full-year leg exists yet.
- v4 does not beat naive on the full year (the OI series starts
  2026-08-10, so most of the full-year window is v3).
- The 0.85 damping that creates the ~$69.70 floor is unchanged; the
  recalibration question (match the 30d point to the analogue median
  -3.5%) is still open and untested.
- Code: `scripts/forecast_v4.py`, collector `scripts/okx_oi_daily.py`,
  config in `config.json`.
