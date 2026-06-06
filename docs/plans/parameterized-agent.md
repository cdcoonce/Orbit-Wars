# Plan: Parameterized Agent + Trial Framework

> Source PRD: [Orbit-Wars #1](https://github.com/cdcoonce/Orbit-Wars/issues/1)
> Spec: docs/superpowers/specs/2026-04-25-parameterized-agent-design.md

## Architectural decisions

- **Params flow**: `PARAMS` dict is the single source of truth; all strategy functions accept a `params` argument defaulting to `PARAMS`. No function in `strategy.py` reads `PARAMS` as a module-level global after Phase 1.
- **Config module**: `src/config.py` exports exactly two names — `PARAMS` (default values) and `PARAM_SPACE` (Optuna bounds with type tags). `send_fractions` is flattened into individual `frac_*` keys; `SKIP_COMBOS` is a fixed set (design decisions, not tunable).
- **`frac_*` lookup convention**: `params.get(f"frac_{src_class.lower()}_{tgt_class.lower()}")` — direct O(1) lookup, no dict rebuild. A missing key (`None`) means skip that combo (same semantics as current `None` entries).
- **Agent boundary**: `agent.py` is the only file that touches the raw `obs` dict. It extracts `comet_ids`, `initial_planets` (turn-0 positions), `player`, `angular_velocity`, and `turn` before calling `plan_moves`.
- **`initial_planets` semantics**: Turn-0 planet positions from `obs["initial_planets"]` (verify this field exists in the kaggle-environments obs schema). In the trial runner, `make_agent()` uses a per-closure cache (`nonlocal initial_planets`, set when `turn == 0`) so each game resets independently — a module-level global would bleed game N's initial state into game N+1.
- **Lookahead normalization**: Min-max normalization `(score - min) / (max - min + ε)` for both greedy and lookahead scores within each source planet's candidate set. Handles negative `score_state()` returns. If candidate set has <2 entries, bypass blending and use raw greedy score directly.
- **Simulation isolation**: `src/lookahead.py` has zero runtime imports from `kaggle_environments`. Uses plain dataclasses and `math_utils` only. `step_state()` signature includes `opponent_fn=None` for forward-compatibility with MCTS.
- **Trial runner isolation**: `trials/` is a standalone directory. It imports from `src/` but nothing in `src/` imports from `trials/`.
- **Champion file**: `trials/champion.py` is auto-generated Python (never hand-edited), committed to git to track champion evolution. Written atomically via temp-file + `os.replace`. All values validated as finite before write.
- **Optuna backend**: SQLite at `trials/study.db` (added to `.gitignore` — large, binary, regeneratable). Enables persistent, resumable, parallel studies without a separate server.

---

## Phase 1: Config extraction + params threading

> **Unblocks Phases 2, 3, and 4. Must land first.**

### What to build

Extract the hardcoded `PARAMS` dict from `src/strategy.py` into a new `src/config.py`, alongside a `PARAM_SPACE` dict that defines Optuna bounds and types for each tunable key. Thread a `params` argument through **every function** in `strategy.py` that currently reads `PARAMS` as an implicit global — this includes `aggression()`, `value_tier()`, `classify_own()`, `classify_neutral()`, `classify_enemy()`, `detect_threats()`, `handle_threats()`, and `plan_expansion()`. All existing behavior is preserved — this is a pure refactor with no logic changes. Also remove the stale `TODO` scaffolding comments from `math_utils.py` (lines 24 and 55 — functions are fully implemented).

### Acceptance criteria

- [ ] `src/config.py` exists and exports `PARAMS` and `PARAM_SPACE`
- [ ] `send_fractions` is flattened into individual `frac_*` keys in `PARAMS` using naming convention `frac_{src_class.lower()}_{tgt_class.lower()}` (e.g. `frac_fortress_easy_neutral`)
- [ ] `PARAM_SPACE` covers all tunable keys with `(low, high, type)` triples; `game_length` is absent (game rule, not tunable)
- [ ] `SKIP_COMBOS` set defined in `src/config.py`
- [ ] `aggression()` accepts a `params` argument and reads `params["aggression_max"]`, `params["aggression_min"]`, `params["game_length"]` — not module globals
- [ ] All 8 functions in `strategy.py` accept a `params` argument (defaulting to `PARAMS`); no function reads `PARAMS` as a global
- [ ] Stale `TODO` comments removed from `math_utils.py` (lines 24 and 55)
- [ ] Test: `set(PARAM_SPACE.keys()) == set(PARAMS.keys()) - {"game_length"}` — asserts completeness
- [ ] All existing tests pass without modification

---

## Phase 2: Comet module

> **Parallel with Phases 3 and 4. Requires Phase 1.**

### What to build

Add `src/comets.py` with two functions: `get_comet_ids()` reads `obs.get("comet_planet_ids") or []` (defensive — field may be absent in older game versions) and returns a `set[int]` for O(1) lookup; `effective_production()` scales a planet's production by `comet_value_multiplier` when it is a comet, otherwise returns raw production unchanged. Update `agent.py` to extract `comet_ids` from obs and pass it into `plan_moves`. Update `strategy.py`'s `value_tier()` and **both** uses of production in `plan_expansion()` — the OUTPOST tier filter and the score formula `(target.production + bonus) / (eta + 1)**2` — to call `effective_production()` instead of `planet.production` directly. A multiplier of `0.0` makes comets effectively invisible to targeting.

### Acceptance criteria

- [ ] `src/comets.py` exports `get_comet_ids(obs) -> set[int]` and `effective_production(planet, comet_ids, multiplier) -> float`
- [ ] `get_comet_ids()` uses `obs.get("comet_planet_ids") or []` — safe when field is absent or `None`
- [ ] `agent.py` extracts `comet_ids` from obs and passes it into `plan_moves`
- [ ] `strategy.py` calls `effective_production()` in both `value_tier()` and the score formula inside `plan_expansion()` (not just the tier filter — the `target.production` in the scoring expression too)
- [ ] Test: `multiplier=0.0` scores comet as zero; `multiplier=2.0` doubles production; non-comet returns raw production
- [ ] Test: `agent.py` correctly passes `comet_ids` extracted from obs into `plan_moves`
- [ ] Test: `get_comet_ids()` returns empty set when key is absent from obs
- [ ] All existing tests pass

---

## Phase 3: Endgame module

> **Parallel with Phases 2 and 4. Requires Phase 1.**

### What to build

Add `src/endgame.py` with two functions: `total_ships()` sums ships on owned planets plus ships in owned in-transit fleets; `should_play_defensive()` returns `True` only when `turn >= endgame_threshold_turn` AND `my_ships / enemy_ships >= endgame_lead_margin`. Guard against `ZeroDivisionError`: if `enemy_ships == 0`, return `False` (a bot can't be "winning by a margin" if the enemy is already eliminated — this is a game-end edge case). Integrate into `plan_moves()`: when the defensive flag is `True`, skip `plan_expansion()` entirely and run only `handle_threats()`. A bot that is losing near turn 500 stays aggressive.

### Acceptance criteria

- [ ] `src/endgame.py` exports `total_ships(planets, fleets, player) -> int` and `should_play_defensive(planets, fleets, player, turn, threshold_turn, lead_margin) -> bool`
- [ ] `should_play_defensive()` returns `False` when `enemy_ships == 0` (ZeroDivisionError guard)
- [ ] `total_ships()` counts both planet ships and in-transit fleet ships for the correct player
- [ ] `plan_moves()` skips expansion when `should_play_defensive()` returns `True`
- [ ] Test: activates when winning (`my/enemy >= lead_margin`) and past threshold turn
- [ ] Test: stays aggressive when behind (ratio < lead_margin), even past threshold turn
- [ ] Test: stays aggressive when before threshold turn, even when winning
- [ ] Test: `enemy_ships == 0` does not raise ZeroDivisionError
- [ ] Test: `agent.py` passes `turn` correctly into `plan_moves` (already does via `obs["step"]` — verify)
- [ ] All existing tests pass

---

## Phase 4: Lookahead simulator

> **Parallel with Phases 2 and 3. Requires Phase 1.**

### What to build

Add `src/lookahead.py` with three dataclasses (`SimPlanet`, `SimFleet`, `GameState`) and three functions: `build_state()` converts immutable kaggle namedtuples to mutable sim objects; `step_state()` simulates one turn (planet rotation via `predict_planet_position`, fleet launch, fleet movement, combat resolution, production); `score_state()` returns a float scoring production advantage plus a weighted ship-count advantage.

`step_state()` signature: `step_state(state, move, player, angular_velocity, initial_planets, opponent_fn=None)`. The `opponent_fn` parameter is unused now (opponent always passes) but makes the interface forward-compatible with MCTS — a future caller can inject an opponent strategy without touching the simulator internals.

Integrate into `plan_expansion()`: for each `(source, target)` candidate, compute both `greedy_score` and `lookahead_score`. Normalize both using **min-max normalization** `(score - min) / (max - min + ε)` across all candidates for that source planet. If the candidate set has fewer than 2 entries, bypass normalization and blending — use the raw greedy score directly. Blend via `lookahead_blend` param. Update `agent.py` to extract `initial_planets` (turn-0 positions) and pass into `plan_moves`.

### Acceptance criteria

- [ ] `src/lookahead.py` exports `SimPlanet`, `SimFleet`, `GameState`, `build_state()`, `step_state()`, `score_state()`
- [ ] No `kaggle_environments` import in `lookahead.py`
- [ ] `step_state()` signature includes `opponent_fn=None` (unused but forward-compatible)
- [ ] `step_state()` correctly: rotates orbiting planets via `predict_planet_position`, deducts ships from source on fleet launch, moves fleets by `fleet_speed(ships)`, resolves combat (largest group wins, difference survives), produces ships on owned planets
- [ ] `plan_expansion()` uses min-max normalization: `(s - lo) / (hi - lo + 1e-9)` for both greedy and lookahead scores
- [ ] `plan_expansion()` bypasses normalization/blending when candidate set has <2 entries
- [ ] `agent.py` extracts `initial_planets` (turn-0 positions) from obs and passes into `plan_moves`; uses per-game closure cache if `obs["initial_planets"]` is not a real obs field
- [ ] `lookahead_blend=0.0` produces identical move selection to pre-Phase-4 behavior
- [ ] Test: `build_state()` produces valid `GameState` from real namedtuples
- [ ] Test: `step_state()` handles planet rotation, fleet movement, combat resolution, production
- [ ] Test: `score_state()` returns a float; returns negative when losing
- [ ] Test: min-max normalization handles all-negative lookahead scores without crashing
- [ ] Test: single-candidate set bypasses blending, returns greedy selection
- [ ] Test: `agent.py` correctly passes `initial_planets` into `plan_moves`
- [ ] All existing tests pass

---

## Phase 5: Trial runner

> **Requires Phases 1, 2, 3, and 4.**

### What to build

Create the `trials/` directory with three files.

`trials/champion.py` — initial champion file containing `CHAMPION_PARAMS` set to the defaults from `PARAMS`. Committed to git; auto-updated by `run_trials.py` on promotion.

`trials/game_runner.py` — provides `make_agent(params)` (returns an agent closure with per-closure `initial_planets` cache so each game resets independently on turn 0), `run_game(params_a, params_b)` wrapped in a `concurrent.futures.ThreadPoolExecutor` with a 60-second timeout (timed-out games count as draws), and `run_games(challenger, champion, n_games)` which alternates player 0/1 assignment across games (game 0: challenger=player 0; game 1: challenger=player 1; etc.) and returns challenger win count.

`trials/run_trials.py` — Optuna study with SQLite persistence, 4 parallel workers, 200 trials. Champion promotion via atomic write (`os.replace`) when win rate meets `PROMOTION_THRESHOLD` (currently ≥ 65%). All promoted values validated as finite before write. Logging via Optuna callback: prints trial number, win rate, best win rate seen so far, and a `[PROMOTED]` flag on each promotion.

Add `trials/study.db` to `.gitignore`.

### Acceptance criteria

- [ ] `trials/champion.py` exists and imports cleanly; `CHAMPION_PARAMS` matches `PARAMS` defaults
- [ ] `make_agent(params)` returns a callable; uses `nonlocal initial_planets` cache that resets when `turn == 0` so each game starts fresh
- [ ] `run_game()` wraps game execution in `concurrent.futures.ThreadPoolExecutor` with 60s timeout; returns `"draw"` on timeout
- [ ] `run_games()` alternates player assignment: game index `i` → challenger is player `i % 2`
- [ ] Champion promotion uses `os.replace` (atomic write); validates all values are finite before write
- [ ] Optuna study uses `load_if_exists=True` — resumable across runs
- [ ] Optuna callback logs: `Trial N: win_rate=X.XX | best=X.XX [PROMOTED]` (PROMOTED only on promotion)
- [ ] Configurable constants at module top: `N_GAMES=10`, `N_WORKERS=4`, `N_TRIALS=200`, `PROMOTION_THRESHOLD=0.55`
- [ ] `trials/study.db` is in `.gitignore`
- [ ] `trials/champion.py` is tracked in git (not gitignored)
- [ ] Test: `make_agent(params)` returns a callable that accepts `obs`
- [ ] Test: `run_games()` alternates player assignment correctly
- [ ] Test: champion write is atomic (temp file + os.replace)
- [ ] Test: timeout returns `"draw"` without raising
