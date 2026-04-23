# Tiered Attack Strategy — Design Spec

**Date:** 2026-04-23
**Status:** Approved

## Summary

Replace the single `greedy_expand` function with a classifier-pipeline strategy that:

1. Classifies own planets, neutral planets, and enemy planets into labeled tiers each turn
2. Detects inbound threats to owned planets
3. Dispatches moves using a source × target matrix, with all thresholds in one `PARAMS` block

The architecture is threat-reactive: the bot stays in expansion mode by default and interrupts only when a specific threat is detected.

---

## Architecture

Two passes per turn inside `plan_moves()`:

```
agent(obs)
  └─ plan_moves(planets, fleets, player, av)
       │
       ├─ Pass 1: Classify
       │    ├─ classify_own(planet)         → OwnClass
       │    ├─ classify_neutral(planet, ships_to_send, av) → NeutralClass
       │    ├─ classify_enemy(planet, ships_to_send, av)   → EnemyClass
       │    └─ detect_threats(my_planets, enemy_fleets)    → list[Threat]
       │
       └─ Pass 2: Dispatch
            ├─ handle_threats(...)     → defensive reinforce moves
            └─ plan_expansion(...)     → offensive moves gated by dispatch matrix
```

`agent.py` calls `plan_moves()` instead of `greedy_expand()`. Everything else lives in `strategy.py`.

---

## Classification

### Own Planet Classes

| Class        | Condition                                                               |
| ------------ | ----------------------------------------------------------------------- |
| `THREATENED` | enemy fleet inbound within `threat_radius` and on intercept course      |
| `FORTRESS`   | ships ≥ `fortress_min_ships` AND production ≥ `fortress_min_production` |
| `FACTORY`    | production ≥ `factory_min_production` (but not FORTRESS)                |
| `OUTPOST`    | everything else                                                         |

Priority: THREATENED is checked first and overrides the others.

### Neutral Planet Classes

Neutral planets do not produce ships, so only ships-on-arrival matters.

| Class          | Condition                                   |
| -------------- | ------------------------------------------- |
| `EASY_NEUTRAL` | ships_to_send / target.ships > `weak_ratio` |
| `HARD_NEUTRAL` | ships_to_send / target.ships ≤ `weak_ratio` |

### Enemy Planet Classes

Enemy planets produce ships during travel, so ETA matters.

| Class             | Condition                                         |
| ----------------- | ------------------------------------------------- |
| `SOFT_ENEMY`      | ships_to_send / expected_defenders > `weak_ratio` |
| `CONTESTED_ENEMY` | ratio between `contested_ratio` and `weak_ratio`  |
| `HARDENED_ENEMY`  | ratio < `contested_ratio`                         |

### Value Tier (used in scoring, not gating)

Used to rank targets within an allowed bucket via `production / (eta + 1)`. Stationary planets get a production bonus of +1 for scoring purposes because they never drift and are reliable long-term investments.

| ValueTier | Condition                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------- |
| `HIGH`    | production ≥ `high_value_production`, or stationary with production ≥ `high_value_production - 1` |
| `MEDIUM`  | production 2–3, or stationary with production ≥ 1                                                 |
| `LOW`     | production ≤ 1 and orbiting                                                                       |

---

## Dispatch Matrix

Gates _whether_ to attack. Scoring picks _which_ target within the allowed set.

| Source       | Target                          | Send Fraction |
| ------------ | ------------------------------- | ------------- |
| `FORTRESS`   | `EASY_NEUTRAL`                  | 0.60          |
| `FORTRESS`   | `HARD_NEUTRAL`                  | 0.75          |
| `FORTRESS`   | `SOFT_ENEMY`                    | 0.65          |
| `FORTRESS`   | `CONTESTED_ENEMY`               | 0.75          |
| `FORTRESS`   | `HARDENED_ENEMY`                | skip          |
| `FACTORY`    | `EASY_NEUTRAL`                  | 0.50          |
| `FACTORY`    | `HARD_NEUTRAL`                  | skip          |
| `FACTORY`    | `SOFT_ENEMY`                    | 0.50          |
| `FACTORY`    | `CONTESTED_ENEMY`               | skip          |
| `FACTORY`    | `HARDENED_ENEMY`                | skip          |
| `OUTPOST`    | `EASY_NEUTRAL` (LOW value only) | 0.40          |
| `OUTPOST`    | anything else                   | skip          |
| `THREATENED` | any offensive                   | skip          |

`THREATENED` planets only receive reinforcements from nearby FORTRESS/FACTORY planets via `handle_threats()`.

The `OUTPOST → EASY_NEUTRAL` row is doubly gated: the target must be both `EASY_NEUTRAL` (capturable) **and** `LOW` value tier. OUTPOSTs do not attack MEDIUM or HIGH value EASY_NEUTRAL targets — those require a FORTRESS or FACTORY to commit the larger garrison needed to hold them.

---

## Threat Detection

For each enemy fleet, project its trajectory forward using `(x, y, angle)` and fleet speed. If the projected path passes within `threat_radius` of any owned planet within `threat_eta_window` turns, flag that planet as `THREATENED` with `Threat(planet_id, incoming_ships, eta)`.

Defense handler selects the nearest non-threatened FORTRESS or FACTORY that can arrive before the fleet does (with an `eta_buffer` turns to spare) and sends `defense_reinforce_fraction` of its garrison.

---

## PARAMS Block

All thresholds and fractions live at the top of `strategy.py`:

```python
PARAMS = {
    # Own planet classification
    "fortress_min_ships": 40,
    "fortress_min_production": 3,
    "factory_min_production": 3,

    # Target value classification
    "high_value_production": 4,
    "stationary_value_bonus": 1,   # added to production when scoring stationary targets

    # Threat level ratios
    "weak_ratio": 1.5,
    "contested_ratio": 1.1,

    # Send fractions per (source_class, target_class) — None = skip
    "send_fractions": {
        ("FORTRESS", "EASY_NEUTRAL"):    0.60,
        ("FORTRESS", "HARD_NEUTRAL"):    0.75,
        ("FORTRESS", "SOFT_ENEMY"):      0.65,
        ("FORTRESS", "CONTESTED_ENEMY"): 0.75,
        ("FORTRESS", "HARDENED_ENEMY"):  None,
        ("FACTORY",  "EASY_NEUTRAL"):    0.50,
        ("FACTORY",  "HARD_NEUTRAL"):    None,
        ("FACTORY",  "SOFT_ENEMY"):      0.50,
        ("FACTORY",  "CONTESTED_ENEMY"): None,
        ("FACTORY",  "HARDENED_ENEMY"):  None,
        ("OUTPOST",  "EASY_NEUTRAL"):    0.40,
    },

    # Defense
    "threat_radius": 5.0,
    "threat_eta_window": 30,
    "defense_reinforce_fraction": 0.5,
    "eta_buffer": 5,

    # Minimums
    "min_garrison": 15,
}
```

---

## File Changes

| File                     | Change                                                                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `src/strategy.py`        | Replace with classifier pipeline: `PARAMS`, classify functions, `detect_threats`, `handle_threats`, `plan_expansion`, `plan_moves` |
| `src/agent.py`           | `greedy_expand` → `plan_moves`                                                                                                     |
| `build.py`               | No change                                                                                                                          |
| `tests/test_strategy.py` | New: unit tests for each classifier function                                                                                       |

---

## What Does Not Change

- `src/math_utils.py` — no changes
- `intercept()` / `can_capture()` / `angle_to_target()` / `turns_to_arrive()` — reused as-is
- Build pipeline and submission format — unchanged
