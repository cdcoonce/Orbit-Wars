## Gotchas Index

Subtle behaviors, non-obvious invariants, and traps that have caused or could cause bugs. Ordered by module.

Cross-links: [Home](Home.md) | [Strategy](src/strategy.md) | [Lookahead](src/lookahead.md) | [Math Utils](src/math_utils.md) | [Endgame](src/endgame.md)

---

## Lookahead (`src/lookahead.py`)

**Foothold cost** — when a planet changes hands in the simulator, `planet.ships` is set to `surviving - 1`, not `surviving`. The real Kaggle engine does NOT deduct this extra ship. It is a deliberate pessimism bias to discourage the lookahead from over-valuing conquest moves that land with only a 1-ship margin. → [lookahead](src/lookahead.md)

**Recursion cap** — `opponent_fn` is only constructed when `lookahead_blend > 0` and `initial_planets` is available; otherwise it is `None`. When it IS constructed, the `plan_moves` call that generates `_opp_moves` uses `greedy_params_opp = {**params, "lookahead_blend": 0.0}`. This forces the opponent's `plan_expansion` to use pure greedy scoring (blend=0), so it never builds its own `opponent_fn` — preventing unbounded mutual recursion. The cap is in the params passed to `plan_moves`, not in a guard inside `step_state`. → [lookahead](src/lookahead.md)

**Duck-typing** — `SimPlanet` and `SimFleet` attribute names are intentionally identical to the Kaggle engine's `Planet` and `Fleet` namedtuple field names. All strategy functions (`plan_moves`, `detect_threats`, `intercept`, etc.) accept either the real Kaggle objects or the sim objects without branching. Breaking this name alignment will silently corrupt simulation results. → [lookahead](src/lookahead.md)

**Combat tie** — ties break to the incumbent owner. When the winning owner's surviving ships equal zero after combat resolution (an attack that exactly matches the defense), the planet stays with its current owner at `ships=0` rather than collapsing to neutral — this keeps the lookahead from undervaluing defensive holds. A neutral planet (`owner=-1`) defending itself wins its own ties the same way, so it stays neutral with `ships=0`. The planet only flips to `owner=-1` when the tie (or full cancellation, `surviving < 0`) is won by a _non-incumbent_ — e.g., two equal-size attacker fleets cancel each other on a contested planet. → [lookahead](src/lookahead.md)

**`build_state` copies** — `build_state` does a full field-by-field copy of every planet and fleet into new mutable dataclass instances. `step_state` mutates state in place. Each independent lookahead branch requires a fresh `build_state` call. Reusing the same `GameState` across branches corrupts results silently. → [lookahead](src/lookahead.md)

---

## Math Utils (`src/math_utils.py`)

**Sun-crossing guard** — `path_crosses_sun` checks whether a straight-line segment passes within `SUN_RADIUS=10` of `CENTER=(50,50)`. Both `handle_threats` and `plan_expansion` call this check and **silently skip** any move that would cross the exclusion zone. No error is raised; the move is simply dropped. Debugging missing moves? Check sun proximity first. → [math_utils](src/math_utils.md)

**Stationary planet distinction** — the threshold is `orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT`, i.e., `orbital_radius + 10 >= 50`, i.e., `orbital_radius >= 40`. A planet 40 units from center is stationary; a planet 39 units from center orbits. This compound check is used in both `predict_planet_position` (math_utils) and `is_stationary` (strategy). The two functions must stay in sync. → [math_utils](src/math_utils.md)

---

## Endgame (`src/endgame.py`)

**ZeroDivisionError guard** — `should_play_defensive` returns `False` when `enemy_ships == 0`, NOT `True`. This is a safety guard against dividing by zero, not a signal that defensive mode is warranted. A fully-eliminated opponent means the game is effectively over; returning `False` here causes `plan_moves` to continue normal expansion, which is harmless. → [endgame](src/endgame.md)

---

## Strategy (`src/strategy.py`)

**Garrison ramp direction** — `min_garrison_early` is the garrison threshold at turn 0, and it is typically LOW (default 6). A low threshold means planets attack with fewer ships on hand — **more aggressive** early game. The threshold ramps UP to `min_garrison` (default 28) over `garrison_ramp_turns` turns — **more conservative** over time. "Early" does not mean "cautious". → [strategy](src/strategy.md)

**`handle_threats` min_garrison guard** — before sending any reinforcement, the candidate ship count is compared against the raw `params["min_garrison"]` value, NOT the ramped or aggression-adjusted value. This is distinct from `plan_expansion`'s garrison check. A reinforcement is skipped if `ships_to_send < min_garrison` regardless of turn number or aggression level. → [strategy](src/strategy.md)

**Lambda default-arg capture** — the opponent function in `plan_expansion` is constructed as:

```python
opponent_fn = lambda state, m=_opp_moves: m
```

NOT as:

```python
opponent_fn = lambda state: _opp_moves
```

The `m=_opp_moves` default-arg captures the value at lambda creation time. Without it, all candidates from the same source planet would share a closure over the loop variable, causing them all to use the last iteration's opponent moves. → [strategy](src/strategy.md)

**SKIP_COMBOS** — 7 `(source_class, target_class)` pairs are hard-blocked and never generate moves: `FORTRESS→HARDENED_ENEMY`, `FACTORY→HARD_NEUTRAL`, `FACTORY→CONTESTED_ENEMY`, `FACTORY→HARDENED_ENEMY`, `OUTPOST→HARD_NEUTRAL`, `OUTPOST→CONTESTED_ENEMY`, `OUTPOST→HARDENED_ENEMY`. Adding a new class combo requires two updates: (1) add it to `SKIP_COMBOS` or it will be attempted, AND (2) add the `frac_<src>_<tgt>` key to `PARAMS` — `plan_expansion` does `params.get(f"frac_{src}_{tgt}")` and silently skips the combo if the key is absent. → [strategy](src/strategy.md)

**Normalized blend** — when lookahead blending is active, greedy scores and lookahead scores are min-max normalized **independently across all candidates for the current source planet** before combining. Raw score magnitudes are NOT compared directly. A lookahead score of 0.5 and a greedy score of 100 can both normalize to any value in `[0, 1]`. Debugging blend behavior requires inspecting normalized values, not raw ones. → [strategy](src/strategy.md)
