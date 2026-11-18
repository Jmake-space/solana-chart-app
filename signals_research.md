# Solana forecast signals — research notes

**Date:** 2026-11-18 (probes and computations run 2026-11-18 ~04:00–05:30 UTC)
**Status:** research only. Nothing in this file has been wired into the forecast. The top-1 candidate below **passes the project's adoption bar on its test window**; the recommendation is in §1.
**Standing rules:** no paid source, no API key, no sign-ups, no trading/wallet actions. Forecast is experimental, not financial advice.

## 0. What was already tested (do not redo)

| Signal | Result | Verdict |
|---|---|---|
| Binance funding rate | corr +0.074 with next-day return; worsens v3 MAE at every scale | REJECTED |
| distMA30 mean reversion (v4, k=0.02) | gains $0.01–0.03/day; worse on crash/bounce stretch | NOT ADDED |
| Weekly mean reversion to 50w MA | 12w corr −0.41 but daily MAE worse at every k (k=0.01 $2.25 / k=0.02 $2.39 vs v3 $2.20, naive $2.17) | NOT ADOPTED |
| OKX ATM implied vol | no free history; daily collector started 2026-11-18 (`iv_series.csv`); testable only after ~30–60 prints, mid/late Dec 2026 | COLLECTING |
| v3 baseline | 30d drift + vol damping, log-space bands. Scoreboard 2 passed / 16 failed vs naive (only drift30 at 30d) | CURRENT MODEL |

## 1. Headline result — OKX open interest is the first signal that beats naive

**OKX SOL-USDT-SWAP open-interest daily % change** is the first candidate in this project that passes the adoption bar (see §7 for the bar) on its available window:

- Correlation with next-day SOL return: **+0.486 Pearson / +0.325 Spearman, n=99** (Aug 10–Nov 17, 2026). Same-day +0.312, lag-2 −0.048 — the peak is at exactly 1-day lead, which is the signature of a genuine lead effect, not an alignment artefact. Split-half: +0.517 / +0.364 (stable across halves).
- Walk-forward 1-day MAE, full 99-day window: **v3 + OI k=0.2 → $2.08 vs naive $2.28, v3 $2.31**, direction 57%. (k=0.3 → $2.09, dir 59%; k=0.1 → $2.16.)
- **Out-of-sample check (k frozen):** OLS slope fitted on Aug 10–Sep 29 (+0.257) applied to Sep 30–Nov 17: **$1.76 vs naive $1.86, v3 $1.88**, direction 58%. Holds out-of-sample, though the margin is modest (~$0.10/day on the test half).
- Slices (full window): high-vol days v3+OI k=0.3 **$2.45 vs v3 $2.94** (n=10); post-spike days $1.93 vs v3 $2.17 (n=13).
- Interpretation: rising OI = fresh leverage entering; on OKX it leads price up the next day. Note the L/S result below — OI rises while the long share falls, i.e. the new positions are disproportionately short, and the next day price rises (crowded-short squeeze pattern). OI change and L/S change are correlated −0.555.

**OKX long/short account-ratio daily change — strong in-sample, FAILS out-of-sample. Do not adopt.**
- Correlation with next-day return: **−0.506 Pearson / −0.420 Spearman, n=99**. Same-day +0.042 (zero), lag-2 +0.159 — again a clean 1-day lead, not leakage. Split-half −0.680 / −0.336.
- Full-window MAE at k=0.07: **$1.99 vs naive $2.28, v3 $2.31**, direction 62%; high-vol slice $2.12 vs $2.94; post-spike $1.57 vs $2.17. Best in-sample numbers in the project.
- **But:** with the slope frozen from the fit half (−0.102), test-half MAE is **$2.19 vs naive $1.86** — worse than naive out-of-sample, despite 62% direction. The magnitude does not transfer (fit-half slope −0.102 vs full-sample −0.067; second-half correlation only −0.336). Applying it with the wrong sign gives $4.07/$3.42 — the signal is directional-real but magnitude-unstable. Keep collecting, re-test in 30 days; do not adopt now.
- Note the earlier draft numbers that used the **same-day** feature in the MAE test were wrong (look-ahead + oversized k, MAE $4–$19). The numbers above use the previous day's feature, which is the only correct alignment. See §7 for the alignment rule.

**Recommendation:** adopt the **OI term only, as v4**: `pred = v3 × (1 + 0.2 × ΔOI%_prevday)`, k frozen at 0.2 (near the OLS slope +0.283 full-sample / +0.257 fit-half). Do **not** add the L/S term. Start daily collection of both OKX series immediately (see §8) so the window extends past 100 days and the L/S re-test becomes possible; re-verify v4 in 30 days with fresh data. The full-year leg of the bar is impossible for OKX signals (history capped at 100 days — see §2), so the 90-day leg + out-of-sample split is the bar that was actually run.

## 2. Ranked shortlist

### Rank 1 — OKX open interest % change (SOL-USDT-SWAP)
- **What/hypothesis:** daily % change in perpetual-swap open interest (USD notional). Rising OI = new leverage entering; leads next-day return (+0.486).
- **Endpoint:** `GET https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history?instType=SWAP&instId=SOL-USDT-SWAP&period=1D&limit=100` — free, no key. Returns `[ts, oi_contracts, oi_contracts, oi_usd]`; use field 4 (USD notional). Live OI 2026-11-18: 3,166,781 contracts / ~$236.9M.
- **History:** 100 rows at 1D (Aug 10 → Nov 17, 2026). `before=` pagination parameter is **ignored** (returns the same newest rows). No full-year history available from this endpoint.
- **Reachability:** works from VM via curl. **Quirk:** `urllib`'s default User-Agent gets HTTP 403 — send a browser User-Agent. **Period values are case-sensitive:** `period=1D` works, `period=1d` returns code 51000 "Parameter period error". Same quirk on the L/S endpoints.
- **Evidence:** §1 numbers above. Test plan §7, test 1.
- **Adoption status:** passes the bar on the 99-day window + out-of-sample split. Recommend adopt as v4 (k=0.2 frozen).

### Rank 2 — OKX long/short account ratio change (SOL-USDT-SWAP)
- **What/hypothesis:** daily change in long-accounts/short-accounts ratio. Falling ratio (more accounts going short) predicts up next day (−0.506) — contrarian / crowded-short signal.
- **Endpoint:** `GET https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio-contract?instId=SOL-USDT-SWAP&period=1D&limit=100` — free, no key. Returns `[ts, ratio]`; latest 2.29 (Nov 17). Related: currency ratio `.../long-short-account-ratio?ccy=SOL&period=1D` returns **180 rows** (May 22 → Nov 17) but is weaker (level −0.291, daily change −0.282, n=180).
- **History:** 100 days (contract ratio); 180 days (currency ratio). Same pagination limit.
- **Reachability:** works from VM (same UA quirk, same `1D` case quirk).
- **Evidence:** §1 numbers above. Fails the out-of-sample leg of the bar → **not adopted**. Keep on watchlist; re-test after 30 days of daily collection.
- **Test plan:** §7, test 2.

### Rank 3 — DeFiLlama DEX volume / TVL-in-SOL as *volatility* signals (bands, not points)
- **What/hypothesis:** on-chain activity does not predict SOL *direction* (all directional corrs |r| < 0.08, n=366), but activity **levels** predict next-day *magnitude*: DEX volume level corr with |next-day return| **+0.226**; TVL-in-SOL level **+0.206**. Both beat trailing vol30's |return| correlation (0.15, from the v3 work). High DEX volume / high TVL-in-SOL days precede bigger moves.
- **Endpoints (all free, no key, full history in one call):**
  - TVL: `GET https://api.llama.fi/v2/historicalChainTvl/Solana` — 2,073 daily points, Mar 2021 → 2026-11-18, last $4.778B. **Must use TVL in SOL terms** (TVL_USD / SOL close) — TVL in USD mechanically rises with price.
  - Chain fees: `GET https://api.llama.fi/overview/fees/Solana` — 1,739 daily points from Jan 2022, last $6.76M/24h. (Fees/revenue collapsed: Solana network revenue $1,404.8M in 2025 → $288.7M annualised 2026, ~−79%, Fidelity/Blockworks via Solana Compass.)
  - DEX volume: `GET https://api.llama.fi/overview/dexs/Solana` — 1,871 daily points, last $750M/24h.
  - Stablecoins on Solana: `GET https://stablecoins.llama.fi/stablecoincharts/Solana` — 1,653 daily points; $13.64B circulating.
  - Rate limit ~500 req/5 min free; Pro is $300/mo (not needed).
- **Measured directional corrs (n=366, vs next-day return):** TVL USD level −0.068, ΔTVL −0.044; TVL-in-SOL level +0.041, Δ −0.038; fees level −0.023, Δ +0.012; DEX level −0.079, Δ −0.040; stablecoins level +0.023, Δ +0.008. **None is a direction signal.**
- **Test plan:** §7, test 3 — band-width tuning, not point forecast.

### Rank 4 — Kalshi SOL price-range markets (distributional cross-check, no history yet)
- **What:** Kalshi runs SOL price-range markets: series `KXSOLE` ("SOL price range on [date] at [time]?") — hourly/daily events, each with ~$1-wide buckets as separate binary markets (e.g. `KXSOLE-26NOV2017-B75` = "$75 to 75.9999" for SOL price on Nov 20, 2026, close 22:00 UTC). Also `KXSOLMAXM` ("Solana max this month") — the live event found is stale (25OCT01, Oct 2025). No SOL "above $X by date" series was found; BTC/ETH have those (`KXBTCABOVEBY`, `KXETHABOVE2500BY`).
- **Live odds (probed 2026-11-18):** the `/markets` list endpoint returns `yes_bid`/`yes_ask: None` for these buckets, but the **single-market** and **orderbook** endpoints work: B75 bucket — `last_price_dollars $0.03`, `previous_yes_bid $0.02`, `previous_yes_ask $0.10`, `no_bid $0.83`, `no_ask $0.98`; orderbook `yes_dollars: [[$0.01, 20746], [$0.02, 5279]]`. So the market implies ~1–3% for SOL in $75–76 at Nov 20 22:00 UTC (narrow $1 bucket, 2 days out — mass spreads across buckets B56–B103+).
- **Endpoints:** `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXSOLE&limit=5` (find events), `GET .../markets?event_ticker=KXSOLE-26NOV2017` (bucket list), `GET .../markets/{ticker}` (single market incl. last_price), `GET .../markets/{ticker}/orderbook` (live bid/ask + depth). Free, no key.
- **History:** **none found.** The candlesticks endpoint (`/markets/{ticker}/candlesticks?...`) returns 404. A Kalshi series would need daily snapshots of the orderbooks (like the IV collector). Each event is a fresh set of buckets, so history must be built, not downloaded.
- **How it would map to the forecast:** the bucket yes-prices across B56–B103 sum to ~1 and give a market-implied distribution for SOL at a fixed future time (e.g. Nov 20 22:00 UTC). Its median is comparable to v3's +2d point; its interquartile range is comparable to the log-space bands. It is a **distributional cross-check**, not a daily point input — it does not map cleanly to a 1-day-ahead return (different horizon per event, hourly/daily cadence, thin books).
- **Test plan:** §7, test 4. Honest assessment: useful as a sanity check on the bands, not as a forecast input.

### Rank 5 — Prediction markets, Polymarket: DEAD END (documented)
- Polymarket's daily "Solana Up or Down" and "Solana above $X by [date]" markets **do not appear in any API response from this VM**.
- Gamma API (`https://gamma-api.polymarket.com`): `search`, `tag_slug`, `active`/`closed` filters are **ignored** — every query returns the same 5 politics markets (Xi Jinping, Newsom, AOC, Buttigieg, Shapiro). `/events?limit=100&active=true` returned **2 events**. `/tags` returned an empty list. Gamma is non-functional from here.
- CLOB API (`https://clob.polymarket.com/markets`): works, 1,000 markets/page, `next_cursor` pagination. Scanned **2,000+ markets** (pages 1–2, plus `?active=true`): **0 live SOL price markets, 0 "Up or Down" markets**. The only SOL market found is closed: "Will the price of $SOL be above $11 on January 3?" (end 2023-01-03, closed: true). The 6 "SOL" mentions in the active list are all 2023 insolvency markets (Binance/Huobi/Silvergate).
- CLOB price history (`/prices-history?market=<token_id>&interval=1d`) exists but there is no live SOL market to point it at.
- Verdict: no usable Polymarket SOL signal. Do not retry without a different access route (the website itself was not scraped; Gamma/CLOB are the documented APIs).

## 3. Dead ends with published evidence (do not re-test)

| Signal | Evidence | Source |
|---|---|---|
| **SOL ETF flows** | Next-24h rank corr **+0.01 (SOL)** / −0.02 (XRP); cumulative SOL ETF inflows $1.54B while SOL fell 46.9% (2025-10-28–2026-10-23, SoSoValue flows vs Binance prices) | whycoinmoves.com/research/xrp-solana-etf-flows-and-price |
| **Fear & Greed index** | BTC price changes Granger-cause the index, not the reverse; day after extreme fear BTC +0.084% vs +0.132% after all other days — no edge (3,157 days, Feb 2018–Sep 2026) | ScienceDirect 2023 study; edgeormyth.com/tests/crypto-fear-greed/ (alternative.me API works from VM: value 11, Extreme Fear, 2026-11-18) |
| **Exchange inflows/outflows** | 41M+ transfers >1 SOL, 101 labelled CEX hot wallets, CatBoost/XGBoost/RF/LSTM: "aggregate Solana exchange-flow variables provide neither reliable standalone predictive performance nor a stable incremental gain over conventional predictors"; "technical indicators deliver the strongest average one-day-ahead SOL direction forecasts" | MDPI *Forecasting* 2026, 8, 65, "Do Solana Exchange Flows Matter?" |
| **BTC lead / SOL-BTC beta** | Prior-day BTC return → next-day SOL return **corr −0.026** (n=366, computed here); SOL/BTC ratio Δ +0.064. Published: "using one coin's previous-day return to predict another coin's next-day return did not outperform simply assuming a zero return" (Coinbase daily closes Sep–Oct 2026). Same-day SOL/BTC corr is 0.85–0.93, beta ~1.23–1.41 — strong same-day co-movement, weak next-day lead | btcusa.com/Threads analysis; Gale Finance |
| **LSTM/ML papers** | Claim MAPE <5% / R² 0.78–0.90 but never compare against a naive baseline; one is internally inconsistent (claims SOL, reports BTC prices ~$88,425) | SOSTECH Feb 2026; FinTech Innov. J. 2026; Zurnalai comparative study — not credible evidence |
| **Macro (DXY/rates/dominance)** | Described as front-running BTC drawdowns / rotation gauge with explicit caveats ("correlation that comes and goes", "context, never an entry trigger"). No SOL-specific leading evidence found | Various; context only |

## 4. Blocked / paywalled / keyed (do not propose buying without flagging cost)

| Source | Status from this VM | Cost / note |
|---|---|---|
| Coinglass open API v4 | 401 "API key missing" | Key required; pricing not checked (no sign-up) |
| SoSoValue ETF API | 403 from VM | — |
| Farside (farside.co.uk/sol) | 403 from VM | — |
| CryptoQuant | Free Basic: 10,000 credits/mo, 30 days history; on-chain data needs Professional ($99+/mo) | Paid tier flagged, not bought |
| Glassnode | API from $29/mo | Paid, not bought |
| Dune | $65/mo | Paid, not bought |
| Artemis, Nansen | Keyed / paid | — |
| GitHub API (dev activity) | **Rate-limited from this VM** (403, shared egress IP 104.29.200.239, 60/hr unauthenticated quota exhausted). `bitcoin/bitcoin` returned 200 earlier; `solana/solana` and `solana-labs/agave` both 404 (repos moved — validator client is now `anza-xyz/agave`; `agave` returned 403 on rate limit, not a genuine 404). CoinGecko `/coins/solana` returns `developer_data: null` on the free tier | Dev activity is a slow, monthly-granularity variable with a weak prior anyway; an authenticated GitHub token would unblock it, but it is not a priority signal |
| Binance vision OI archive | 404 at documented monthly/daily `openInterest` zip paths; `?list-type=2` S3 listing returns the HTML index, not XML | Funding-rate archive works; OI archive does not (from here) |
| Binance futures API / api.binance.com | HTTP 451 / restricted location (geo-blocked) | Known limit |
| Bybit | CloudFront-blocked | Known limit |
| Deribit | No SOL options listed | — |

## 5. Other probes (for completeness)

- **OKX taker volume:** endpoint needs `ccy` param (error 50014 "ccy can't be empty" with `instType=CONTRACTS` alone); not pursued — OI/L-S already cover the derivatives family.
- **OKX top-trader data:** starts 2024-03-22; Binance global accounts ~76% long / top traders ~79% long (blockchain.news, 2026-11-17) — positioning is extremely long, consistent with the contrarian L/S read.
- **Solana public RPC:** works (`getSupply`: circulating ~591.7M SOL). Staking ratio ~68–69%, barely moved during the crash (~4.8M SOL left staking in 30 days) — a slow structural variable, not a daily predictor. No history from RPC.
- **Polymarket/Kalshi:** see §2 ranks 4–5.

## 6. Full correlation table (computed 2026-11-18 against local daily closes)

n=366 unless noted. Feature dated day d, target = SOL return close(d) → close(d+1).

| Feature | corr(next-day ret) | corr(\|next-day ret\|) | n |
|---|---|---|---|
| OKX OI USD daily % change | **+0.486** (Spearman +0.325) | +0.231 | 99 |
| OKX L/S account ratio daily change | **−0.506** (Spearman −0.420) | −0.222 | 99 |
| OKX L/S account ratio level | −0.355 | −0.121 | 100 |
| OKX currency L/S (ccy=SOL) level / daily change | −0.291 / −0.282 | −0.034 / −0.134 | 180 |
| OKX OI USD level | −0.073 | −0.046 | 100 |
| DeFiLlama DEX volume level | −0.079 | **+0.226** | 366 |
| DeFiLlama TVL-in-SOL level | +0.041 | **+0.206** | 366 |
| DeFiLlama stablecoins level | +0.023 | −0.186 | 366 |
| DeFiLlama TVL USD level / Δ | −0.068 / −0.044 | +0.083 / −0.034 | 366 |
| DeFiLlama chain fees level / Δ | −0.023 / +0.012 | +0.048 / +0.039 | 366 |
| BTC daily return | −0.026 | −0.195 | 366 |
| SOL/BTC ratio level / Δ | −0.050 / +0.064 | +0.028 / −0.015 | 366 |
| (prior work) Binance funding rate | +0.074 | — | ~1,095 |
| (prior work) distMA50 vs fwd 12w return | −0.41 (12w horizon) | — | 21 episodes |

## 7. Adoption bar (explicit — same discipline as the funding test)

A signal is wired into the forecast **only if all four** hold:

1. **MAE:** walk-forward 1-day-ahead MAE beats **naive and v3** in the 90d window (and full-year where history allows — impossible for OKX: 100d cap).
2. **Slices:** no worsening on high-vol days (trailing-30d vol > 3.5%) or post-spike days (|prev-day return| > 5%).
3. **Direction:** ≥55% correct direction in the same window.
4. **Out-of-sample:** parameters (k) fitted on the first half of the window, then beaten-naive on the second half — or 30 fresh days collected with k frozen.

**Results against the bar:** OI passes all four (90d ≈ 99d window). L/S passes 1–3 in-sample, **fails 4** → not adopted. DeFiLlama vol signals are band signals, so their bar is different (see test 3).

### Test 1 — OKX OI % change (ready to run; already run — see §1)
- Pull: `open-interest-history` (above), field 4 = OI USD. Compute `ΔOI%_d = OI_d / OI_{d-1} − 1`. **Alignment (critical):** the 1D row dated d is the value at 00:00 UTC on day d; the feature used to predict close(d+1) is `ΔOI%_d`. In walk-forward code predicting close[i], use the feature from **day i−1** (`dates[i-1]`). Using the same-day feature is look-ahead and inflates MAE (the first draft of this test did exactly that and produced $4–$19 MAE — the corrected version is in §1).
- Correlation: Pearson + Spearman vs next-day return; same-day and lag-2 as leakage checks (next-day must be the peak).
- Walk-forward MAE at 30d/90d (full-year N/A): `pred = v3 × (1 + k·ΔOI%)`, k grid 0.1/0.2/0.3/0.5; compare vs naive and v3; direction %; high-vol and post-spike slices.
- Adopt: k frozen at 0.2 (near OLS slope +0.283 full / +0.257 fit-half). Re-verify after 30 fresh days.

### Test 2 — OKX L/S ratio change (ready to run; already run — see §1)
- Pull: `long-short-account-ratio-contract`, field 2 = ratio. Feature `ΔLS_d = LS_d − LS_{d-1}`. Same alignment rule as test 1.
- Same corr + MAE protocol; k grid 0.02/0.05/0.07/0.1 in `pred = v3 × (1 − k·ΔLS)`.
- Adopt requires: pass the bar **including leg 4** on a fresh 30 days (it failed leg 4 on Sep 30–Nov 17). Until then, collect only.

### Test 3 — DeFiLlama DEX volume / TVL-in-SOL for band width
- Pull daily DEX volume and TVL-in-SOL (TVL_USD / SOL close) from §2 rank 3; align day d → |return| close(d)→close(d+1).
- Step 1 (done): corr with |next-day return| is +0.226 / +0.206 vs vol30's +0.15.
- Step 2: walk-forward band test — scale the log-space band half-width by `(1 + a·z)`, where z is the z-scored DEX-volume (or TVL-in-SOL) level, a grid 0/0.1/0.2/0.3. Measure 30d/90d/full-year: coverage of the 95% band and mean band width. **Adopt only if** coverage stays ≥90% while mean width shrinks, or coverage improves at the same width. Do not touch the point forecast with these — they carry no direction.

### Test 4 — Kalshi implied distribution (needs 30 days of snapshots first)
- Daily (ideally at a fixed time, e.g. 21:00 UTC): fetch the nearest KXSOLE event's orderbooks for all buckets; record yes mid-price per bucket; normalise to sum 1; compute implied median, p25, p75 for SOL at the event's close time.
- Compare implied median vs v3's point at the matching horizon (event close is typically 1–3 days out) and implied IQR vs the log-space bands.
- Calibration: over ~30 events, does SOL land inside the market's central 50% interval ~50% of the time? Does the implied median beat v3's point on MAE at the event horizon?
- **Adopt only if** the implied median beats v3 on MAE at matched horizons over ≥30 events **and** the book is liquid enough (yes+no depth > $1,000 per bucket at the median). Until then it is a cross-check, not an input. Note: this does not map cleanly to a 1-day-ahead return — say so in any report.

## 8. What to build next (for the parent agent — not done here, research only)

1. **Daily OKX collector** (analogous to `scripts/okx_iv_daily.py`): snapshot OI USD + contract L/S ratio + currency L/S ratio once a day into a CSV (e.g. `~/workspace/solana/okx_derivs_daily.csv`), wired into `sync_hourly.sh` with a fail-safe. Reason: the 100-row API window rolls — without collection the test window can never extend past 100 days, and the L/S re-test needs fresh data.
2. **v4 = v3 + OI term** (k=0.2 frozen) — the only adoption recommended now. L/S stays out until it passes leg 4 on fresh data.
3. **Optional:** daily Kalshi KXSOLE orderbook snapshot (same collector pattern) to build the history test 4 needs; DeFiLlama daily snapshot is not needed (full history is downloadable in one call).

## 9. Sources

- OKX v5 public/Rubik API: https://www.okx.com/docs-v5/en/#public-data-rest-api-get-open-interest-history ; long-short endpoints under `/api/v5/rubik/stat/contracts/`
- DeFiLlama: https://api.llama.fi ; https://stablecoins.llama.fi ; docs https://defillama.com/docs/api
- Kalshi API: https://api.elections.kalshi.com/trade-api/v2/ (docs: https://trading-api.readme.io)
- Polymarket Gamma API: https://gamma-api.polymarket.com ; CLOB API: https://clob.polymarket.com
- ETF flows: https://whycoinmoves.com/research/xrp-solana-etf-flows-and-price
- Fear & Greed: https://edgeormyth.com/tests/crypto-fear-greed/ ; ScienceDirect 2023 study (BTC price → index, Granger)
- Exchange flows: MDPI *Forecasting* 2026, 8, 65 — https://mdpi-res.com/d_attachment/forecasting/forecasting-08-00065/article_deploy/forecasting-08-00065-v2.pdf
- Cross-asset lead: btcusa.com / Threads analysis (Coinbase daily closes Sep 1–Oct 26, 2026)
- Binance public data: https://data-api.binance.vision
