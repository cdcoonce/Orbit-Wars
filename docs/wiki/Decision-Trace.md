Annotated walkthrough of a single agent turn. Shows exactly how classifiers, scoring, and blending interact to produce a move. See [Game-Loop](Game-Loop.md) for the full execution order and [Home](Home.md) for function signatures.

## Context: Turn 47

**Game state snapshot:**

| Entity              | Value                                                   |
| ------------------- | ------------------------------------------------------- |
| Turn                | 47                                                      |
| Our planet (source) | FACTORY class, 52 ships, production=5                   |
| Candidate A         | Neutral planet, production=2, orbiting (moves), 8 ships |
| Candidate B         | Enemy planet, production=4, stationary, 11 ships        |

---

## Step 1: Aggression

```python
t = min(47, 500) / 500  # = 0.094
agg = 0.917 - 0.094 * (0.917 - 0.737)  # = 0.900
```

`min_garrison / agg = 28 / 0.900 = 31.1` — source has 52 ships, clears the threshold.

---

## Step 2: Own-Planet Classification

Source planet: 52 ships, production=5.

> **Assumed params for this trace:** `fortress_min_ships=60` (Optuna-tuned value; default is 20). This reflects a realistic tuned champion that prefers fewer but better-defended FORTRESS planets.

```python
# classify_own(source, threats=[], params)
# Step 1: THREATENED?  No threats → skip
# Step 2: FORTRESS?
#   ships (52) >= fortress_min_ships (60)?  → No (52 < 60) → not FORTRESS
# Step 3: FACTORY?
#   production (5) >= factory_min_production (4)?  → Yes → FACTORY
```

`src_class = "FACTORY"`

---

## Step 3: Probe Ships

```python
probe_ships = source.ships  # = 52 (full fleet, not halved)
```

Used only for initial classification — not the actual send count.

---

## Step 4: Opponent Pre-computation (once per source)

```python
greedy_params_opp = {**params, "lookahead_blend": 0.0}
_opp_base = build_state(initial_planets, fleets, turn=47)
opp_player = 1  # third positional arg to plan_moves
_opp_moves = plan_moves(_opp_base.planets, _opp_base.fleets, opp_player,
                        angular_velocity, turn=47,
                        params=greedy_params_opp, initial_planets=initial_planets)
# Default-arg capture prevents stale closure in loop (fix from commit 79b46f9)
opponent_fn = lambda state, m=_opp_moves: m
```

Opponent response is frozen from the current board state. `blend=0` prevents recursion.

---

## Step 5: Candidate A — Neutral Planet (production=2, ETA=4)

### 5a. Classification

```python
classify_neutral(target, probe_ships=52)
# target.ships = 8
# ratio = 52 / 8 = 6.5  >  weak_ratio (1.15)
# → "EASY_NEUTRAL"
```

### 5b. SKIP_COMBOS check

`("FACTORY", "EASY_NEUTRAL")` — not in SKIP_COMBOS. Proceed.

### 5c. Ships to send

```python
fraction = params["frac_factory_easy_neutral"]  # = 0.708
ships_to_send = max(1, int(52 * 0.708 * 0.900))  # = int(33.1) = 33
```

Probe value ≈19 ships noted in the task description reflects `frac_factory_easy_neutral ≈ 0.37` from an earlier param set; the current default is 0.708 → 33 ships.

### 5d. Intercept + validity

```python
future_x, future_y, eta = intercept(source, target, angular_velocity, ships_to_send=33)
# eta = 4 turns  (orbiting target, two-iteration correction)
can_capture(33, target, eta=4)
# expected_defenders = target.ships = 8  (neutral, no production growth)
# 33 > 8  → True
path_crosses_sun(...)  # → False
```

### 5e. Greedy score

```python
eff_prod = effective_production(target, comet_ids, comet_value_multiplier)
# target not a comet → eff_prod = float(2) = 2.0
bonus = 0  # orbiting planet, not stationary
greedy_score_A = (2.0 + 0) / (4 + 1)**2  # = 2 / 25 = 0.08
```

### 5f. Lookahead score

```python
state = build_state(initial_planets, fleets, turn=47)
candidate_move = [source.id, angle_to_target(...), 33]

# T+1: apply our move + opponent response
state = step_state(state, candidate_move, player=0, angular_velocity,
                   initial_planets, opponent_fn)
# Opponent moves toward our FACTORY planet — its ships threaten our production.

# T+2: greedy rollout (lookahead_turns=2, so n_extra=1)
opp_greedy = plan_moves(state.planets, state.fleets, player=1, ..., blend=0)
fresh_opp_fn = lambda s: opp_greedy
state = step_state(state, our_move_t2, player=0, ..., fresh_opp_fn)

lookahead_score_A = score_state(state, player=0, ship_weight=0.087)
# = (my_prod - enemy_prod) + 0.087 * (my_ships - enemy_ships)
# Opponent has moved toward our FACTORY → lower net production advantage
# lookahead_score_A = 0.06
```

---

## Step 6: Candidate B — Enemy Planet (production=4, ETA=3)

### 6a. Classification

```python
_, _, probe_eta = intercept(source, target, angular_velocity, probe_ships=52)
# probe_eta = 3 turns  (stationary target)
classify_enemy(target, ships_to_send=52, eta=3)
# expected_defenders = 11 + 4*3 = 23
# ratio = 52 / 23 = 2.26  >  weak_ratio (1.15)  → "SOFT_ENEMY"
```

Using the full fleet for the probe (not half) means an adjacent FACTORY correctly
sees this planet as SOFT rather than CONTESTED — the half-fleet probe would have
computed `ratio = 26 / 23 = 1.13`, just under `weak_ratio`, misclassifying it as
`CONTESTED_ENEMY`.

### 6b. SKIP_COMBOS check

`("FACTORY", "SOFT_ENEMY")` — not in SKIP_COMBOS. Proceed.

### 6c. Ships to send

```python
fraction = params["frac_factory_soft_enemy"]  # = 0.678
ships_to_send = max(1, int(52 * 0.678 * 0.900))  # = int(31.7) = 31
```

### 6d. Intercept + validity

```python
_, _, eta = intercept(source, target, angular_velocity, 31)  # eta = 3
can_capture(31, target, eta=3)
# expected_defenders = 11 + 4*3 = 23
# 31 > 23  → True
# stationary planet — path_crosses_sun check passes
```

### 6e. Greedy score

```python
eff_prod = float(4)  # not a comet
bonus = params["stationary_value_bonus"]  # = 2  (stationary planet)
greedy_score_B = (4 + 2) / (3 + 1)**2  # = 6 / 16 = 0.375
```

### 6f. Lookahead score

After 2 simulated turns, the enemy planet has been contested but opponent hasn't had time to respond fully. Net production advantage is better than candidate A.

```python
lookahead_score_B = 0.22  # from score_state
```

---

## Step 7: Score Blending

Two candidates: A (neutral, prod=2) and B (enemy, prod=4).

```python
blend = params["lookahead_blend"]  # = 0.484
```

Normalize each score across the two candidates:

|             | Greedy | Lookahead |
| ----------- | ------ | --------- |
| Candidate A | 0.08   | 0.06      |
| Candidate B | 0.375  | 0.22      |

```python
# Greedy normalization
lo_g, hi_g = 0.08, 0.375
ng_A = (0.08  - 0.08) / (0.375 - 0.08 + 1e-9)  # = 0.0
ng_B = (0.375 - 0.08) / (0.375 - 0.08 + 1e-9)  # = 1.0

# Lookahead normalization
lo_l, hi_l = 0.06, 0.22
nl_A = (0.06 - 0.06) / (0.22 - 0.06 + 1e-9)    # = 0.0
nl_B = (0.22 - 0.06) / (0.22 - 0.06 + 1e-9)    # = 1.0

# Blended final score
final_A = (1 - 0.484) * 0.0 + 0.484 * 0.0  # = 0.0
final_B = (1 - 0.484) * 1.0 + 0.484 * 1.0  # = 1.0
```

Both candidates give `final_A = 0.0`, `final_B = 1.0` — B dominates A on both metrics, so normalization doesn't change the winner here. The blend matters when greedy and lookahead _disagree_: a high-greedy target that lookahead reveals as dangerous will have a high `ng` but low `nl`, pulling `final` down.

**Winner: Candidate B** (attack the SOFT_ENEMY planet).

---

## Step 8: Move Emission

```python
ships_to_send = max(1, int(52 * 0.678 * 0.900))  # = 31
future_x, future_y, _ = intercept(source, target, angular_velocity, 31)
angle = angle_to_target(source.x, source.y, future_x, future_y)

move = [enemy_planet_id, angle, 31]
```

The engine receives `[[enemy_planet_id, angle_rad, 31]]` as the agent's action for turn 47.

---

## Classifier Reference

### Own-Planet Classes

| Class      | Condition                                  |
| ---------- | ------------------------------------------ |
| THREATENED | Any `Threat.planet_id` matches this planet |
| FORTRESS   | `ships >= 20` AND `production >= 2`        |
| FACTORY    | `production >= 2` (and not FORTRESS)       |
| OUTPOST    | Everything else                            |

### Neutral-Planet Classes

| Class        | Condition                                                         |
| ------------ | ----------------------------------------------------------------- |
| EASY_NEUTRAL | `target.ships == 0` OR `probe / target.ships > weak_ratio` (1.15) |
| HARD_NEUTRAL | Otherwise                                                         |

### Enemy-Planet Classes

| Class           | Condition                                             |
| --------------- | ----------------------------------------------------- |
| SOFT_ENEMY      | `probe / (ships + prod*eta) > weak_ratio` (1.15)      |
| CONTESTED_ENEMY | `probe / (ships + prod*eta) > contested_ratio` (0.84) |
| HARDENED_ENEMY  | Otherwise                                             |

### SKIP_COMBOS (never attempted)

```python
{
    ("FORTRESS", "HARDENED_ENEMY"),
    ("FACTORY",  "HARD_NEUTRAL"),
    ("FACTORY",  "CONTESTED_ENEMY"),
    ("FACTORY",  "HARDENED_ENEMY"),
    ("OUTPOST",  "HARD_NEUTRAL"),
    ("OUTPOST",  "CONTESTED_ENEMY"),
    ("OUTPOST",  "HARDENED_ENEMY"),
}
```
