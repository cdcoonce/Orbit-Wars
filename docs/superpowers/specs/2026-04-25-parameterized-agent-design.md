# Parameterized Agent + Trial Framework — Design Spec

**Date:** 2026-04-25
**Status:** Approved

---

## Overview

Extend the Orbit Wars bot with three new strategic features (comet handling, endgame mode, lookahead) and a full Optuna-based trial framework for automated parameter tuning via local self-play. All strategic behavior is expressed through a single `PARAMS` dict; all tunable bounds live in `PARAM_SPACE`. Optuna runs a challenger-vs-champion tournament to find the best config.

---

## Architecture

```
src/
  config.py         # PARAMS dict + PARAM_SPACE bounds (single source of truth for Optuna)
  math_utils.py     # unchanged
  comets.py         # get_comet_ids(), effective_production()
  endgame.py        # total_ships(), should_play_defensive()
  lookahead.py      # SimPlanet, SimFleet, GameState, build_state(), step_state(), score_state()
  strategy.py       # updated to accept params + integrate new modules
  agent.py          # updated to pass comet_ids + initial_planets through

trials/
  champion.py       # CHAMPION_PARAMS dict — auto-generated, never hand-edited
  game_runner.py    # make_agent(), run_game(), run_games()
  run_trials.py     # Optuna study, objective function, champion promotion
```

**Key principle:** `strategy.py` is the orchestrator — it calls feature modules but doesn't know their internals. `agent.py` is the only file that touches the raw `obs` dict.

---

## Config Module (`src/config.py`)

Two exports: `PARAMS` (default values) and `PARAM_SPACE` (Optuna bounds).

`send_fractions` is **flattened** into individual keys so Optuna can tune each independently. Combos that are never taken (previously `None`) live in a fixed `SKIP_COMBOS` set — design decisions, not tunable values.

```python
PARAMS = {
    # Own planet classification
    "fortress_min_ships": 40,
    "fortress_min_production": 3,
    "factory_min_production": 3,

    # Target value
    "high_value_production": 4,
    "medium_value_production": 2,
    "stationary_value_bonus": 1,

    # Threat ratios
    "weak_ratio": 1.5,
    "contested_ratio": 1.1,

    # Send fractions (flattened)
    "frac_fortress_easy_neutral":    0.60,
    "frac_fortress_hard_neutral":    0.75,
    "frac_fortress_soft_enemy":      0.65,
    "frac_fortress_contested_enemy": 0.75,
    "frac_factory_easy_neutral":     0.50,
    "frac_factory_soft_enemy":       0.50,
    "frac_outpost_easy_neutral":     0.40,
    "frac_outpost_soft_enemy":       0.40,

    # Defense
    "threat_radius": 5.0,
    "threat_eta_window": 30,
    "defense_reinforce_fraction": 0.5,
    "eta_buffer": 5,
    "min_garrison": 15,

    # Aggression curve
    "aggression_max": 1.0,
    "aggression_min": 0.6,
    "game_length": 500,             # fixed — game rule, not tunable

    # Comets
    "comet_value_multiplier": 1.0,  # 0=avoid, >1=prefer

    # Endgame
    "endgame_threshold_turn": 450,  # turn endgame check activates
    "endgame_lead_margin": 1.2,     # my_ships/enemy_ships ratio to go defensive

    # Lookahead
    "lookahead_turns": 1,           # 1 or 2
    "lookahead_blend": 0.5,         # 0=pure greedy, 1=pure lookahead score
    "lookahead_ship_weight": 0.01,  # weight of ship-count advantage vs production in score_state
}

SKIP_COMBOS = {
    ("FORTRESS", "HARDENED_ENEMY"),
    ("FACTORY",  "HARD_NEUTRAL"),
    ("FACTORY",  "CONTESTED_ENEMY"),
    ("FACTORY",  "HARDENED_ENEMY"),
}

PARAM_SPACE = {
    "fortress_min_ships":            (20,   60,   int),
    "fortress_min_production":       (2,    5,    int),
    "factory_min_production":        (2,    5,    int),
    "high_value_production":         (3,    6,    int),
    "medium_value_production":       (1,    4,    int),
    "stationary_value_bonus":        (0,    3,    int),
    "weak_ratio":                    (1.1,  2.5,  float),
    "contested_ratio":               (0.8,  1.5,  float),
    "frac_fortress_easy_neutral":    (0.4,  0.9,  float),
    "frac_fortress_hard_neutral":    (0.5,  0.95, float),
    "frac_fortress_soft_enemy":      (0.4,  0.9,  float),
    "frac_fortress_contested_enemy": (0.5,  0.95, float),
    "frac_factory_easy_neutral":     (0.3,  0.8,  float),
    "frac_factory_soft_enemy":       (0.3,  0.8,  float),
    "frac_outpost_easy_neutral":     (0.2,  0.7,  float),
    "frac_outpost_soft_enemy":       (0.2,  0.7,  float),
    "threat_radius":                 (3.0,  8.0,  float),
    "threat_eta_window":             (10,   50,   int),
    "defense_reinforce_fraction":    (0.3,  0.7,  float),
    "eta_buffer":                    (2,    10,   int),
    "min_garrison":                  (5,    30,   int),
    "aggression_max":                (0.7,  1.0,  float),
    "aggression_min":                (0.3,  0.8,  float),
    "comet_value_multiplier":        (0.0,  3.0,  float),
    "endgame_threshold_turn":        (380,  490,  int),
    "endgame_lead_margin":           (1.05, 2.0,  float),
    "lookahead_turns":               (1,    2,    int),
    "lookahead_blend":               (0.0,  1.0,  float),
    "lookahead_ship_weight":         (0.001, 0.1, float),
}
```

`game_length` is not in `PARAM_SPACE` — it's a game rule.

---

## Feature Modules

### `src/comets.py`

Two functions:

- `get_comet_ids(obs: dict) -> set[int]` — reads `obs["comet_planet_ids"]`, returns a set for O(1) lookup. Comets are exposed directly by the game engine; no inference needed.
- `effective_production(planet, comet_ids, multiplier) -> float` — returns `planet.production * multiplier` if the planet is a comet, else `planet.production` unchanged.

`strategy.py`'s `value_tier()` and the scoring inside `plan_expansion()` call `effective_production()` instead of `planet.production` directly. A multiplier of `0.0` makes comets score zero — effectively excluding them from targeting. A multiplier of `2.0` makes them twice as attractive as their raw production suggests.

**Future upgrade (not in scope):** capture + evacuate logic — track comet departure turn from `obs["comets"]` and send ships off before it leaves.

---

### `src/endgame.py`

Two functions:

- `total_ships(planets, fleets, player) -> int` — sum of ships on owned planets + ships in owned fleets in transit. Both count toward the turn-500 score.
- `should_play_defensive(planets, fleets, player, turn, threshold_turn, lead_margin) -> bool` — returns `True` when `turn >= threshold_turn` AND `my_ships / enemy_ships >= lead_margin`.

When `should_play_defensive` returns `True`, `plan_moves` skips expansion entirely and only runs `handle_threats`. If we're _behind_ on total ships near turn 500, the bot stays aggressive — a losing bot going passive hands the win over.

---

### `src/lookahead.py`

A lightweight state simulator — no `kaggle_environments` overhead, fast enough to call inside the turn loop.

**Data structures:**

```python
@dataclass
class SimPlanet:
    id: int; owner: int; x: float; y: float
    radius: float; ships: int; production: int

@dataclass
class SimFleet:
    owner: int; x: float; y: float; angle: float; ships: int

@dataclass
class GameState:
    planets: list[SimPlanet]
    fleets: list[SimFleet]
    turn: int
```

**Functions:**

- `build_state(planets, fleets, turn) -> GameState` — converts immutable namedtuples to mutable sim objects
- `step_state(state, move, player, angular_velocity, initial_planets) -> GameState` — simulates one turn:
  1. Rotate orbiting planets: `angle = initial_angle + angular_velocity * new_turn`
  2. Launch new fleets from move (deduct ships from source planet)
  3. Move all fleets by `fleet_speed(ships)` along their angle
  4. Resolve combat: fleets within `planet.radius` of a planet → largest group wins, difference survives
  5. Produce ships on all owned planets
  - Opponent is assumed to pass (no moves). Known simplification; accurate enough for 1–2 turn horizon.
- `score_state(state, player) -> float` — `(my_production - enemy_production) + ship_weight * (my_ships - enemy_ships)`, production-weighted since production compounds.

**Integration into `plan_expansion`:** for each `(source, target)` pair, compute both scores:

```
greedy_score    = (effective_production + bonus) / (eta + 1)²
lookahead_score = score_state(step_state(..., candidate_move, ...), player)
```

Before blending, both scores are normalized to `[0, 1]` within the candidate set for that source planet (divide each by `max(scores) + ε`). This keeps the blend scale-invariant regardless of game state magnitude.

```
final_score = (1 - blend) * norm_greedy + blend * norm_lookahead
```

`blend=0.0` reproduces today's behavior exactly. `blend=1.0` uses pure lookahead. Optuna finds the right blend — it may discover that 0.0 is optimal, which is also useful signal.

---

## Trial Runner

### `trials/champion.py`

Auto-generated Python file, never hand-edited:

```python
# Written by run_trials.py on promotion — do not edit manually
CHAMPION_PARAMS = { ... }
```

Written atomically on promotion (write to temp file, rename) so parallel workers never read a half-written champion.

---

### `trials/game_runner.py`

- `make_agent(params) -> callable` — returns an agent closure that captures its `params` dict and calls `plan_moves(..., params)`
- `run_game(params_a, params_b) -> str` — runs one game via `kaggle_environments`, returns `"a_wins"`, `"b_wins"`, or `"draw"`
- `run_games(challenger, champion, n_games) -> int` — runs `n_games` games alternating player 0/1 assignment (eliminates first-mover bias), returns challenger win count

---

### `trials/run_trials.py`

```python
study = optuna.create_study(
    study_name="orbit-wars",
    storage="sqlite:///trials/study.db",  # persists across runs, enables parallel workers
    direction="maximize",
    load_if_exists=True,
)
study.optimize(objective, n_trials=N_TRIALS, n_jobs=N_WORKERS)
```

Objective function:

1. Sample challenger from `PARAM_SPACE` (int vs float via `suggest_int` / `suggest_float`)
2. Fill non-tunable keys from `PARAMS`
3. Call `run_games(challenger, CHAMPION_PARAMS, N_GAMES)`
4. If `win_rate >= PROMOTION_THRESHOLD` → promote challenger to champion
5. Return win rate

**Defaults:**

- `N_GAMES = 10` — enough signal, fast enough. Tune down to 6–8 for faster iteration.
- `N_WORKERS = 4` — parallel Optuna workers via SQLite coordination
- `N_TRIALS = 200`
- `PROMOTION_THRESHOLD = 0.55` — avoids noise-driven promotions (50% is too easy to clear with 10 games)

**Expected speed:** ~10–30 seconds/trial with 4 workers → 200 trials in roughly 10–15 minutes.

---

## Changes to Existing Files

| File                       | Change                                                                                                                                             |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/agent.py`             | Pass `comet_ids` and `initial_planets` from `obs` into `plan_moves`                                                                                |
| `src/strategy.py`          | Accept `params` arg everywhere; integrate comet/endgame/lookahead calls; rebuild `send_fractions` dict from flat keys + `SKIP_COMBOS` at call time |
| `tests/test_math_utils.py` | No changes                                                                                                                                         |
| `tests/test_strategy.py`   | Update to pass `params` arg; add tests for comet/endgame/lookahead integration                                                                     |

---

## Out of Scope

- Comet evacuation logic (future upgrade — foundation laid via `comet_value_multiplier`)
- MCTS / deeper search (Phase 4 if lookahead hits a ceiling)
- Kaggle submission gating (submit manually after local trials converge)
- Opponent modeling in lookahead simulator
