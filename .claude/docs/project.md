# Orbit Wars — Project Context

Kaggle competition bot for the Orbit Wars real-time strategy game. Up to 4 players on a 100×100 board send ship fleets between orbiting planets to accumulate the most total ships by turn 500.

## Tech Stack

- **Python 3.11** — pinned via `.python-version`
- **uv** — package manager; run commands as `uv run <cmd>`
- **kaggle-environments** — game engine; provides `Planet`, `Fleet`, `CENTER`, `ROTATION_RADIUS_LIMIT`, `SUN_RADIUS` namedtuples/constants
- **pytest** — test runner (130 tests across 7 test files)
- **optuna** — Bayesian hyperparameter search for self-play tuning
- **kaggle CLI** — submission: `kaggle competitions submit -c orbit-wars -f submission.py -m "msg"`

## Project Layout

```text
src/
  agent.py        — entry point: agent(obs) → [[planet_id, angle, ships], ...]
  strategy.py     — plan_moves, plan_expansion, classify_*, detect_threats, handle_threats
  config.py       — PARAMS (active defaults), PARAM_SPACE (Optuna search bounds), SKIP_COMBOS
  math_utils.py   — orbital math: predict_planet_position, angle_to_target, fleet_speed, turns_to_arrive
  comets.py       — effective_production (scales comet value by multiplier), get_comet_ids
  endgame.py      — should_play_defensive: plays pure defense when ahead near turn 500
  lookahead.py    — 1–2 turn simulator: SimPlanet, SimFleet, GameState, build_state, step_state, score_state

tests/
  test_strategy.py           — classify/detect/expand/plan unit tests
  test_lookahead.py          — step_state, score_state, plan_expansion blend integration (33 tests)
  test_math_utils.py         — orbital math unit tests
  test_comets.py             — comet classification unit tests
  test_comets_integration.py — comet × strategy integration tests
  test_endgame.py            — should_play_defensive unit tests
  test_config.py             — PARAMS key coverage
  test_trial_runner.py       — Optuna objective smoke tests (requires optuna)

trials/
  run_trials.py   — Optuna self-play driver (200 trials, 4 workers, promotes at ≥55% win rate)
  champion.py     — CHAMPION_PARAMS: best known params (updated on promotion)
  game_runner.py  — run_games(params_a, params_b, n_games): returns (win_rate, results)
  benchmark.py    — champion vs original hand-tuned defaults (20 games)

build.py          — bundles src/ → submission.py (strips relative imports, deduplicates kaggle imports)
run_game.py       — local game: our agent vs starter agent
submission.py     — build artifact (gitignored)
```

## Data Flow

```text
obs dict (Kaggle runtime)
  └─ agent(obs)                                   [src/agent.py]
       ├─ get_comet_ids(planets)                  [src/comets.py]
       └─ plan_moves(planets, fleets, player, ω)  [src/strategy.py]
            ├─ aggression(turn)                   — linear decay max→min over game_length turns
            ├─ detect_threats(owned, fleets)       — find inbound enemy fleets within threat_radius
            ├─ classify_own(planet, threats)       — FORTRESS / FACTORY / OUTPOST / THREATENED
            ├─ handle_threats(threats, owned)      — reinforce from FORTRESS/FACTORY sources
            ├─ should_play_defensive(...)          — [src/endgame.py] pure defense near game end
            └─ plan_expansion(owned, neutrals, enemies)
                 ├─ classify_neutral(target)       — EASY_NEUTRAL / HARD_NEUTRAL
                 ├─ classify_enemy(target, eta)    — SOFT_ENEMY / CONTESTED_ENEMY / HARDENED_ENEMY
                 ├─ intercept(source, target)      — 2-iter ETA + predicted position
                 ├─ can_capture(ships, target, eta)
                 ├─ effective_production(target)   — [src/comets.py] prod × comet_multiplier
                 └─ lookahead scoring (if blend > 0)
                      ├─ build_state(planets, fleets, turn)   [src/lookahead.py]
                      ├─ opponent_fn = plan_moves(opp, blend=0)  — recursion termination
                      ├─ step_state(state, move, player, ω, opponent_fn)  × lookahead_turns
                      └─ score_state(state, player)           — prod_diff + ship_weight × ship_diff
  └─ returns [[planet_id, angle_rad, num_ships], ...]
```

## Key Architecture Patterns

### Tiered Planet Classifier

Own planets are classified before every expansion decision:

- **FORTRESS** — ≥`fortress_min_ships` ships AND ≥`fortress_min_production`; can attack enemies and hard neutrals
- **FACTORY** — ≥`factory_min_production`; expands to easy neutrals and soft enemies only
- **OUTPOST** — everything else; expands to easy neutrals only (LOW-value targets excluded)
- **THREATENED** — any planet with an inbound enemy fleet; skipped for offense, prioritized for defense

`SKIP_COMBOS` in `config.py` prunes illegal `(src_class, tgt_class)` pairs (e.g. FACTORY never attacks HARDENED_ENEMY).

### Target Classifier

Targets are scored by class using send-fraction params (`frac_{src}_{tgt}`):

- Neutral: `EASY_NEUTRAL` (ships=0 or ratio > weak_ratio) vs `HARD_NEUTRAL`
- Enemy: `SOFT_ENEMY` → `CONTESTED_ENEMY` → `HARDENED_ENEMY` by `ships_to_send / expected_defenders`

### Greedy Score

`(eff_prod + stationary_bonus) / (eta + 1)^2` — production-per-turn discounted by distance.

### Lookahead Simulator (`src/lookahead.py`)

Step order matches the real Kaggle engine:

```text
1. Production    — owned planets += production
2. Rotate        — orbiting planets advance by angular_velocity
3. Our fleet     — launch candidate move
4. Opponent      — opponent_fn(state) → opponent fleet launches
5. Move fleets   — all fleets advance one step
6. Combat        — arrivals resolve; ties → neutral with 0 ships
```

`SimPlanet` and `SimFleet` share attribute names with kaggle namedtuples so `plan_moves` operates on sim objects without conversion (duck-type compatibility).

**Recursion termination**: `opponent_fn` calls `plan_moves` with `lookahead_blend=0.0` forced; `plan_expansion` with `blend=0` never enters the lookahead path, capping recursion depth at 1.

**Opponent precompute**: computed once per source planet (outside the candidate target loop) for O(n) vs O(n²) cost.

### Garrison Ramp

Early-game `min_garrison` ramps linearly from `min_garrison_early` (2) to `min_garrison` (27) over `garrison_ramp_turns` (71) turns, allowing aggressive early expansion without stranding the fleet.

### Endgame Defense

`should_play_defensive` returns True when `turn >= endgame_threshold_turn` AND our total ships exceed the enemy's by `endgame_lead_margin`×. When active, only `handle_threats` defense moves are issued.

### PARAMS / PARAM_SPACE

`src/config.py` holds two dicts:

- `PARAMS` — active defaults used by `plan_moves`; updated to match `trials/champion.py` after each Optuna retune
- `PARAM_SPACE` — `{key: (low, high, type)}` bounds for Optuna search

### Optuna Trial Framework

`trials/run_trials.py` runs self-play: challenger (Optuna sample from PARAM_SPACE) vs current champion (from `champion.py`). Promotion threshold: 55% win rate over 20 games. 4 parallel workers write to a shared `study.db`. On promotion, `champion.py` is atomically overwritten.

When retuning after a major simulator change: **delete `study.db` first** — stale Bayesian priors from a broken simulator mislead sampling.

## Game Mechanics (quick ref)

- Board 100×100, sun at (50,50) radius 10, y-axis increases downward
- `angular_velocity` ∈ [0.025, 0.05] rad/turn, uniform for all planets
- Static planet guard: `orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT` (orbital_radius ≥ 40) → planet doesn't move
- Fleet speed: `1 + 5 * (log(ships)/log(1000))^1.5` (1 ship → 1.0, 1000 ships → 6.0)
- Neutral planets do **not** produce ships; only owned planets produce
- Win condition: most total ships (planets + in-transit fleets) at turn 500; ELO scoring

## Test & Build Commands

```bash
# Tests (fast, no optuna needed)
python -m pytest tests/ --ignore=tests/test_trial_runner.py -v

# Full suite (requires optuna installed)
python -m pytest tests/ -v

# Build submission
python build.py

# Local game vs starter agent
uv run python run_game.py

# Optuna self-play tuning (200 trials, ~30–60 min)
python trials/run_trials.py

# Benchmark champion vs original defaults
python trials/benchmark.py

# Kaggle submission
kaggle competitions submit -c orbit-wars -f submission.py -m "message"
```
