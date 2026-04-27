## Overview

`src/math_utils.py` provides six pure geometry/kinematics helpers used throughout the strategy and lookahead layers. All imports of Kaggle constants (`CENTER`, `SUN_RADIUS`, `ROTATION_RADIUS_LIMIT`) come directly from the engine package; the values are `CENTER=50.0`, `SUN_RADIUS=10.0`, `ROTATION_RADIUS_LIMIT=50.0`.

Cross-links: [Strategy](strategy.md) | [Lookahead](lookahead.md) | [Agent](agent.md) | [Gotchas](../Gotchas.md) | [Home](../Home.md)

---

## Functions

### `fleet_speed(num_ships, max_speed=6.0) -> float`

Log curve from the Kaggle spec:

```
if num_ships <= 1:
    return 1.0
return 1.0 + (max_speed - 1.0) * (log(num_ships) / log(1000)) ** 1.5
```

Speed grows sub-linearly with fleet size. At 1000 ships it reaches exactly `max_speed`.

| Ships | Speed |
| ----: | ----: |
|     1 |  1.00 |
|    10 |  1.96 |
|   100 |  3.72 |
|  1000 |  6.00 |

The `1.5` exponent makes the curve concave-up in log-space: most of the speed gain happens in the 100–1000 range. Small fleets are slow; massing ships pays off for long-range attacks.

---

### `predict_planet_position(planet, angular_velocity, turns) -> tuple[float, float]`

Predicts where `planet` will be after `turns` turns.

**Stationary check:** computes `orbital_radius = sqrt((x-50)^2 + (y-50)^2)`. If `orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT` (i.e., `orbital_radius + 10 >= 50`, equivalently `orbital_radius >= 40`), the planet does not orbit — returns current `(x, y)` unchanged.

**For orbiting planets:**

```python
period = round(2 * pi / angular_velocity)
normalized_turns = turns % period          # avoids floating-point drift on large turn counts
current_angle = atan2(y - CENTER, x - CENTER)
future_angle = current_angle + angular_velocity * normalized_turns
return (CENTER + orbital_radius * cos(future_angle),
        CENTER + orbital_radius * sin(future_angle))
```

The modulo normalization keeps `normalized_turns` within one orbital period, preventing accumulated floating-point error on multi-turn lookahead calls.

**Gotcha — stationary planet distinction:** the threshold is `orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT`, a compound check. A planet at orbital_radius=40 satisfies `40+10=50 >= 50` → stationary. A planet at orbital_radius=39 gives `39+10=49 < 50` → orbiting. This is the same threshold used by [`is_stationary`](strategy.md) in strategy.

---

### `path_crosses_sun(x1, y1, x2, y2) -> bool`

Returns `True` if the line segment from `(x1,y1)` to `(x2,y2)` passes within `SUN_RADIUS=10` of `CENTER=(50,50)`.

Implementation: projects the center onto the segment (clamped `t ∈ [0,1]`) and tests if the closest-point distance-squared is less than `SUN_RADIUS^2`. The zero-length segment case (same start and end) is handled separately — returns True iff the single point is inside the sun.

**Gotcha — sun-crossing guard:** both `handle_threats` and `plan_expansion` in strategy call this function and silently skip any move whose straight-line path would intersect the exclusion zone. The move is dropped without error. See [Gotchas](../Gotchas.md).

---

### `angle_to_target(from_x, from_y, target_x, target_y) -> float`

```python
return math.atan2(target_y - from_y, target_x - from_x)
```

Standard `atan2` in screen coordinates: origin top-left, y increases downward. Result: `0` = right, `π/2` = down, `π` or `-π` = left, `-π/2` = up. This matches the Kaggle action format directly — no coordinate flip needed.

---

### `distance(x1, y1, x2, y2) -> float`

```python
return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
```

Euclidean distance. Used everywhere; no edge-case handling (returns `0.0` for identical points).

---

### `turns_to_arrive(from_x, from_y, target_x, target_y, num_ships) -> int`

```python
d = distance(from_x, from_y, target_x, target_y)
speed = fleet_speed(num_ships)
return max(1, math.ceil(d / speed))
```

Ceiling division — always at least 1 turn. The `max(1, ...)` guard prevents returning 0 for same-position edge cases where `d=0`. Used by `intercept` and `detect_threats` to compute ETAs.
