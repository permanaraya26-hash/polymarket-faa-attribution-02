"""Forecast Polymarket Yes prices: per-market, recent-volatility mixture quantiles.

Method (tuned on the 6 practice cases; local mean pinball 0.274 vs the house
baseline's 0.364):
  - Median stays at the checkpoint price (no drift: recent trends do not
    carry forward on these markets; drift variants all scored worse).
  - Spread comes from the market's own recent moves: sigma is the RMS of the
    last 30 one-minute returns, floored at 0.0005 and capped at 0.005, and it
    grows with horizon as h**0.45 (slightly slower than a random walk's
    sqrt(h), which the practice data supports).
  - Prices mostly do not move minute to minute (~88% of minutes are flat),
    so the forecast is a mixture: with probability p(h) = f**h the price has
    not moved at all by minute h, where f is the share of flat minutes in
    the last 30 (capped at 0.98 so no market is ever declared frozen); with
    probability 1 - p(h) it moves normally with the sigma above. The
    quantiles of that mixture are what is written. This collapses the inner
    quantiles onto the checkpoint price at short horizons, exactly where the
    price usually is, while the outer quantiles still widen for jumps.

Stdlib only, deterministic, offline. Reads every *.in in MAKEFUN_INPUT_DIR
(or /input) and writes <id>.out to MAKEFUN_OUTPUT_DIR (or /output).
"""

import json
import math
import os
from statistics import NormalDist

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

TAUS = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.644854, -0.67449, 0.0, 0.67449, 1.644854)

WINDOW = 30          # minutes of recent returns used for sigma and flat share
SIGMA_FLOOR = 0.0005  # price units per sqrt(minute)
SIGMA_CAP = 0.005
ALPHA = 0.45         # horizon exponent: spread grows as h ** ALPHA
FLAT_CAP = 0.98      # a market is never treated as more than 98% flat per minute

_ND = NormalDist()


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    v = round(min(1.0, max(0.0, x)) * 1e6) / 1e6
    return 0.0 if v == 0 else v


def forecast_market(prices, horizon):
    """240 (or horizon) rows of five quantiles for one market."""
    if not prices:
        raise ValueError("market has no prices")
    x = prices[-1]
    n = len(prices)
    # Recent one-minute returns (at most the last WINDOW of them).
    start = max(0, n - 1 - WINDOW)
    rets = [prices[i + 1] - prices[i] for i in range(start, n - 1)]
    if rets:
        rms = math.sqrt(sum(r * r for r in rets) / len(rets))
        flat = sum(1 for r in rets if r == 0) / len(rets)
    else:
        rms = 0.0
        flat = 0.0
    sigma = min(SIGMA_CAP, max(SIGMA_FLOOR, rms))
    f = min(FLAT_CAP, flat)

    rows = []
    for h in range(1, horizon + 1):
        s = sigma * (h ** ALPHA)
        p = f ** h  # P(price has not moved at all by minute h)
        row = []
        if s <= 0.0 or p >= 1.0:
            row = [x] * 5
        else:
            lo = (1.0 - p) / 2.0  # lower edge of the atom's interval
            for tau in TAUS:
                if tau < lo:
                    q = x + s * _ND.inv_cdf(tau / (1.0 - p))
                elif tau <= lo + p:
                    q = x
                else:
                    q = x + s * _ND.inv_cdf((tau - p) / (1.0 - p))
                row.append(q)
        row = [price6(v) for v in row]
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for fname in inputs:
        case_id = fname[: -len(".in")]
        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        horizon = int(case["horizon_minutes"])
        quantiles = case["quantiles"]
        if len(quantiles) != len(TAUS) or any(
            t != q for t, q in zip(TAUS, quantiles)
        ):
            raise ValueError(f"{fname} asks for quantiles {quantiles}, not {list(TAUS)}")
        forecasts = [
            {"id": m["id"], "q": forecast_market(m["prices"], horizon)}
            for m in case["markets"]
        ]
        out = os.path.join(OUTPUT_DIR, case_id + ".out")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"forecasts": forecasts}) + "\n")


if __name__ == "__main__":
    main()
