"""Forecast GTA VI's launch-day Twitch viewers hour by hour.

Entry for make.fun competition gta6-twitch-ccu-forecast-01.

Method (fitted at run time from the case's own comparables, nothing
hard-coded from the practice cases):

  1. Anchor. The case's hour-1 print p1 is the anchor. Every comparable
     launch's release day is reduced to log-ratios
     lr_h = ln(viewers_h / viewers_1), h = 2..24.
  2. Pool. Keep the comparables that look like this launch: a rolling
     midnight-local console launch, not front-loaded by a simultaneous
     global unlock or early access, not a free-to-play / slow-burn
     outlier, and not the target's own pre-release history. The filters
     are data-driven (peak/viewers_1 between 1.30 and 15, hour 1 present,
     at least 20 of the 24 release-day hours present) with the case's
     own "Tier:" notes as a second screen.
  3. Fit. For each hour separately, an ordinary least-squares line of
     lr_h on ln(viewers_1): across launches, a bigger hour-1 print
     means a smaller later ramp (r = -0.82 for the peak ratio), because
     hour 1 already holds the regions unlocked by then, while the US
     unlocks at hours 6 (east) and 9 (west) and the evening prime time
     still lie ahead. The line is only trusted inside the hour-1 range
     the pool actually shows: ln(p1) is clamped at the pool's largest
     ln(viewers_1), so a record-size GTA VI hour 1 is forecast with the
     ramp of the biggest comparable launch, never with a ramp
     extrapolated below 1 (hour 1 cannot already be the peak when the
     largest market has not unlocked yet).
  4. Spread. The five quantiles are the fitted value plus the
     quantiles of that hour's regression residuals, half empirical
     (linear-interpolation quantiles) and half normal (mean + z*sd):
     the blend is better calibrated than either alone on the practice
     launches (90% coverage 0.89 vs 0.85 empirical).

On the four practice launches (answers fetched from SullyGnome, the
same source the kit quotes) this scores a mean pinball loss of 0.179
as run on the practice cases, against the house persistence
baseline's 0.387 (per case: Wolverine 0.244, Red Dead Redemption 2
0.151, God of War Ragnarok 0.134, Spider-Man 2 0.186). The final
case carries all 42 comparables, the four practice launches included;
under those conditions the same model scores 0.174 on the practice
cases.

Standard library only, deterministic: no clock, no randomness, no
network. Two runs on the same case write the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
SIGMA = 0.15  # house baseline spread, used only by the fallback

# Pool filters (see module docstring).
PEAK_RATIO_MIN = 1.30
PEAK_RATIO_MAX = 15.0
MIN_RELEASE_HOURS = 20
MIN_POOL = 5


def parse_time(text):
    """ISO-8601 with a Z suffix, parsed on Python 3.12 and 3.13 alike."""
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def round2(x):
    """x rounded to 2 decimals, half up (as the starter rounds it)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def quantile(sorted_vals, tau):
    """Linear-interpolation quantile (type 7) of an ascending list."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))


def ols(xs, ys):
    """Least-squares line y = a + b*x; returns (a, b)."""
    n = len(xs)
    mx = mean(xs)
    my = mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def release_curve(comp):
    """A comparable's release-day hourly viewers: {hour 1..24: viewers}.

    The hour of a point is its offset from the comparable's day_start.
    """
    try:
        day_start = parse_time(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return {}
    hours = {}
    for point in comp.get("hourly") or []:
        try:
            viewers = point["viewers"]
            at = parse_time(point["from"])
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is None or viewers <= 0:
            continue
        delta = (at - day_start).total_seconds() / 3600.0
        hour = int(delta) + 1
        if 1 <= hour <= 24:
            hours[hour] = viewers
    return hours


def tier_excluded(comp):
    """True when the comparable's own notes mark it out of scope."""
    text = ((comp.get("unlock") or "") + " " + (comp.get("name") or "")).lower()
    return (
        "early-access-contaminated" in text
        or "tier: weak" in text
        or "target-history" in text
        or "not a launch" in text
        or "before release" in text
    )


def comparable_rows(case):
    """(v1, {hour: log-ratio}) for every usable comparable launch."""
    rows = []
    for comp in case.get("comparables") or []:
        if tier_excluded(comp):
            continue
        hours = release_curve(comp)
        v1 = hours.get(1)
        if v1 is None or len(hours) < MIN_RELEASE_HOURS:
            continue
        peak = max(hours.values())
        ratio = peak / v1
        if not (PEAK_RATIO_MIN <= ratio <= PEAK_RATIO_MAX):
            continue
        log_ratios = {}
        for h in range(2, 25):
            if h in hours:
                log_ratios[h] = math.log(hours[h] / v1)
        if len(log_ratios) >= MIN_RELEASE_HOURS - 1:
            rows.append((v1, log_ratios))
    return rows


def relaxed_rows(case):
    """Wider pool, used only when the strict pool is too small to fit."""
    rows = []
    for comp in case.get("comparables") or []:
        hours = release_curve(comp)
        v1 = hours.get(1)
        if v1 is None or len(hours) < MIN_RELEASE_HOURS:
            continue
        peak = max(hours.values())
        if not (1.0 <= peak / v1 <= PEAK_RATIO_MAX):
            continue
        log_ratios = {}
        for h in range(2, 25):
            if h in hours:
                log_ratios[h] = math.log(hours[h] / v1)
        if len(log_ratios) >= MIN_RELEASE_HOURS - 1:
            rows.append((v1, log_ratios))
    return rows


def fit_forecast(rows, p1):
    """Per-hour regression forecast: {hour: [q05, q25, q50, q75, q95]}."""
    log_p1 = math.log(p1)
    log_max = max(math.log(v1) for v1, _ in rows)
    log_min = min(math.log(v1) for v1, _ in rows)
    if log_p1 > log_max:
        log_p1 = log_max  # never extrapolate the ramp past the pool
    if log_p1 < log_min:
        log_p1 = log_min
    out = {}
    for h in range(2, 25):
        points = [
            (math.log(v1), lr[h]) for v1, lr in rows if h in lr
        ]
        if len(points) < 3:
            # Too few launches report this hour: fall back to the
            # persistence baseline for this hour only, not the whole case.
            out[h] = [
                min(1e9, max(1.0, round2(p1 * math.exp(z * SIGMA * math.sqrt(h - 1)))))
                for z in Z
            ]
            continue
        a, b = ols([p[0] for p in points], [p[1] for p in points])
        fit = a + b * log_p1
        residuals = sorted(y - (a + b * x) for x, y in points)
        m = mean(residuals)
        s = sd(residuals)
        quantiles = []
        for tau, z in zip(LEVELS, Z):
            empirical = quantile(residuals, tau)
            normal = m + z * s
            quantiles.append(fit + 0.5 * (empirical + normal))
        for i in range(1, 5):
            quantiles[i] = max(quantiles[i], quantiles[i - 1])
        out[h] = [
            min(1e9, max(1.0, round2(p1 * math.exp(q)))) for q in quantiles
        ]
    return out


def baseline_forecast(p1):
    """The house persistence baseline, as the fallback of last resort."""
    out = {}
    for h in range(2, 25):
        row = [
            round2(p1 * math.exp(z * SIGMA * math.sqrt(h - 1))) for z in Z
        ]
        out[h] = [min(1e9, max(1.0, q)) for q in row]
    return out


def forecast_case(case):
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    # No hour-1 print at all: nothing to anchor on. Emit the baseline
    # at p1 = 1 rather than crashing, so the output is still valid.
    p1 = max(1.0, float(first["viewers"])) if first is not None else 1.0
    try:
        rows = comparable_rows(case)
        if len(rows) < MIN_POOL:
            rows = relaxed_rows(case)
        if len(rows) < 3:
            raise ValueError("too few comparables")
        hours = fit_forecast(rows, p1)
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        hours = baseline_forecast(p1)
    return {
        "hours": [
            {"hour": row["hour"], "q": hours[row["hour"]]}
            for row in case["forecast"]
        ]
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
