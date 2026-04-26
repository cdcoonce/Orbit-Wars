# Lookahead Simulator Improvement — Design Spec

**Date:** 2026-04-26
**Status:** Draft

---

## Overview

The current 1-turn lookahead simulator has three known problems:

1. **Dead `lookahead_turns` param** — `plan_expansion` always calls `step_state` once regardless of its value.
2. **Passive opponent model** — `step_state` assumes the opponent passes; in practice the opponent expands, so our lookahead scores systematically overestimate the value of slow moves.
3. **Production step order bug** — production runs _after_ combat in `step_state`, but the real game engine adds production before movement. This causes the simulator to underestimate defenders at arrival, making attacks look easier than they are.

Fixing these should move `lookahead_blend` from a near-zero value (Optuna keeps finding ~0.05 is optimal, implying the current simulator is nearly useless) toward a meaningful signal, and improve overall play quality.

**ELO context:** Currently at 636 (baseline 600). Self-play tuning is hitting diminishing returns; opponent modeling is the next real strategic lever.

---

## Architecture

No new files. All changes are confined to two files:

```
src/
  lookahead.py    ← production step order fix + opponent_fn wiring
  strategy.py     ← build opponent_fn, wire lookahead_turns loop

tests/
  test_lookahead.py  ← update test_fleet_captures_neutral_planet + new tests
```

---

## Issue 1: Production Step Order Fix

### Current (wrong) order in `step_state`

```
Step 1: Rotate orbiting planets
Step 2: Launch fleet from move
Step 3: Move all fleets
Step 4: Combat (resolve arrivals)
Step 5: Production ← WRONG POSITION
```

### Correct order (matching Kaggle game engine)

The Kaggle game engine adds production at the START of each turn — before movement or combat. Evidence: the `can_capture` check in `strategy.py` uses `target.ships + target.production * eta`, adding production for every turn including turn 0 of the fleet's journey. This is only correct if the planet produces on the SAME turn the fleet departs, not after it arrives.

```
Step 1: Production (all owned planets +production)  ← MOVED HERE
Step 2: Rotate orbiting planets
Step 3: Launch fleet from move
Step 4: Move all fleets
Step 5: Combat (resolve arrivals)
```

### Effect

- Planets defend with an extra turn of ships at combat time → attacks that barely succeeded in the old sim now fail → more accurate `can_capture` / lookahead agreement.
- Neutral planets are unaffected (they don't produce regardless of position).

### Test impact

`test_fleet_captures_neutral_planet` currently expects:

```
7 ships after combat + 1 production at end = 8 ships
```

After the fix it becomes:

```
neutral has 2 ships (no production), fleet wins with 8-2=6 survive → takeover -1 → 7 ships
(no production at end of step for the captured planet — it produces next turn)
```

Update assertion: `assert p.ships == 7`.

Add a new test `test_production_runs_before_combat` that verifies a planet with 1 ship + 1 production/turn survives an attack from 2 ships (because after production it has 2 ships → tie → attacker fails to capture).

---

## Issue 2: Opponent Model

### Design principle

`lookahead.py` must NOT import from `strategy.py` (circular import). Instead, `strategy.py` constructs an `opponent_fn` callable and passes it into `step_state`. The `opponent_fn` signature is `(state: GameState) -> list[list]` — returns a list of `[planet_id, angle, ships]` moves.

`step_state` already has `opponent_fn=None` in its signature (reserved slot). We now wire it up.

### Recursion termination

The opponent's `plan_moves` call **must** use `lookahead_blend=0.0`. If it used the full params (blend > 0), it would call `step_state` again, which would call `opponent_fn` again → infinite recursion. The `lookahead_blend=0.0` override is the hard termination condition.

```
plan_expansion (blend > 0)
  └─ step_state(our_move, opponent_fn=greedy_opp)
       └─ opponent_fn(state)
            └─ plan_moves(..., params={blend=0})   ← no further lookahead
                 └─ plan_expansion(blend=0)        ← pure greedy, no step_state
```

### Performance: precompute opponent moves once per source planet

`step_state` is called inside `plan_expansion`'s inner loop — once per `(source, target)` candidate pair. If we called `plan_moves` inside each `step_state` invocation, total work per turn would scale as O(n_sources × n_targets × plan_moves_cost), which is O(n²) instead of O(n).

**Solution:** compute opponent moves once per source planet, before the candidate loop. Pass the precomputed moves list into `step_state` as the `opponent_fn` result.

```
Accuracy trade-off: opponent is responding to the base state, not to our specific
candidate move. This is slightly inaccurate — if we launch 40 ships, the opponent
sees 40 fewer ships available — but good enough for a 1–2 turn horizon and orders
of magnitude cheaper.
```

Implementation in `plan_expansion`:

```python
# Once per source planet, outside candidate loop:
if blend > 0 and initial_planets is not None and fleets is not None:
    opp_player = 1 - player
    greedy_params = {**params, "lookahead_blend": 0.0}
    base_state_for_opp = build_state(initial_planets, fleets, turn)
    precomputed_opp_moves = plan_moves(
        base_state_for_opp.planets, base_state_for_opp.fleets,
        opp_player, angular_velocity, turn=turn,
        params=greedy_params, initial_planets=initial_planets,
    )
    def opponent_fn(state):
        return precomputed_opp_moves  # captured from outer scope
else:
    opponent_fn = None
```

### Inside `step_state` — applying opponent moves

After launching our fleet (current Step 2→3), apply opponent moves before advancing fleets:

```python
# After launching our fleet:
if opponent_fn is not None:
    opp_moves = opponent_fn(state)
    for opp_move in opp_moves:
        planet_id, angle, ships = opp_move[0], opp_move[1], opp_move[2]
        opp_source = next((p for p in state.planets if p.id == planet_id), None)
        if opp_source is not None and opp_source.ships >= ships:
            opp_source.ships -= ships
            state.fleets.append(SimFleet(
                owner=1 - player,
                x=opp_source.x, y=opp_source.y,
                angle=angle, ships=ships,
            ))
```

The guard `opp_source.ships >= ships` prevents over-deducting in edge cases where the base-state opponent moves are stale relative to the candidate's effect on the state.

### Duck typing compatibility

`plan_moves` in `strategy.py` accesses planet/fleet attributes by name only — it does not check `isinstance`. `SimPlanet` and `SimFleet` have the same attribute set as the Kaggle namedtuples, so passing `state.planets` and `state.fleets` directly to `plan_moves` works without conversion.

Fields matched:

- `SimPlanet`: `id, owner, x, y, radius, ships, production` ✓
- `SimFleet`: `owner, x, y, angle, ships` ✓

---

## Issue 3: Wire Up `lookahead_turns`

Currently `plan_expansion` always calls `step_state` exactly once. When `lookahead_turns=2`, we want:

- **T+1**: apply our candidate move + opponent greedy response
- **T+2**: apply our greedy move + opponent greedy response → score this state

For T+2, "our greedy move" means calling `plan_moves` on the T+1 state with `lookahead_blend=0.0` — the same greedy-only override used for the opponent. Both players are greedy at T+2; only the T+1 move uses our candidate.

```python
# In plan_expansion, replace single step_state call:
if blend > 0 and initial_planets is not None and fleets is not None:
    state = build_state(initial_planets, fleets, turn)
    candidate_move = [source.id, angle_to_target(...), ships_to_send]

    # T+1: our candidate move + opponent response
    state = step_state(state, candidate_move, player, angular_velocity,
                       initial_planets, opponent_fn)

    # T+2 and beyond (when lookahead_turns > 1):
    n_extra = params.get("lookahead_turns", 1) - 1
    for _ in range(n_extra):
        greedy_params = {**params, "lookahead_blend": 0.0}
        our_greedy_moves = plan_moves(
            state.planets, state.fleets, player, angular_velocity,
            turn=state.turn, params=greedy_params, initial_planets=initial_planets,
        )
        our_move_t2 = our_greedy_moves[0] if our_greedy_moves else None
        state = step_state(state, our_move_t2, player, angular_velocity,
                           initial_planets, opponent_fn)

    lookahead_score = score_state(state, player, params.get("lookahead_ship_weight", 0.01))
```

### Performance note for lookahead_turns=2

When `lookahead_turns=2`, per-candidate cost is:

- T+1: 1 `step_state` call (opponent moves already precomputed)
- T+2: 1 `plan_moves` call (greedy, our moves) + 1 `step_state` call

The T+2 `plan_moves` call is O(n_sources × n_targets). This runs once per candidate pair at depth 2, making the inner loop O(n_sources × n_targets²) at `lookahead_turns=2`. With ~10 planets this is ~100 operations — still fast.

Estimated overhead:

- `lookahead_turns=1` with opponent model: ~2× current cost per turn
- `lookahead_turns=2` with opponent model: ~4× current cost per turn
- At 5ms/turn current budget: 20ms at 4×, well within 1-second limit.

---

## Issue 4: Retune `lookahead_blend` via Optuna

After the simulator is fixed, `lookahead_blend` should be retuned. The current champion value (~0.05) reflects that the old simulator was nearly useless. The new simulator should allow a higher blend to improve selection quality.

Steps:

1. Implement all three fixes above and commit
2. Update `trials/champion.py` to reset to a neutral starting point for the affected params (or just delete `study.db` and start fresh — prior trials used the broken simulator)
3. Run 200-trial Optuna pass to find the new optimal `lookahead_blend` and `lookahead_turns`

`lookahead_turns` should remain in `PARAM_SPACE` as `(1, 2, int)`. Optuna may discover that `lookahead_turns=2` is not worth the cost, which is also useful signal.

---

## Step Order Summary (after all fixes)

```
step_state() turn simulation order:
  1. Production       — owned planets produce ships
  2. Rotate           — orbiting planets advance by angular_velocity
  3. Our fleet launch — deduct from source, add SimFleet
  4. Opponent moves   — if opponent_fn provided, apply each move
  5. Move all fleets  — each fleet advances by fleet_speed along angle
  6. Combat           — resolve arrivals, update owners
```

---

## Test Plan

| Test                                            | File                | Description                                                                   |
| ----------------------------------------------- | ------------------- | ----------------------------------------------------------------------------- |
| `test_production_runs_before_combat`            | `test_lookahead.py` | Planet survives 2-ship attack because production gives it 2 defenders         |
| `test_fleet_captures_neutral_planet` (update)   | `test_lookahead.py` | Change expected ships from 8 → 7                                              |
| `test_opponent_fn_applied`                      | `test_lookahead.py` | Opponent fleet appears in fleets list after step_state with opponent_fn       |
| `test_opponent_fn_deducts_ships`                | `test_lookahead.py` | Opponent source planet loses ships when opponent_fn fires                     |
| `test_opponent_fn_blend_zero_no_recursion`      | `test_lookahead.py` | Passing a real plan_moves-based opponent_fn doesn't hang (terminates in < 1s) |
| `test_lookahead_turns_2_calls_step_state_twice` | `test_lookahead.py` | Mock step_state, verify call count = lookahead_turns                          |
| `test_lookahead_turns_1_matches_old_behavior`   | `test_lookahead.py` | With turns=1, scores identical to baseline (regression guard)                 |

---

## Out of Scope

- MCTS / tree search (depth > 2)
- Opponent move caching across turns (per-turn cache is sufficient)
- Per-pair (not per-source) opponent response (too expensive)
- Comet evacuation logic
- Kaggle submission gating (submit manually after Optuna converges)
