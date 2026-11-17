# GTA VI Twitch viewers, hour by hour

[![make.fun](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/c/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Akhmad045/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/c/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Akhmad045/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/c/gta6-twitch-ccu-forecast-01)

Entry for the [make.fun competition](https://make.fun/c/gta6-twitch-ccu-forecast-01)
`gta6-twitch-ccu-forecast-01`: forecast how many people watch Grand Theft
Auto VI live on Twitch in each hour of its release day, 2026-11-19 (UTC),
from everything recorded up to the end of the day's first hour, as five
quantiles an hour (5%, 25%, 50%, 75%, 95%).

## How it works

`main.py` (Python 3.13, standard library only, deterministic) reads the
case's file, fits a model from the case's own comparables at run time, and
writes `/output/<id>.out`:

1. **Anchor.** The case's hour-1 print is the anchor. Every comparable
   launch's release day is reduced to log-ratios
   `ln(viewers_h / viewers_1)`, hours 2–24.
2. **Pool.** Only comparables shaped like this launch are kept: a rolling
   midnight-local console launch, not front-loaded by a simultaneous
   global unlock or early access, not a free-to-play or slow-burn outlier,
   and not the target's own pre-release history. The filters are
   data-driven (peak / hour-1 between 1.30 and 15, hour 1 present, at
   least 20 of the 24 release-day hours present), with the case's own
   "Tier:" notes as a second screen.
3. **Fit.** For each hour separately, an ordinary least-squares line of the
   log-ratio on `ln(viewers_1)`: across launches, a bigger hour-1 print
   means a smaller later ramp (r = −0.82 for the peak ratio), because
   hour 1 already holds the regions unlocked by then, while the US
   unlocks at hours 6 (east) and 9 (west) and the evening prime time
   still lie ahead. The line is only trusted inside the hour-1 range the
   pool actually shows: `ln(p1)` is clamped at the pool's largest
   `ln(viewers_1)`, so a record-size GTA VI hour 1 is forecast with the
   ramp of the biggest comparable launch, never with a ramp extrapolated
   below 1 — hour 1 cannot already be the peak when the largest market
   has not unlocked yet.
4. **Spread.** The five quantiles are the fitted value plus the quantiles
   of that hour's regression residuals, half empirical and half normal:
   the blend is better calibrated than either alone on the practice
   launches (90% coverage 0.89 vs 0.85 empirical).

If the fit ever fails, the program falls back to the house persistence
baseline for the affected hour (or the whole case), so it always writes a
valid forecast.

## Practice results

Scored locally against the practice launches' real release-day counts
(SullyGnome, the same source the kit quotes), mean pinball loss on the
log scale:

| case | this entry | house baseline |
| --- | --- | --- |
| Marvel's Wolverine (p00) | 0.244 | 0.744 |
| Red Dead Redemption 2 (p01) | 0.151 | 0.287 |
| God of War Ragnarök (p02) | 0.134 | 0.215 |
| Marvel's Spider-Man 2 (p03) | 0.186 | 0.303 |
| **mean** | **0.179** | **0.387** |

(The final case carries all 42 comparables, the four practice launches
included; under those conditions the same model scores 0.174 on the
practice cases.)

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

MIT — see [LICENSE](LICENSE).
