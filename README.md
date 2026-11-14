# Polymarket FAA attribution price forecaster

Forecasts the Yes price of every market of a case for the 240 minutes after
its checkpoint, as five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) per minute.

Method (tuned on the kit's 6 practice cases; local mean pinball loss 0.274
vs the house baseline's 0.364):

- The median stays at the checkpoint price. Recent trends do not carry
  forward on these markets — every drift / mean-reversion variant tried
  scored worse than a flat median.
- The spread is per-market and recent: sigma is the RMS of the last 30
  one-minute returns (floor 0.0005, cap 0.005 price units per sqrt-minute),
  growing with horizon as h**0.45.
- Prices usually do not move at all from minute to minute, so the forecast
  is a mixture: with probability f**h the price has not moved by minute h
  (f = share of flat minutes in the last 30, capped at 0.98), otherwise it
  moves normally with the sigma above. The quantiles of that mixture
  collapse the inner quantiles onto the checkpoint price at short horizons,
  where the price usually is, while the outer quantiles still widen for
  jumps.

Python 3.13, standard library only, deterministic, offline, no model calls.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
