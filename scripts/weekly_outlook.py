#!/usr/bin/env python3
"""3-month (12-week) outlook from the 3-year weekly SOL data.

Adds a `weekly_12w` block to forecast.json. This is a SEPARATE view from the
daily v3 point forecast — it does not change v3's points, because no weekly
model beats naive on MAE at any horizon (4w/8w/12w walk-forward, 3y weekly
data: naive 18.0% / 25.1% / 32.5% MAE; best weekly model 19.6% / 27.0% /
33.0%). What the weekly data DOES support is an analogue distribution:
after a -20% month (25 episodes, 21 with forward data), forward 12w returns
have median +3.0%, p25 -13.8%, p75 +20.9%.

The one real signal found: distance below the 50-week MA correlates -0.41
with forward 12w returns (below the MA -> better forward returns, i.e.
mean reversion). But translating it into a daily forecast term was tested
(v3 + k * (MA50w/close - 1), k = 0.002..0.02, daily walk-forward): it does
NOT beat v3 on the full year (k=0.01 $2.25 vs v3 $2.20, k=0.02 $2.39),
worsens post-spike days at every k, and only shaves $0.01-0.05 on 90d.
NOT adopted as a model term. The outlook below is descriptive, not a
tuned point forecast.

Fail-safe by design: any error (fetch, parse, missing file) prints
"WEEKLY OUTLOOK SKIP: ..." and exits 0, leaving forecast.json untouched.
"""
import csv, json, math, statistics, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path.home() / "workspace/solana"
WEEKLY = BASE / "dataset/weekly/sol_ohlcv_weekly.csv"
FORECAST = BASE / "forecast.json"

def log(msg):
    print(f"WEEKLY OUTLOOK: {msg}")

def main():
    try:
        # refresh the weekly series (same public endpoint as the daily fetch)
        try:
            url = "https://data-api.binance.vision/api/v3/klines?symbol=SOLUSDT&interval=1w&limit=160"
            data = json.loads(urllib.request.urlopen(url, timeout=30).read())
            if len(data) >= 100:
                with open(WEEKLY, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["timestamp", "open", "high", "low", "close", "volume", "source"])
                    for k in data:
                        ts = datetime.fromtimestamp(k[0] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        w.writerow([ts, k[1], k[2], k[3], k[4], k[5], "Binance data-api.binance.vision SOLUSDT 1w"])
                log(f"weekly series refreshed: {len(data)} candles")
        except Exception as e:
            log(f"weekly fetch failed ({e}), using saved series")

        rows = []
        with open(WEEKLY) as f:
            for r in csv.DictReader(f):
                rows.append((r["timestamp"][:10], float(r["close"])))
        rows.sort()
        closes = [c for _, c in rows]
        dates = [d for d, _ in rows]
        n = len(closes)
        if n < 60:
            raise ValueError(f"only {n} weekly candles, need 60+")
        last = closes[-1]
        last_date = dates[-1]

        # analogue episodes: 4w return <= -20%, forward 12w returns
        f12 = []
        for i in range(4, n):
            if closes[i] / closes[i - 4] - 1 <= -0.20 and i + 12 < n:
                f12.append(closes[i + 12] / closes[i] - 1)
        if len(f12) < 10:
            raise ValueError(f"only {len(f12)} analogue episodes with 12w forward data")
        s = sorted(f12)
        p25, med, p75 = s[int(0.25 * (len(s) - 1))], statistics.median(s), s[int(0.75 * (len(s) - 1))]
        # 50w MA gap (mean-reversion context)
        ma50 = statistics.mean(closes[-50:])
        gap = last / ma50 - 1
        # weekly RSI-14
        ch = [closes[i] / closes[i - 1] - 1 for i in range(1, n)]
        gains = [max(c, 0) for c in ch[-14:]]
        losses = [max(-c, 0) for c in ch[-14:]]
        ag, al = statistics.mean(gains), statistics.mean(losses)
        rsi = 100 - 100 / (1 + ag / al) if al > 0 else 100.0

        outlook = {
            "method": "Analogue distribution from 3y weekly data (160 candles). Episodes: weeks with a 4-week return <= -20% (current 4w is -26.6%); forward 12-week returns after those episodes. NOT a point model — no weekly model beats naive on MAE at 4w/8w/12w, so this is a scenario distribution, not a tuned forecast.",
            "as_of_weekly_close": last_date,
            "last_weekly_close_usd": round(last, 2),
            "horizon_weeks": 12,
            "target_date": (datetime.strptime(last_date, "%Y-%m-%d") + __import__("datetime").timedelta(weeks=12)).strftime("%Y-%m-%d"),
            "episodes_n": len(f12),
            "median_return_pct": round(med * 100, 1),
            "p25_return_pct": round(p25 * 100, 1),
            "p75_return_pct": round(p75 * 100, 1),
            "median_usd": round(last * (1 + med), 2),
            "p25_usd": round(last * (1 + p25), 2),
            "p75_usd": round(last * (1 + p75), 2),
            "prob_above_100_pct": round(100 * sum(x > 0.33 for x in f12) / len(f12), 1),
            "prob_below_minus20_pct": round(100 * sum(x < -0.20 for x in f12) / len(f12), 1),
            "prob_positive_pct": round(100 * sum(x > 0 for x in f12) / len(f12), 1),
            "dist_below_ma50w_pct": round(gap * 100, 1),
            "ma50w_usd": round(ma50, 2),
            "weekly_rsi14": round(rsi, 1),
        }
        fc = json.loads(FORECAST.read_text())
        fc["weekly_12w"] = outlook
        FORECAST.write_text(json.dumps(fc, indent=2))
        log(f"12w outlook: median ${outlook['median_usd']} (p25 ${outlook['p25_usd']}, p75 ${outlook['p75_usd']}), "
            f"P(>=$100) {outlook['prob_above_100_pct']}%, n={len(f12)} episodes")
    except Exception as e:
        log(f"SKIP: {type(e).__name__}: {e}")
        return 0
    return 0

if __name__ == "__main__":
    sys.exit(main())
