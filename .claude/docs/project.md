# Orbit Wars — Project Context

Kaggle competition bot for the Orbit Wars real-time strategy game; plays as one of up to 4 players on a 100×100 board, sending ship fleets between orbiting planets to capture the most ships by turn 500.

## Tech Stack

- **Python 3.11** — pinned via `.python-version`
- **uv** — package manager; run all commands as `uv run <cmd>`
- **kaggle-environments** — game engine, provides `Planet`, `Fleet`, `CENTER`, `ROTATION_RADIUS_LIMIT`, `SUN_RADIUS` namedtuples/constants
- **pytest** — test runner (dev dependency)
- **kaggle CLI** — submission: `kaggle competitions submit -c orbit-wars -f submission.py -m "msg"`

## Project Layout

```text
src/
  math_utils.py   — orbital math: predict_planet_position, angle_to_target, fleet_speed, turns_to_arrive
  strategy.py     — greedy_expand: scoring, target selection, fleet dispatch
  agent.py        — agent(obs) entry point; unpacks observation, calls greedy_expand
tests/
  test_math_utils.py  — 11 unit tests for math_utils functions
build.py          — bundles src/ → submission.py (strips relative imports, deduplicates kaggle imports)
run_game.py       — local game: our agent vs built-in "starter" agent
submission.py     — build artifact (gitignored); single-file Kaggle submission
```

## Data Flow

```text
obs dict (Kaggle runtime)
  └─ agent(obs)                         [src/agent.py]
       └─ greedy_expand(planets, ...)   [src/strategy.py]
            ├─ predict_planet_position  [src/math_utils.py]  — orbital position after eta turns
            ├─ turns_to_arrive          [src/math_utils.py]  — ETA based on fleet_speed curve
            └─ angle_to_target          [src/math_utils.py]  — atan2 bearing to future position
  └─ returns [[planet_id, angle_rad, num_ships], ...]
```

## Key Architecture Patterns

- **Static planet guard** (`math_utils.py`): `orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT` (i.e., orbital_radius ≥ 40) — planet won't move, return current position.
- **Discrete-period normalisation** (`math_utils.py`): `turns % round(2π / angular_velocity)` prevents floating-point drift for fleets arriving after a full orbital period.
- **Build pipeline** (`build.py`): regex strips `from .module import` lines; injects a single consolidated `kaggle_environments` import block at the top of `submission.py`.

## Game Mechanics (quick ref)

- Board 100×100, sun at (50,50) radius 10, y-axis increases downward
- `angular_velocity` ∈ [0.025, 0.05] rad/turn, uniform for all planets
- Fleet speed: `1 + 5 * (log(ships)/log(1000))^1.5` (1 ship=1.0, 1000 ships=6.0)
- Win condition: most total ships (planets + fleets) at turn 500; ELO scoring

## Test Commands

```bash
uv run pytest tests/ -v    # run all 11 tests
python build.py             # regenerate submission.py
uv run python run_game.py   # local game vs starter agent
```
