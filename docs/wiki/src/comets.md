## Overview

`src/comets.py` provides two small utilities for handling comet planets — transient visitors that appear on the map temporarily. The key design decision is that comets are discounted relative to their raw production via a tunable multiplier, making permanent planets more attractive by default.

Cross-links: [Strategy](strategy.md) | [Config](config.md) | [Home](../Home.md)

---

## Functions

### `get_comet_ids(obs) -> set[int]`

```python
def get_comet_ids(obs: dict) -> set[int]:
    return set(obs.get("comet_planet_ids") or [])
```

Extracts the set of planet IDs currently designated as comets from the observation dict.

The `or []` guard handles two failure modes cleanly:

- Key absent: `obs.get("comet_planet_ids")` returns `None` → `None or []` → `[]` → `set()`.
- Key present but value is `None`: same path.
- Key present with a list: `list or []` → the list (truthy) → `set(list)`.

Always returns a `set`, never `None` or a list. Called once per turn in `agent.py` and forwarded to `plan_moves` and `value_tier`.

---

### `effective_production(planet, comet_ids, multiplier) -> float`

```python
def effective_production(planet: Planet, comet_ids: set, multiplier: float) -> float:
    if planet.id in comet_ids:
        return planet.production * multiplier
    return float(planet.production)
```

Returns the production value used for scoring this planet.

- If `planet.id in comet_ids`: returns `production * multiplier` (scaled, possibly zero).
- Otherwise: returns `float(production)` — raw production, unaffected by `multiplier`.

**Multiplier semantics:**

| `multiplier` | Effect                                                                |
| :----------: | --------------------------------------------------------------------- |
|    `0.0`     | Comets are invisible to targeting (score contribution = 0)            |
|   `< 1.0`    | Comets are less attractive than their raw production suggests         |
|    `1.0`     | Comets treated identically to permanent planets                       |
|   `> 1.0`    | Comets are more attractive than permanent planets of equal production |

---

## Behavioral Impact of `comet_value_multiplier`

The default `comet_value_multiplier` in PARAMS is `2.22475` (Optuna-tuned; see `config.py` for full precision). This makes comets **more** attractive than permanent planets on paper. However, this parameter interacts with the broader scoring context — a comet with production 2 scores as production 4.45, competing against permanent planets that compound every turn.

**Why comets might still be discounted strategically:** even if the multiplier is above 1.0, comets are transient. A planet you capture this turn may not be yours next turn if it leaves the map. Permanent planets compound production indefinitely — their long-term value exceeds any comet's short-horizon contribution. The multiplier is the primary knob for tuning comet attractiveness; Optuna found that a value above 1.0 works well in practice (aggressive comet capture), but this is game-length and map dependent.

**For re-tuning:** if comets are causing overextension (bot loses ships chasing temporary planets), lower `comet_value_multiplier` toward `0.5`–`1.0`. If comets are being ignored when they're clearly high-value, raise it. Range in `PARAM_SPACE`: `(0.0, 3.0)`.
