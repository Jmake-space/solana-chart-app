# SOL — 3-year weekly lookback and Nov–Dec outlook

Source: Binance `data-api.binance.vision` SOLUSDT 1w, 160 weekly candles
2023-10-30 → 2026-11-16, saved at `dataset/weekly/sol_ohlcv_weekly.csv`
(0 dupes, 159-week span). Weekly close at last candle $74.41; daily last
close $74.97 (2026-11-18). All figures from these candles unless noted.
Experimental, not financial advice. No model was changed on the basis of this.

## Is $69.70 a floor? No — it is a model artefact

The v3 point forecast flattens at ~$69.66 only because its drift is damped
by 0.85^(h-1): cumulative drift converges to drift/(1-0.85), so the forecast
mathematically cannot go below ~$70. There is no weekly price structure at
$69.70 — no cluster of closes, no prior low. Do not treat it as support.

Real weekly levels around here:
- Above: 50-week MA $93.62 (price -20.5% below it); $100 is a real level —
  46 of 160 weeks closed below $100, and $100–150 was the most common band
  (54 weeks). 100-week MA $133.67 (-44.3%).
- Below: Jun 2026 trough close $66.50 (weekly low $60.13); weekly lows
  $59–60 below that, then $51–53. Only 6 weeks in 3 years closed below $70.

Weekly RSI-14 is 53.1 — not oversold on the weekly timeframe (the daily RSI
of 24.1 was oversold; the weekly is not). No weekly mean-reversion signal.

## Where we are

- ATH close $252.73 (Nov 2024), ATH high $295.83. Drawdown from ATH close
  -70.6%; max drawdown in window -73.7% (trough week 2026-06-01).
- Current: 4w -26.6%, 8w -39.0%, 12w -26.9%, 52w -43.0%.
- Mean weekly return: last 12w -2.26%, last 26w -0.08%, full 3y +1.07%.
  Weekly return SD 12.24% — weekly moves this size are normal for SOL.

## Analogue episodes: after a -20% month, what happened next?

25 weeks had a 4-week return ≤ -20% (like Nov 3–17, -20.8%); 21 have
forward data. Forward returns after those weeks:

| horizon | median | p25 – p75 | positive | > +33% | < -20% |
|---|---|---|---|---|---|
| +4w | -3.5% | -7.8% to +18.4% | 10/21 (48%) | 3/21 (14%) | 3/21 (14%) |
| +8w | +3.7% | -6.7% to +10.7% | 13/21 (62%) | 3/21 (14%) | 2/21 (10%) |

No reliable bounce: the next month is a coin flip with a slightly negative
median; the next 8 weeks lean slightly positive. Dispersion is huge
(-33% to +43% at 4w). The 2026 analogues skew worse — Jan–Feb 2026
episodes kept falling (-17% fwd4w, -19% fwd8w); Oct–Nov 2025 episodes also
fell further. The closest precedent for a turn at these levels is the Jun
2026 trough: closed $66.50, +22.7% in 4 weeks — but that turn came from
$66.50, not from $70.

## Back to $100?

Needs +33% from ~$75. Unconditional base rates over 3 years: a +33% move
happened in 13.5% of 4-week windows and 21.1% of 8-week windows. Conditional
on already being down -20% in a month (the analogue set above): 14% over
either 4 or 8 weeks. So $100 by year-end is roughly a 1-in-7 shot — possible,
not the base case. A further -20% leg is about as likely as the +33%
recovery over the next month (3/21 each way).

## Nov–Dec seasonality: no signal

Only 2–3 Novembers in the window, and they were bull-market months, not a
calendar effect: Nov 2023 +53.0%, Dec 2023 +61.5%, Nov 2024 +45.7%,
Dec 2024 -9.9%, Nov 2025 -28.9% (month to date). Do not use seasonality here.

## Nov–Dec central path (v3 + weekly analogues combined)

- v3 daily model: ~$70 by mid-Dec (crosses $70 ~Dec 5), floor ~$69.70 by
  construction; $68 never on the point forecast.
- Analogue medians from $75: ~$72 in 4 weeks, ~$78 in 8 weeks.
- Combined read: roughly flat-to-slightly-down into year-end, very wide
  dispersion. The $100 path needs a reversal the data does not currently
  show (weekly RSI not oversold, price 20% below the 50w MA, 2026 analogues
  mostly persistent downtrends). The $66 / $60 levels below are as live as
  the $100 level above.

## Limits

- 3 years / 160 weeks is thin; analogue n=21 with overlapping episodes.
- Weekly data says nothing about catalysts; this is price history only.
- v3's daily model and this weekly view are separate lenses — v3 still does
  not beat naive on MAE over 90d/full year.


## 12-week outlook (added 2026-11-18, scripts/weekly_outlook.py)

Analogue distribution, not a point model — no weekly model beats naive on
MAE at 4w/8w/12w (naive 18.0% / 25.1% / 32.5%; best weekly model 19.6% /
27.0% / 33.0%), so the 12-week view is the episode distribution, refreshed
by the hourly job into forecast.json as `weekly_12w`:

- From ~$74.79 (week of Nov 16, still-open candle): median +3.0% → **$77**
  by ~Feb 8, 2027; p25 -13.8% → $64.51; p75 +20.9% → $90.40.
- P(≥$100) 19.0% (4/21 episodes); P(<-20%, i.e. below ~$60) 23.8% (5/21);
  positive 57.1% (12/21). n=21 episodes.

## Daily-forecast tuning test (2026-11-18): weekly mean reversion NOT adopted

Guidance tested: add a weekly mean-reversion term to v3,
pred *= (1 + k * (MA50w/close - 1)), k = 0.002..0.02, daily walk-forward,
MA50w mapped to each day (no look-ahead). The weekly correlation is real
(distMA50 vs forward 12w return r = -0.41), but it does not translate into
a better 1-day forecast:

- 30d: k=0.01 $1.92 vs v3 $1.93 (a $0.01 gain, noise).
- 90d: k=0.02 $2.31 vs v3 $2.36 (beats naive $2.33) — the only win, at the
  largest k.
- Full year: k=0.002 $2.20 (same as v3), k=0.005 $2.21, k=0.01 $2.25,
  k=0.02 $2.39 — all worse than or equal to v3 ($2.20), still worse than
  naive ($2.17). Direction flat ~50%.
- Slices: high-vol days k=0.005 $2.72 vs v3 $2.74 (tiny gain); post-spike
  days worse at EVERY k ($2.76–2.94 vs v3 $2.73, naive $2.65 best);
  last 7 days flat.

Verdict: NOT adopted — same pattern as the distMA30 v4 test (tiny 90d gains,
fails on volatility). v3 stays the daily model. The 0.85 damping that
creates the ~$69.70 floor is untestable on the 1-day backtest (it only
affects h>=2); the weekly evidence says the 30d point is likely too
bearish vs the analogue median (-3.5% at 4w vs v3's -7% at 30d), but
recalibrating it would be fitting to a 21-episode median, not a validated
improvement — left as an explicit option, not adopted.
