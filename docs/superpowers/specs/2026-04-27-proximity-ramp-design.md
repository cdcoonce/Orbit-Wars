# Proximity Ramp — Design Spec

**Date:** 2026-04-27
**Feature slug:** proximity-ramp

## Problem

The greedy scoring formula in `plan_expansion` uses a hardcoded distance exponent of 2:

```python
greedy_score = (eff_prod + bonus) / (eta + 1) ** 2
```

This treats early and late game identically. In practice, capturing a nearby planet at turn 10
instead of a distant one at turn 30 means 20 extra turns of production per production point —
a compounding advantage. The agent should strongly prefer nearby targets early, then normalize
to pure value-per-distance as the empire matures and production networks are established.

## Approach: Ramp the Distance Exponent

Add a linear ramp for the distance exponent, mirroring the existing `min_garrison` ramp pattern.
The exponent interpolates from `distance_power_early` (steep — strongly prefers nearby planets)
down to `distance_power_late` (the current-behavior floor) over `distance_ramp_turns` turns.

## New Params

| Param                  | Default | Optuna range      | Purpose                          |
| ---------------------- | ------- | ----------------- | -------------------------------- |
| `distance_power_early` | 3.5     | (2.0, 5.0, float) | Exponent at turn 0               |
| `distance_power_late`  | 2.0     | (1.0, 3.0, float) | Exponent after ramp completes    |
| `distance_ramp_turns`  | 50      | (10, 150, int)    | Turns to ramp from early to late |

`distance_power_late` defaults to `2.0` to preserve current behavior once the ramp completes.
Optuna may push it below 2 if a flatter late-game penalty wins.

## Ramp Helper

```python
def _effective_distance_power(turn: int, params: dict) -> float:
    t = min(turn, params["distance_ramp_turns"]) / params["distance_ramp_turns"]
    return params["distance_power_early"] + t * (params["distance_power_late"] - params["distance_power_early"])
```

This mirrors `_effective_min_garrison` exactly.

## Scoring Formula Change

In `plan_expansion` ([src/strategy.py:221](../../src/strategy.py)):

```python
# Before
greedy_score = (eff_prod + bonus) / (eta + 1) ** 2

# After
dist_power = _effective_distance_power(turn, params)
greedy_score = (eff_prod + bonus) / (eta + 1) ** dist_power
```

## Files Changed

| File                     | Change                                                             |
| ------------------------ | ------------------------------------------------------------------ |
| `src/strategy.py`        | Add `_effective_distance_power` helper; use it in `plan_expansion` |
| `src/config.py`          | Add 3 new params to `PARAMS` and `PARAM_SPACE`                     |
| `tests/test_strategy.py` | 2 new unit tests (ramp helper + score ordering)                    |

## Tests

1. **Ramp helper** — assert `_effective_distance_power` returns `distance_power_early` at turn 0,
   interpolated value mid-ramp, and `distance_power_late` at or beyond `distance_ramp_turns`.
2. **Score ordering** — build two fake planets with equal production at different ETAs; at turn 0
   the closer planet should score higher than at turn 200 (relative gap shrinks after ramp).

## Study DB Note

The current `study.db` shows `lookahead_turns=1` winning across all 200 trials despite `PARAMS`
having `lookahead_turns=3`. After this change ships, `study.db` should be deleted before the
next Optuna retune to clear stale priors and let it explore the new distance params cleanly.
