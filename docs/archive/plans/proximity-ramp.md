# Plan: Proximity Ramp

> Source PRD: [Orbit-Wars #20](https://github.com/cdcoonce/Orbit-Wars/issues/20)
> Spec: `docs/superpowers/specs/2026-04-27-proximity-ramp-design.md`

## Architectural decisions

- **Ramp pattern**: linear interpolation helper, identical signature to `_effective_min_garrison`
- **Formula**: `greedy_score = (eff_prod + bonus) / (eta + 1) ** dist_power` — exponent is the only change
- **Params**: 3 new entries in both `PARAMS` (defaults) and `PARAM_SPACE` (Optuna bounds)
- **Backwards compatibility**: `distance_power_late` defaults to `2.0` — post-ramp behavior is identical to current

---

## Phase 1: Ramp helper + scoring formula + tests

**User stories**: Agent prefers nearby planets early in the game; behavior normalizes to current formula after the ramp window.

### What to build

Add `_effective_distance_power(turn, params)` to `src/strategy.py`, mirroring `_effective_min_garrison`. Wire it into `plan_expansion` to replace the hardcoded exponent `2`. Add the three new params to `src/config.py` in both `PARAMS` and `PARAM_SPACE`. Add two unit tests to `tests/test_strategy.py` covering the ramp helper and score ordering.

### Acceptance criteria

- [ ] `_effective_distance_power(0, params)` returns `distance_power_early`
- [ ] `_effective_distance_power(distance_ramp_turns, params)` returns `distance_power_late`
- [ ] `_effective_distance_power` interpolates correctly at mid-ramp
- [ ] At turn 0, a closer planet (lower eta) scores proportionally higher vs a farther equal-production planet than it does at turn 200
- [ ] `PARAMS` contains `distance_power_early`, `distance_power_late`, `distance_ramp_turns`
- [ ] `PARAM_SPACE` contains all three with correct types and bounds
- [ ] `uv run pytest tests/ --ignore=tests/test_trial_runner.py` passes

---

## Phase 2: Optuna retune

**User stories**: New distance params are tuned to find the best early-game proximity pressure; champion is updated if the challenger wins.

### What to build

Delete `trials/study.db` to clear stale Bayesian priors from the pre-ramp param space. Run `trials/run_trials.py` to explore the expanded param space. If a challenger achieves ≥55% win rate against the current champion, it is promoted to `trials/champion.py` and its params are copied into `src/config.py`.

### Acceptance criteria

- [ ] `trials/study.db` deleted before run (no stale priors)
- [ ] `uv run python trials/run_trials.py` completes without error
- [ ] If challenger promoted: `trials/champion.py` updated and `src/config.py` `PARAMS` reflects new values
- [ ] `uv run python trials/benchmark.py` shows champion win rate ≥ baseline (original defaults)
