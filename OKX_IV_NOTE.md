# OKX implied vol — what was tested 2026-11-18 ~00:56 UTC

Question (from 2026-11-17 ~19:06 EST): does OKX options implied vol predict
tomorrow's SOL move, or just react to it?

## Finding: cannot be backtested from free OKX data — no IV history exists there
- OKX public REST has no IV-history endpoint. The option-summary (Greeks/IV)
  channel is WebSocket-only, live snapshot only.
- Live contracts expire in days: on 2026-11-18 only 3 expiries were listed
  (Nov 18/19/20, 132 instruments). Expired contracts disappear from the
  instruments endpoint, and per-contract history-candles only cover the few
  days that contract was listed. So a 12-month ATM IV series cannot be
  reconstructed from OKX free data.
- Binance options API is geo-blocked from this VM (451 / restricted location)
  and Bybit is CloudFront-blocked from this VM. Paid archives (e.g. Laevitas /
  Amberdata / CryptoStruct day files ~€1/day) are the only route to a long
  IV history — not pursued, no paid source without approval.

## Live snapshot (computed, not quoted) — 2026-11-18 00:56 UTC
- Spot (OKX SOL-USD index): $74.99. ATM IV from bid/ask mids, Black-Scholes,
  r=0: Nov 18 expiry 64.8% C / 65.9% P; Nov 19: 70.5% / 70.7%;
  Nov 20: 70.4% / 70.6%. Term structure essentially flat ~70%.
- Context: realised vol annualised is ~60% on vol30 (3.16%/day) and ~87% on
  vol7 (4.53%/day). So IV ~70% sits between the two — options are pricing
  more vol than the last month delivered, less than the last week delivered.
  That is a sentiment print, not a forecast: it says nothing yet about
  direction, and direction is what the v3 model needs.
- Smile: deep OTM strikes run 80–97% IV vs ~70% ATM — wide, thin book;
  use ATM only for any future series.

## What would make the test possible
Collect one ATM IV snapshot a day (script ready:
`scripts/okx_iv_snapshot.py`, first snapshot saved as
`okx_iv_snapshot_2026-11-18.json`). After ~30–60 daily prints it can be
tested the same way funding was: correlation with next-day return, and
whether adding it to v3 beats naive on MAE. Until then, do NOT add IV to
the forecast — there is no evidence it predicts, only that it exists.
