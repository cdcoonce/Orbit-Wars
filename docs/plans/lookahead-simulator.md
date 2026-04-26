# Plan: Lookahead Simulator Improvement

> Source PRD: [Orbit-Wars #8](https://github.com/cdcoonce/Orbit-Wars/issues/8)
> Spec: `docs/superpowers/specs/2026-04-26-lookahead-simulator-improvement.md`

## Architectural decisions

- **No new files** — all changes confined to `src/lookahead.py` and `src/strategy.py`
- **`opponent_fn` interface** — `(state: GameState) -> list[list]`; already present in `step_state` signature as `None`; wired from `strategy.py` (no circular import)
- **Recursion termination** — opponent's `plan_moves` call always uses `lookahead_blend=0.0`; `plan_expansion` with `blend=0` never calls `step_state`; recursion depth is capped at 1
- **Opponent move precomputation** — computed once per source planet before the candidate loop, not once per `(source, target)` pair; trades minor accuracy for O(n) vs O(n²) cost
- **Duck-type compatibility** — `SimPlanet`/`SimFleet` share all attribute names with kaggle namedtuples; `plan_moves` can operate on sim objects without conversion
- **Corrected step order**:
  ```
  1. Production  (owned planets +production)
  2. Rotate      (orbiting planets advance)
  3. Our fleet launch
  4. Opponent fleet launches (opponent_fn)
  5. Move all fleets
  6. Combat
  ```

---

## Phase 1: Production step order fix

**User stories**: 1, 6

### What to build

Move the production step in `step_state` from the end (after combat) to the beginning (before rotation and fleet launch). This makes the simulator match the real Kaggle game engine, where planets produce ships at the start of each turn before any movement or combat resolves.

Update the existing test that asserts post-capture ship counts — a newly-captured neutral planet no longer receives production in the same turn it's captured (neutral doesn't produce, and the new owner's production applies next turn). Add a new test that proves production fires before combat by showing a 1-ship planet + 1 production survives a 2-ship attack.

### Acceptance criteria

- [ ] `step_state` with no move and one owned planet with `production=2`: ships increase by 2 per step (unchanged behavior)
- [ ] `step_state` with neutral planet: no production added regardless of step order (unchanged)
- [ ] A planet with 1 ship and `production=1` survives an arriving fleet of 2 ships (produces first → 2 defenders → tie or defeat for attacker)
- [ ] `test_fleet_captures_neutral_planet` updated: expected ships after capture is 7, not 8
- [ ] All existing `TestStepState` and `TestScoreState` tests pass

---

## Phase 2: Opponent model + `lookahead_turns` wiring

**User stories**: 2, 3, 4, 5, 7, 8

### What to build

Wire the existing `opponent_fn=None` slot in `step_state` to actually apply opponent fleet launches when provided. The opponent moves are deducted from their source planets and added as in-transit fleets before the movement step.

In `plan_expansion`, construct an `opponent_fn` closure (when `blend > 0`) that calls `plan_moves` on the opponent's planets with `lookahead_blend=0.0` forced. Precompute this response once per source planet (from the base state, before the candidate loop) to keep the per-candidate cost O(1).

Wire `lookahead_turns` so the candidate evaluation loop calls `step_state` `lookahead_turns` times: T+1 uses the candidate move, T+2+ use the acting player's greedy best move (also with `blend=0`). Both players respond greedily at every depth beyond 1.

### Acceptance criteria

- [ ] `step_state` with a non-None `opponent_fn` returning one move: opponent
      fleet appears in `state.fleets` and opponent source planet loses ships
- [ ] `step_state` with `opponent_fn=None` (default): behavior identical to
      Phase 1 result (no regression)
- [ ] Recursion termination: a counter-incrementing `opponent_fn` asserts call
      count == 1 per `step_state` invocation (not recursive); 1s smoke test secondary
- [ ] Silent-skip guard: when precomputed opponent move references a planet with
      insufficient ships, no fleet is added and no exception is raised
- [ ] `plan_expansion` with `lookahead_turns=2`: `state.turn == original_turn + 2`
      after scoring; score differs from `lookahead_turns=1` when turn 2 matters
- [ ] `opponent_fn` constructed once per source planet (not per candidate):
      mock asserts call count == number of source planets, not number of candidates
- [ ] `plan_expansion` with `lookahead_turns=1, blend=0` picks same target as
      pure greedy (regression guard)
- [ ] `plan_expansion` with `lookahead_turns=1, blend=1, opponent_fn` active:
      opponent planet count reduces correctly in scored state
- [ ] `step_state` docstring updated: `opponent_fn` is now wired, not a stub
- [ ] All existing `TestPlanExpansionBlend` tests pass

---

## Phase 3: Optuna retune

**User stories**: 7

### What to build

The prior `study.db` was optimized against the broken simulator — its trial data is misleading for the new `lookahead_blend` search space. Delete it and run a fresh 200-trial Optuna pass. `lookahead_turns` (1 or 2) remains in `PARAM_SPACE` so Optuna can discover whether 2-turn depth is worth the cost. Promote the best challenger to champion and run the 20-game benchmark against original defaults to verify improvement vs the 85% baseline.

### Acceptance criteria

- [ ] `src/config.py` PARAMS updated from current `trials/champion.py` before
      deleting `study.db` (preserve garrison-ramp champion params as baseline)
- [ ] `study.db` deleted; `trials/champion.py` preserved
- [ ] 200-trial Optuna run completes without error
- [ ] New champion promoted and written to `trials/champion.py`
- [ ] `trials/benchmark.py` run: champion win rate vs original defaults reported
- [ ] `src/config.py` PARAMS updated to reflect the new champion values
- [ ] Promoted champion's `lookahead_blend` is notably higher than pre-fix
      value (~0.05), confirming the simulator now provides useful signal
