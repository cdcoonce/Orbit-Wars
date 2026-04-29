## Overview

`src/agent.py` is the Kaggle submission entry point. It constructs typed objects from the raw observation dict, maintains a single per-game cache (`_initial_planets`), and delegates all decision-making to [`plan_moves`](strategy.md).

Cross-links: [Strategy](strategy.md) | [Math Utils](math_utils.md) | [Comets](comets.md) | [Home](../Home.md)

---

## The `obs` Dict

The Kaggle runtime passes a single `obs: dict` to the agent each turn. All keys:

| Key                       | Type                         | Semantics                                                                                                                                          |
| ------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `obs['planets']`          | `list[list]`                 | Raw planet data — each inner list is unpacked into a `Planet` namedtuple: `(id, owner, x, y, radius, ships, production)`. `owner == -1` = neutral. |
| `obs['fleets']`           | `list[list]`                 | Raw fleet data — each inner list is unpacked into a `Fleet` namedtuple: `(id, owner, x, y, angle, from_planet_id, ships)`.                         |
| `obs['player']`           | `int`                        | Our player number — `0` or `1`.                                                                                                                    |
| `obs['angular_velocity']` | `float`                      | Radians per turn that all orbiting planets rotate around the sun. Constant for the entire game.                                                    |
| `obs['step']`             | `int`                        | Turn number, 0-indexed. Ranges from 0 to 499 (500 total turns).                                                                                    |
| `obs['comet_planet_ids']` | `list[int]` or absent/`None` | Planet IDs currently designated as comets. May be missing or `None` in older env versions; `get_comet_ids` handles both gracefully.                |

`Planet` namedtuple fields: `id, owner, x, y, radius, ships, production`

`Fleet` namedtuple fields: `id, owner, x, y, angle, from_planet_id, ships`

---

## Module-level Caches

```python
_initial_planets = None                                  # turn-0 planet snapshot
_prev_comet_positions: dict[int, tuple[float, float]] = {}  # comet xy from last turn
```

### `_initial_planets`

**Why it exists:** `plan_expansion` calls `build_state(initial_planets, fleets, turn)` at the start of each per-source lookahead branch to clone the board state. `build_state` needs the full planet list as it existed at turn 0 — the stable orbital positions — because `step_state` advances planets by `angular_velocity` each simulated turn. Without the turn-0 snapshot, each call to `build_state` would start from an already-rotated position and compound the error across `lookahead_turns` steps. The Kaggle environment only provides the _current_ turn's planet positions, so the cache is the only source of truth for the starting state.

If the agent is reloaded mid-game (e.g., in local testing), the `or _initial_planets is None` guard ensures the cache is re-populated rather than staying `None`.

### `_prev_comet_positions`

Comets follow pre-computed elliptical paths at constant linear speed (~4 units/turn), not circular orbits. `predict_planet_position` assumes circular motion, so it can miss a comet by 3-5× its actual angular rate. The agent estimates comet velocity from consecutive position observations:

```python
comet_velocities[p.id] = (p.x - prev_x, p.y - prev_y)   # per-turn displacement
```

On the **first sighting** of a comet (turn when it spawns), no prior position exists, so `comet_velocities` has no entry for that comet. `intercept()` returns a `(None, None, None)` sentinel for comets with no velocity data, and `plan_expansion` skips them rather than firing at the spawn location (which the comet would have already left by arrival time).

---

## Agent Function

```python
def agent(obs: dict) -> list[list]:
```

**Signature:** receives the raw observation dict, returns a list of moves.

**Return format:** `[[planet_id, angle_rad, num_ships], ...]`

- `planet_id` — integer ID of the **source** planet launching the fleet.
- `angle_rad` — launch angle in radians (math convention: 0 = right, π/2 = down in screen coords).
- `num_ships` — number of ships to send.

The Kaggle engine interprets each triple as: launch `num_ships` from planet `planet_id` in direction `angle_rad`. An empty list `[]` is valid (pass the turn).

**Processing order:**

1. Deserialize `obs['planets']` and `obs['fleets']` into typed namedtuples.
2. Extract `player`, `angular_velocity`, `turn` from obs.
3. Call `get_comet_ids(obs)` to get the current comet set.
4. Populate `_initial_planets` cache on turn 0 or if uninitialized.
5. Compute `comet_velocities` by diffing current comet positions against `_prev_comet_positions`; update `_prev_comet_positions` for next turn.
6. Call `plan_moves(planets, fleets, player, angular_velocity, turn, comet_ids=..., comet_velocities=..., initial_planets=...)` and return its output directly.
