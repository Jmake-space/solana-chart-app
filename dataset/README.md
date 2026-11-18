# SOL OHLCV dataset — local

## Source
- **Binance public market data, `data-api.binance.vision`, symbol SOLUSDT, interval 1h, no API key.**
- Why this endpoint: `api.binance.com` returns HTTP 451 from this VM (geo-blocked); `api.binance.us` works but SOL volume there is ~100x lower than global, so it is not representative. `data-api.binance.vision` is Binance's own public market-data endpoint serving the same global SOLUSDT klines.
- Rate limits respected: 9 requests total, limit 1000 klines each, 0.3 s sleep between calls. Klines weight 2/request vs 6000/min limit.

## Coverage
- **Granularity: hourly (1h candles), full 12 months — this is the finest granularity available for the full period from this free source.** Intraday finer than 1h (e.g. 1m) exists on Binance but would be ~527,000 rows for 12 months and was not pulled; hourly is the finest practical granularity here.
- **First candle:** 2025-11-17T00:00:00Z, open $137.17, close $139.17
- **Last candle (closed):** 2026-11-18T03:00:00Z, close $74.80 (refreshed 2026-11-18 04:08 UTC)
- **Rows:** 8,788 hourly candles in 366 daily partition files; 366 daily aggregate rows in `daily/sol_ohlcv_daily.csv`
- **Close range:** min $60.88, max $147.52; first close $139.17 → last close $74.07 (**-46.8%** over the window)
- **Total volume:** 1,000,695,503 SOL (hourly sum)
- **Fetch date:** 2026-11-18 04:08 UTC. The next hourly candle was still open at fetch time and is **excluded** — every row in this dataset is a closed candle.

## Layout
```
dataset/
  README.md                         this file
  MANIFEST.json                     machine-readable coverage + verification
  year=2025/month=11/sol_ohlcv_2025-11-17.csv   ... one file per UTC day
  year=2026/month=11/sol_ohlcv_2026-11-17.csv
  daily/sol_ohlcv_daily.csv         daily aggregate (open=first 1h open, high=max, low=min, close=last 1h close, volume=sum)
```
Columns (all files): `timestamp,open,high,low,close,volume,source`
- `timestamp`: candle open, UTC, ISO 8601 with `Z` (e.g. `2025-11-17T00:00:00Z`)
- prices in USDT, volume in SOL, `source` names the endpoint + symbol + interval.

## Verification (2026-11-17, scripts/verify_dataset.py)
- 366 partition files, 8,782 rows — exactly the expected count for 2025-11-17 00:00 → 2026-11-17 21:00 inclusive
- **0 duplicate timestamps, 0 non-1h steps (no gaps), 0 OHLC/volume violations** (high ≥ open/close ≥ low, volume > 0)
- Daily aggregate cross-check: **0 mismatches** (a string-max bug in the first daily build was caught by this check and fixed — see git/scripts history note in fetch script)
- Spot-checks vs live Binance, 3/3 exact match on open+close: 2025-11-17T00:00Z ($139.17), 2026-05-18T23:00Z ($85.38), 2026-11-17T22:00Z ($74.07)
- Per-month row counts: 2025-11: 336, 2025-12: 744, 2026-01: 744, 2026-02: 672, 2026-03: 744, 2026-04: 720, 2026-05: 744, 2026-06: 720, 2026-07: 744, 2026-08: 744, 2026-09: 720, 2026-10: 744, 2026-11: 407 (17th is a partial day: 23 closed hours)

## Refresh
```bash
python3 ~/workspace/solana/scripts/fetch_binance.py   # re-pulls 2025-11-17 → last closed hour, rewrites partitions + daily
python3 ~/workspace/solana/scripts/verify_dataset.py  # re-runs all checks above
python3 ~/workspace/solana/scripts/forecast.py         # re-runs backtest + forward forecast on the new data
python3 ~/workspace/solana/scripts/make_chart_data.py # rebuilds chart-data.json for the app
```
The fetch script is anchored to a fixed start (2025-11-17); to extend it, change `START` in `fetch_binance.py`. No API key, no account, no paid source.
