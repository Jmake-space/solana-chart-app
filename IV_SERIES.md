# OKX SOL ATM implied-vol series — free subset, built 2026-11-18

User decision (2026-11-17, ~20:02 EST): build the IV series from the free
subset available; do NOT buy a paid history.

## What the series contains

- `iv_series.csv` — one row per expiry per day, ATM strikes only.
  Columns: `date, snapshot_ts_utc, spot_usd, expiry, days_to_expiry, rank,
  atm_call_strike, atm_call_iv_pct, atm_call_mid, atm_put_strike,
  atm_put_iv_pct, atm_put_mid`. `rank` is `nearest` or `next` expiry.
  Backfilled 2026-11-18 from the saved snapshot (see below); the series
  starts 2026-11-18 and grows by 2 rows/day.
- `iv_snapshots/okx_iv_YYYY-MM-DD.json` — the full raw option chain for that
  day (every strike, bid/ask mid, inverted IV), so ATM values can be
  re-derived or the definition revisited later without re-fetching.
- IV is computed, not quoted: Black-Scholes inversion from bid/ask mids,
  r=0, T=days/365, same method as `scripts/okx_iv_snapshot.py`.
- ATM only, by design: deep OTM strikes run 80–97% IV vs ~70% ATM (wide,
  thin book), so including them would make the series incomparable day to
  day. ATM = strike closest to spot, separately for calls and puts.

First rows (2026-11-18, spot $74.99, snapshot 00:56 UTC): nearest expiry
2026-11-18 (0.29d) call IV 64.8% / put 65.9%; next expiry 2026-11-19 (1.29d)
call 70.5% / put 70.7%. Flat term structure ~70%, between realised vol30
~60% and vol7 ~87% annualised. Full write-up: `OKX_IV_NOTE.md`.

## How it is collected

- Collector: `scripts/okx_iv_daily.py` (OKX public REST only, no API key,
  no credentials). It fetches index-tickers + option tickers + instruments,
  inverts IV for the whole chain, picks ATM call/put for the nearest and
  next expiries, saves the raw chain JSON, and appends the rows.
- Trigger: one step in `scripts/sync_hourly.sh`, after `update_manifest.py`
  and before the Pi sync, so the series rides to pi5d05 with the rest of
  `~/workspace/solana/`. The hourly cron (`solana-hourly-refresh`) is
  unchanged; the collector no-ops when today's rows already exist, so the
  first hourly run after midnight UTC takes the snapshot.
- `--dry-run` fetches live and prints the ATM IVs without writing anything.
- Fail-safe: the collector catches every error, prints `IV SKIP: ...`, and
  exits 0; the shell step has `|| echo ...` as belt-and-braces. An OKX
  outage, block, or empty chain can never fail the hourly sync or touch the
  dataset, forecast, or Pi copy. Verified 2026-11-18 by simulating an OKX
  outage (patched fetch to raise): exit 0, series byte-identical.

## Limits

- Starts 2026-11-18 — there is no free IV history before this (OKX public
  REST has no IV-history endpoint; Greeks/IV is WebSocket-only, live
  snapshot only; expired contracts disappear). A correlation test needs
  ~30–60 daily prints before it is meaningful, i.e. not before mid/late
  December 2026.
- Only ~3 expiries exist at a time and they roll daily, so `days_to_expiry`
  for the nearest leg shrinks toward 0 each day — compare like-for-like
  (same rank, or IV interpolated to a fixed horizon) when testing.
- Snapshot time is whenever the first hourly run after midnight UTC lands
  (typically ~00:0x–01:0x UTC), not a fixed clock time; intraday IV moves
  are not captured.
- IV is a vol print, not a direction signal on its own. It may turn out to
  predict nothing — funding rate already tested out as noise (+0.074 corr,
  worse MAE at every scale).

## How the test will run (when ~30–60 prints exist)

Same bar funding was tested against, in `scripts/` (new script, IV stays
OUT of `forecast_v3.py`, `config.json`, and the app until then):
1. Align each day's ATM IV (nearest expiry, and separately next expiry)
   with the next day's log return from `dataset/daily/sol_ohlcv_daily.csv`.
   Compute Pearson corr(IV_t, return_{t+1}) and corr(IV_t, |return_{t+1}|),
   n≈30–60. Also corr(IV_t − realised vol30_t, return_{t+1}) — the IV
   premium over realised vol is the more plausible signal.
2. If |corr| is material (>~0.2 with n≥30), walk-forward test: v3 point
   forecast × (1 − k·(IV − vol)) or a drift tilt by IV rank, k on a small
   grid, MAE over 30d/90d/full-series vs v3 and vs naive. Adopt ONLY if it
   beats naive on MAE in at least one window without worsening the others —
   the same adoption bar as the v4 distMA30 decision (which was NOT adopted).
3. Report the result with the numbers, including the negative case. Do not
   wire IV into the forecast on a correlation alone.
