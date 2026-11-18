# Solana Chart App + Forecasting

An explainable Solana price chart and forecasting baseline, built on local
data. No trading, no orders, no wallet actions — forecasting only.

> **Experimental, not financial advice.** The models here are simple
> closed-form baselines. None of them beats a naive "tomorrow ≈ today"
> guess on error over 90 days or the full year (see the scoreboard below).
> Do not use this to make investment decisions.

## What this is

- A **dataset**: 12 months of SOLUSDT hourly OHLCV from Binance public
  market data, saved as partitioned CSVs with a manifest and verification.
- A **chart app**: a self-contained `app/index.html` (vanilla canvas, no
  external calls at render time) — candlestick/line, timeframes 1D–All plus
  a 3-year weekly view, volume, MA7/MA30, tap-to-pin OHLC, forecast panel.
- A **forecasting baseline**: drift models v1–v3 with walk-forward
  backtests, plus a 12-week analogue outlook from 3 years of weekly data.
- An **hourly refresh**: fetch → verify → forecast → rebuild → sync to a
  Raspberry Pi NVMe snapshot store.

## Layout

```
.
├── README.md                  this file
├── config.json                model config (VOL_ALPHA, drift window, regimes)
├── forecast.json              current forecast output (v3 + weekly 12w outlook)
├── chart-data.json            compact arrays the chart app embeds
├── app/index.html             self-contained chart app (generated)
├── dataset/                   12 months SOLUSDT 1h, one CSV per UTC day
│   ├── README.md              source, coverage, verification
│   ├── MANIFEST.json          machine-readable coverage + verification
│   ├── year=YYYY/month=MM/    daily partition files
│   ├── daily/sol_ohlcv_daily.csv
│   └── weekly/sol_ohlcv_weekly.csv   3y weekly candles (160, Oct 2023 →)
├── scripts/
│   ├── fetch_binance.py       pull 1h klines (Binance public data, no key)
│   ├── verify_dataset.py      duplicates / gaps / OHLC violations / daily mismatches
│   ├── forecast.py            v1: drift14
│   ├── forecast_v2.py         v2: drift30
│   ├── forecast_v3.py         v3: drift30 + tunable vol damping (current)
│   ├── make_chart_data.py     build chart-data.json
│   ├── build_local_app.py     generate app/index.html
│   ├── update_manifest.py     refresh MANIFEST.json
│   ├── weekly_outlook.py      12-week analogue outlook from 3y weekly data
│   ├── okx_iv_daily.py        daily OKX ATM IV snapshot collector
│   ├── okx_iv_snapshot.py     one-off OKX IV snapshot
│   └── sync_hourly.sh         the hourly pipeline (see below)
├── models/
│   ├── baseline_v1.md         drift14
│   ├── baseline_v2.md         drift30
│   └── baseline_v3.md         drift30 + vol damping, log-space bands
├── iv_series.csv              daily OKX ATM IV (2 rows/day, from 2026-11-18)
├── iv_snapshots/              raw OKX option chains, one JSON/day
├── macro_3y_note.md           3-year weekly lookback + Nov–Dec outlook
├── IV_SERIES.md               IV collection method + test plan
└── OKX_IV_NOTE.md             why no free IV history exists
```

## Data sources

- **Prices: Binance public market data, `data-api.binance.vision`,
  SOLUSDT, 1h, no API key.** `api.binance.com` returns HTTP 451 from the
  build VM (geo-blocked) and `api.binance.us` has ~100x lower SOL volume,
  so the global `.vision` endpoint is the representative price. 8,788
  closed hourly candles, 2025-11-17 → 2026-11-18, verified 0 duplicate
  timestamps / 0 non-1h gaps / 0 OHLC violations / 0 daily mismatches,
  3/3 spot-checks exact. First close $139.17 → last close $74.80 (-46.3%).
- **Weekly: same endpoint, 1w klines**, 160 candles Oct 2023 → Nov 2026.
- **Options IV: OKX public REST, no key** (`/api/v5/public/instruments`,
  `/api/v5/public/opt-summary`), Black-Scholes inversion from bid/ask
  mids. No IV history exists on OKX public REST, so the series is built
  forward from 2026-11-18 (see `IV_SERIES.md`).
- No paid source and no API key anywhere in this repo.

## Hourly refresh

`scripts/sync_hourly.sh`, run by an hourly cron:

```
fetch (Binance) → verify (abort on any failure) → forecast v3
  → weekly 12w outlook → chart-data → local app rebuild → manifest
  → daily OKX IV snapshot (fail-safe, never breaks the sync)
  → sync to Pi NVMe (/mnt/nas02/solana/ on pi5d05) → verify Pi copy
```

The hosted chart app is a static artifact with data embedded at build
time, so it is rebuilt separately when the data changes — the hourly job
keeps the VM copy, the Pi copy, and the local app fresh.

## Models

- **v1 `baseline_v1_drift14`**: next-day close = last close × (1 + mean
  daily return over prior 14 days); multi-day drift damped by 0.85^(h-1).
- **v2 `baseline_v2_drift30`**: same with a 30-day drift window — the
  least-bad drift window on the backtest.
- **v3 `baseline_v3_drift30_vol`** (current): v2 × vol-damp, where
  vol-damp = clamp((3.0% / trailing-30d vol) ^ VOL_ALPHA, 0.25, 1.0).
  `VOL_ALPHA` (default 1.0, in `config.json`) is tunable; 0 reproduces
  v2 exactly. Vol-scaled bands were tested and rejected.
- **Bands are log-space** (fixed 2026-11-18): low/high = point ×
  exp(±1.96 × log-residual SD × √h). The old symmetric dollar bands
  implied a -52% downside at 30d; log-space keeps the cone plausible
  (+30d $49.80–$98.87 at the fix) with equal or better coverage
  (94.3% full-year / 94.4% 90d).
- **Weekly 12-week outlook** (`weekly_12w` in `forecast.json`): an
  analogue distribution from 3y weekly data — after a -20% month
  (n=21 episodes), forward 12w returns have median +3.0% (→ ~$77 by
  Feb 2027), p25 -13.8%, p75 +20.9%; P(≥$100) 19%, P(<-20%) 24%.
  This is a scenario distribution, not a point model — no weekly model
  beats naive on MAE at 4w/8w/12w.

Current forecast (last close ~$74.80, drift -1.16%/day, vol30 3.14%,
damp 0.954): +1d $73.97, +7d $71.12, +30d $69.49. Note the ~$69.70
"floor" is a property of the 0.85 damping, not a market support level —
there is no weekly price structure there (see `macro_3y_note.md`).

## Backtest scoreboard (1-day-ahead, walk-forward, no look-ahead)

PASS = MAE strictly below naive in the same window. 18 model×window
combos tested (drift3/7/14/30, MA7, v3 × 30d/90d/full year):

- **2 passed, 16 failed.** The only passes are drift30 and v3 in the
  last 30 days. No model beats naive on MAE over 90d or the full year
  (naive $2.33 / $2.17 vs v3 $2.36 / $2.20).

Tested and **rejected** as forecast inputs, with the numbers in the
model notes: Binance funding rate (corr +0.074, worsens MAE at every
scale); distMA30 mean reversion (gains $0.01–0.03/day, worse on the
latest crash/bounce stretch); weekly mean reversion to the 50w MA
(real 12w correlation -0.41, but worse full-year MAE and worse
post-spike days); vol-scaled bands. No XGBoost / ML anywhere — v1–v3
are closed-form drift formulas; 366 daily closes is thin data for a
tree model and explainability matters here.

## IV series status

Collecting since 2026-11-18 (2 rows/day: nearest + next expiry ATM
call/put IV). Live snapshot at start: ATM IV ~70% vs ~60% realised
annualised (vol30) — options pricing more vol than the last month
delivered. A correlation test needs ~30–60 daily prints, not before
mid/late December 2026; until then IV stays out of the forecast.

## Snapshot note

This repo is a snapshot as of push time. The live folder keeps changing
— the hourly cron adds new candles, re-runs the forecast, and appends
IV rows — so the repo will drift from the live data unless re-synced.
There is no auto-push set up; re-syncing is a manual step.

## License

MIT — see `LICENSE`.
