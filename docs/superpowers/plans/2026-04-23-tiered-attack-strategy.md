# Tiered Attack Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `greedy_expand` with a classifier-pipeline strategy that classifies own/neutral/enemy planets, detects inbound threats, and dispatches moves via a source × target matrix with a single tunable `PARAMS` block.

**Architecture:** Two passes per turn inside `plan_moves()` — Pass 1 classifies all planets and detects threats; Pass 2 dispatches defensive reinforcements first, then offensive expansion moves gated by a (source_class × target_class) dispatch matrix. All thresholds live in one `PARAMS` dict.

**Tech Stack:** Python 3.11, kaggle-environments (Planet/Fleet namedtuples), pytest, uv

---

## File Map

| File                     | Action  | Responsibility                                                                                      |
| ------------------------ | ------- | --------------------------------------------------------------------------------------------------- |
| `src/strategy.py`        | Rewrite | `PARAMS`, `Threat`, classifiers, `detect_threats`, `handle_threats`, `plan_expansion`, `plan_moves` |
| `src/agent.py`           | Modify  | Swap `greedy_expand` import/call → `plan_moves`                                                     |
| `tests/test_strategy.py` | Create  | Unit tests for all new classifier and handler functions                                             |

**Kept unchanged:** `src/math_utils.py`, `build.py`, `intercept()`, `can_capture()`, `my_planets()`, `neutral_planets()`, `enemy_planets()`

---

## Task 1: PARAMS, Threat, `is_stationary`, `value_tier`

**Files:**

- Modify: `src/strategy.py`
- Create: `tests/test_strategy.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_strategy.py`:

```python
import math
import pytest
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from src.strategy import PARAMS, Threat, is_stationary, value_tier


def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5, ships=20, production=2):
    return Planet(id, owner, x, y, radius, ships, production)


# --- is_stationary ---

def test_is_stationary_true():
    # x=90: orbital_radius=40, 40+SUN_RADIUS(10)=50 >= ROTATION_RADIUS_LIMIT(50) → static
    assert is_stationary(make_planet(x=90.0, y=50.0)) is True


def test_is_stationary_false():
    # x=70: orbital_radius=20, 20+10=30 < 50 → orbits
    assert is_stationary(make_planet(x=70.0, y=50.0)) is False


# --- value_tier ---

def test_value_tier_high():
    assert value_tier(make_planet(x=70.0, production=PARAMS["high_value_production"])) == "HIGH"


def test_value_tier_medium():
    assert value_tier(make_planet(x=70.0, production=2)) == "MEDIUM"


def test_value_tier_low():
    assert value_tier(make_planet(x=70.0, production=1)) == "LOW"


def test_value_tier_stationary_bonus():
    # stationary + production=high_value_production-1 → bumped to HIGH
    assert value_tier(make_planet(x=90.0, production=PARAMS["high_value_production"] - 1)) == "HIGH"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -v
```

Expected: `ImportError` — `PARAMS, Threat, is_stationary, value_tier` not yet defined.

- [ ] **Step 3: Add imports, `PARAMS`, `Threat`, `is_stationary`, `value_tier` to `src/strategy.py`**

Replace the two import lines at the top of `src/strategy.py`:

```python
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .math_utils import angle_to_target, distance, predict_planet_position, turns_to_arrive
```

With:

```python
import math
from collections import namedtuple

from kaggle_environments.envs.orbit_wars.orbit_wars import (
    CENTER,
    ROTATION_RADIUS_LIMIT,
    SUN_RADIUS,
    Fleet,
    Planet,
)
from .math_utils import (
    angle_to_target,
    distance,
    fleet_speed,
    predict_planet_position,
    turns_to_arrive,
)

Threat = namedtuple("Threat", ["planet_id", "incoming_ships", "eta"])

PARAMS = {
    # Own planet classification
    "fortress_min_ships": 40,
    "fortress_min_production": 3,
    "factory_min_production": 3,
    # Target value classification
    "high_value_production": 4,
    "stationary_value_bonus": 1,
    # Threat level ratios (ships_to_send / expected_defenders)
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


def is_stationary(planet: Planet) -> bool:
    dx = planet.x - CENTER
    dy = planet.y - CENTER
    orbital_radius = math.sqrt(dx * dx + dy * dy)
    return orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT


def value_tier(planet: Planet) -> str:
    prod = planet.production
    if is_stationary(planet):
        prod += PARAMS["stationary_value_bonus"]
    if prod >= PARAMS["high_value_production"]:
        return "HIGH"
    if prod >= 2:
        return "MEDIUM"
    return "LOW"
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_strategy.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full suite to verify no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all 11 existing math_utils tests + 6 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/strategy.py tests/test_strategy.py
git commit -m "feat: add PARAMS, Threat, is_stationary, value_tier"
```

---

## Task 2: `classify_own`

**Files:**

- Modify: `src/strategy.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_strategy.py`:

```python
from src.strategy import classify_own


def test_classify_own_threatened():
    planet = make_planet(id=1, ships=50, production=5)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=10)]
    assert classify_own(planet, threats) == "THREATENED"


def test_classify_own_threatened_overrides_fortress():
    planet = make_planet(
        id=1,
        ships=PARAMS["fortress_min_ships"],
        production=PARAMS["fortress_min_production"],
    )
    threats = [Threat(planet_id=1, incoming_ships=30, eta=10)]
    assert classify_own(planet, threats) == "THREATENED"


def test_classify_own_fortress():
    planet = make_planet(
        ships=PARAMS["fortress_min_ships"],
        production=PARAMS["fortress_min_production"],
    )
    assert classify_own(planet, []) == "FORTRESS"


def test_classify_own_factory():
    planet = make_planet(ships=10, production=PARAMS["factory_min_production"])
    assert classify_own(planet, []) == "FACTORY"


def test_classify_own_outpost():
    planet = make_planet(ships=10, production=1)
    assert classify_own(planet, []) == "OUTPOST"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -k "classify_own" -v
```

Expected: `ImportError` for `classify_own`.

- [ ] **Step 3: Add `classify_own` to `src/strategy.py`**

Add after `value_tier`:

```python
def classify_own(planet: Planet, threats: list) -> str:
    if any(t.planet_id == planet.id for t in threats):
        return "THREATENED"
    if (
        planet.ships >= PARAMS["fortress_min_ships"]
        and planet.production >= PARAMS["fortress_min_production"]
    ):
        return "FORTRESS"
    if planet.production >= PARAMS["factory_min_production"]:
        return "FACTORY"
    return "OUTPOST"
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_strategy.py -k "classify_own" -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strategy.py tests/test_strategy.py
git commit -m "feat: add classify_own"
```

---

## Task 3: `classify_neutral` + `classify_enemy`

**Files:**

- Modify: `src/strategy.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_strategy.py`:

```python
from src.strategy import classify_enemy, classify_neutral


def test_classify_neutral_easy():
    target = make_planet(owner=-1, ships=10)
    ships_to_send = int(10 * PARAMS["weak_ratio"]) + 1
    assert classify_neutral(target, ships_to_send) == "EASY_NEUTRAL"


def test_classify_neutral_hard():
    target = make_planet(owner=-1, ships=100)
    assert classify_neutral(target, 10) == "HARD_NEUTRAL"


def test_classify_neutral_zero_ships():
    target = make_planet(owner=-1, ships=0)
    assert classify_neutral(target, 1) == "EASY_NEUTRAL"


def test_classify_enemy_soft():
    target = make_planet(owner=1, ships=5, production=1)
    eta = 10
    # expected_defenders = 5 + 1*10 = 15
    ships_to_send = int(15 * PARAMS["weak_ratio"]) + 1
    assert classify_enemy(target, ships_to_send, eta) == "SOFT_ENEMY"


def test_classify_enemy_contested():
    target = make_planet(owner=1, ships=5, production=1)
    eta = 10
    # expected_defenders = 15; ratio between contested_ratio and weak_ratio
    ships_to_send = int(15 * PARAMS["contested_ratio"]) + 1
    assert classify_enemy(target, ships_to_send, eta) == "CONTESTED_ENEMY"


def test_classify_enemy_hardened():
    target = make_planet(owner=1, ships=5, production=1)
    eta = 10
    # expected_defenders = 15; ratio below contested_ratio
    ships_to_send = int(15 * PARAMS["contested_ratio"]) - 1
    assert classify_enemy(target, ships_to_send, eta) == "HARDENED_ENEMY"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -k "classify_neutral or classify_enemy" -v
```

Expected: `ImportError` for `classify_neutral, classify_enemy`.

- [ ] **Step 3: Add `classify_neutral` and `classify_enemy` to `src/strategy.py`**

Add after `classify_own`:

```python
def classify_neutral(target: Planet, ships_to_send: int) -> str:
    if target.ships == 0:
        return "EASY_NEUTRAL"
    ratio = ships_to_send / target.ships
    if ratio > PARAMS["weak_ratio"]:
        return "EASY_NEUTRAL"
    return "HARD_NEUTRAL"


def classify_enemy(target: Planet, ships_to_send: int, eta: int) -> str:
    expected_defenders = target.ships + target.production * eta
    if expected_defenders == 0:
        return "SOFT_ENEMY"
    ratio = ships_to_send / expected_defenders
    if ratio > PARAMS["weak_ratio"]:
        return "SOFT_ENEMY"
    if ratio > PARAMS["contested_ratio"]:
        return "CONTESTED_ENEMY"
    return "HARDENED_ENEMY"
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_strategy.py -k "classify_neutral or classify_enemy" -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strategy.py tests/test_strategy.py
git commit -m "feat: add classify_neutral and classify_enemy"
```

---

## Task 4: `detect_threats`

**Files:**

- Modify: `src/strategy.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_strategy.py`:

```python
from src.strategy import detect_threats


def make_fleet(id=0, owner=1, x=70.0, y=50.0, angle=0.0, from_planet_id=99, ships=10):
    return Fleet(id, owner, x, y, angle, from_planet_id, ships)


def test_detect_threats_inbound():
    # Static planet at (90, 50); fleet at (70, 50) heading right → will arrive
    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    fleet = make_fleet(owner=1, x=70.0, y=50.0, angle=0.0, ships=10)
    threats = detect_threats([planet], [fleet], player=0, angular_velocity=0.03)
    assert any(t.planet_id == 1 for t in threats)


def test_detect_threats_ignores_passing():
    # Fleet heading left (angle=pi), moving away from planet at (90, 50)
    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    fleet = make_fleet(owner=1, x=70.0, y=50.0, angle=math.pi, ships=10)
    threats = detect_threats([planet], [fleet], player=0, angular_velocity=0.03)
    assert not any(t.planet_id == 1 for t in threats)


def test_detect_threats_ignores_own_fleets():
    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    own_fleet = make_fleet(owner=0, x=70.0, y=50.0, angle=0.0, ships=10)
    threats = detect_threats([planet], [own_fleet], player=0, angular_velocity=0.03)
    assert len(threats) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -k "detect_threats" -v
```

Expected: `ImportError` for `detect_threats`.

- [ ] **Step 3: Add `detect_threats` to `src/strategy.py`**

Add after `classify_enemy`:

```python
def detect_threats(
    my_planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
) -> list:
    threats = []
    seen: set[tuple[int, int]] = set()
    for fleet in fleets:
        if fleet.owner == player:
            continue
        speed = fleet_speed(fleet.ships)
        for t in range(1, PARAMS["threat_eta_window"] + 1):
            fleet_x = fleet.x + t * speed * math.cos(fleet.angle)
            fleet_y = fleet.y + t * speed * math.sin(fleet.angle)
            for planet in my_planets:
                if (fleet.id, planet.id) in seen:
                    continue
                px, py = predict_planet_position(planet, angular_velocity, t)
                if distance(fleet_x, fleet_y, px, py) < PARAMS["threat_radius"]:
                    threats.append(Threat(planet_id=planet.id, incoming_ships=fleet.ships, eta=t))
                    seen.add((fleet.id, planet.id))
    return threats
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_strategy.py -k "detect_threats" -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strategy.py tests/test_strategy.py
git commit -m "feat: add detect_threats"
```

---

## Task 5: `handle_threats`

**Files:**

- Modify: `src/strategy.py`
- Modify: `tests/test_strategy.py`

> **ETA check:** `fleet_speed(25) ≈ 2.59`. Fortress at (70,50) → threatened at (90,50): distance=20, ETA=8 ≤ 20−5=15 → sends. Far fortress at (10,50): distance=80, ETA=31 > 15 → skips.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_strategy.py`:

```python
from src.strategy import handle_threats


def test_handle_threats_reinforces_when_able():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    # Fortress at (70, 50): distance=20, arrives in ~8 turns ≤ threat.eta(20)-buffer(5)=15
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    moves = handle_threats(threats, [threatened, fortress], own_classes, angular_velocity=0.03)
    assert len(moves) == 1
    assert moves[0][0] == 2


def test_handle_threats_skips_when_too_slow():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    # Far fortress at (10, 50): distance=80, ETA ~31 > threat.eta(20)-buffer(5)=15
    far_fortress = make_planet(id=2, owner=0, x=10.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    moves = handle_threats(threats, [threatened, far_fortress], own_classes, angular_velocity=0.03)
    assert len(moves) == 0


def test_handle_threats_skips_outpost():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    outpost = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=1)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "OUTPOST"}
    moves = handle_threats(threats, [threatened, outpost], own_classes, angular_velocity=0.03)
    assert len(moves) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -k "handle_threats" -v
```

Expected: `ImportError` for `handle_threats`.

- [ ] **Step 3: Add `handle_threats` to `src/strategy.py`**

Add after `detect_threats`:

```python
def handle_threats(
    threats: list,
    owned: list[Planet],
    own_classes: dict,
    angular_velocity: float,
) -> list[list]:
    moves = []
    already_used: set[int] = set()
    for threat in threats:
        target = next((p for p in owned if p.id == threat.planet_id), None)
        if target is None:
            continue
        for source in owned:
            if source.id == threat.planet_id or source.id in already_used:
                continue
            if own_classes.get(source.id) not in ("FORTRESS", "FACTORY"):
                continue
            ships_to_send = int(source.ships * PARAMS["defense_reinforce_fraction"])
            if ships_to_send < PARAMS["min_garrison"]:
                continue
            _, _, eta = intercept(source, target, angular_velocity, ships_to_send)
            if eta <= threat.eta - PARAMS["eta_buffer"]:
                future_x, future_y, _ = intercept(source, target, angular_velocity, ships_to_send)
                angle = angle_to_target(source.x, source.y, future_x, future_y)
                moves.append([source.id, angle, ships_to_send])
                already_used.add(source.id)
                break
    return moves
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_strategy.py -k "handle_threats" -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strategy.py tests/test_strategy.py
git commit -m "feat: add handle_threats"
```

---

## Task 6: `plan_expansion`

**Files:**

- Modify: `src/strategy.py`
- Modify: `tests/test_strategy.py`

> **Test geometry:** `x=72` → orbital_radius=22, orbiting → LOW value tier. `x=90` → orbital_radius=40, static → MEDIUM/HIGH tier. Enemy at (72,50) with ships=1, production=1: probe_ships=30, probe_eta≈1, expected=2, ratio=15 → SOFT_ENEMY.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_strategy.py`:

```python
from src.strategy import plan_expansion


def test_plan_expansion_fortress_attacks_soft_enemy():
    fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "FORTRESS"}
    moves = plan_expansion([fortress], [], [soft_enemy], own_classes, angular_velocity=0.03)
    assert len(moves) == 1
    assert moves[0][0] == 0


def test_plan_expansion_outpost_skips_hard_neutral():
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    hard_neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=100, production=2)
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion([outpost], [hard_neutral], [], own_classes, angular_velocity=0.03)
    assert len(moves) == 0


def test_plan_expansion_outpost_takes_easy_low_neutral():
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    easy_low = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=5, production=1)
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion([outpost], [easy_low], [], own_classes, angular_velocity=0.03)
    assert len(moves) == 1
    assert moves[0][0] == 0


def test_plan_expansion_skips_below_min_garrison():
    planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=PARAMS["min_garrison"] - 1)
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "FORTRESS"}
    moves = plan_expansion([planet], [target], [], own_classes, angular_velocity=0.03)
    assert len(moves) == 0


def test_plan_expansion_skips_threatened():
    planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "THREATENED"}
    moves = plan_expansion([planet], [target], [], own_classes, angular_velocity=0.03)
    assert len(moves) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -k "plan_expansion" -v
```

Expected: `ImportError` for `plan_expansion`.

- [ ] **Step 3: Add `plan_expansion` to `src/strategy.py`**

Add after `handle_threats`:

```python
def plan_expansion(
    owned: list[Planet],
    neutrals: list[Planet],
    enemies: list[Planet],
    own_classes: dict,
    angular_velocity: float,
) -> list[list]:
    moves = []
    targets = neutrals + enemies

    for source in owned:
        src_class = own_classes.get(source.id, "OUTPOST")
        if src_class == "THREATENED":
            continue
        if source.ships < PARAMS["min_garrison"]:
            continue

        probe_ships = source.ships // 2
        best_score = float("-inf")
        best_target = None
        best_fraction = None

        for target in targets:
            if target.owner == -1:
                tgt_class = classify_neutral(target, probe_ships)
                if src_class == "OUTPOST" and value_tier(target) != "LOW":
                    continue
            else:
                _, _, probe_eta = intercept(source, target, angular_velocity, probe_ships)
                tgt_class = classify_enemy(target, probe_ships, probe_eta)

            fraction = PARAMS["send_fractions"].get((src_class, tgt_class))
            if fraction is None:
                continue

            ships_to_send = max(1, int(source.ships * fraction))
            _, _, eta = intercept(source, target, angular_velocity, ships_to_send)
            if not can_capture(ships_to_send, target, eta):
                continue

            bonus = PARAMS["stationary_value_bonus"] if is_stationary(target) else 0
            score = (target.production + bonus) / (eta + 1)
            if score > best_score:
                best_score = score
                best_target = target
                best_fraction = fraction

        if best_target is None:
            continue

        ships_to_send = max(1, int(source.ships * best_fraction))
        future_x, future_y, _ = intercept(source, best_target, angular_velocity, ships_to_send)
        angle = angle_to_target(source.x, source.y, future_x, future_y)
        moves.append([source.id, angle, ships_to_send])

    return moves
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_strategy.py -k "plan_expansion" -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strategy.py tests/test_strategy.py
git commit -m "feat: add plan_expansion with dispatch matrix"
```

---

## Task 7: `plan_moves` + update `agent.py` + remove old code

**Files:**

- Modify: `src/strategy.py`
- Modify: `src/agent.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_strategy.py`:

```python
from src.strategy import plan_moves


def test_plan_moves_returns_moves():
    owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
    moves = plan_moves([owned, neutral], fleets=[], player=0, angular_velocity=0.03)
    assert len(moves) >= 1
    assert moves[0][0] == 0
    assert isinstance(moves[0][1], float)
    assert isinstance(moves[0][2], int)


def test_plan_moves_no_owned_planets():
    neutral = make_planet(id=0, owner=-1, x=70.0, y=50.0, ships=10, production=2)
    moves = plan_moves([neutral], fleets=[], player=0, angular_velocity=0.03)
    assert moves == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_strategy.py -k "plan_moves" -v
```

Expected: `ImportError` for `plan_moves`.

- [ ] **Step 3: Add `plan_moves` to `src/strategy.py`**

Add after `plan_expansion`:

```python
def plan_moves(
    planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
) -> list[list]:
    owned = my_planets(planets, player)
    neutrals = neutral_planets(planets)
    enemies = enemy_planets(planets, player)

    if not owned:
        return []

    threats = detect_threats(owned, fleets, player, angular_velocity)
    own_classes = {p.id: classify_own(p, threats) for p in owned}

    defense_moves = handle_threats(threats, owned, own_classes, angular_velocity)
    defense_used = {m[0] for m in defense_moves}

    expansion_owned = [p for p in owned if p.id not in defense_used]
    expansion_classes = {k: v for k, v in own_classes.items() if k not in defense_used}
    expansion_moves = plan_expansion(expansion_owned, neutrals, enemies, expansion_classes, angular_velocity)

    return defense_moves + expansion_moves
```

- [ ] **Step 4: Delete `target_score` and `greedy_expand` from `src/strategy.py`**

Remove the `target_score` function (starts with `def target_score(`) and the `greedy_expand` function (starts with `def greedy_expand(`) — both their signatures and bodies — from `src/strategy.py`. These are replaced by inline scoring in `plan_expansion` and the new `plan_moves`.

Verify they are gone:

```bash
grep -n "def target_score\|def greedy_expand" src/strategy.py
```

Expected: no output (both functions deleted).

- [ ] **Step 5: Update `src/agent.py`**

Replace the full content of `src/agent.py` with:

```python
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .strategy import plan_moves


def agent(obs: dict) -> list[list]:
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)
    angular_velocity = obs.get("angular_velocity", 0.0)

    return plan_moves(planets, fleets, player, angular_velocity)
```

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (11 math_utils + all strategy tests), zero failures.

- [ ] **Step 7: Commit**

```bash
git add src/strategy.py src/agent.py tests/test_strategy.py
git commit -m "feat: add plan_moves, remove greedy_expand, wire agent.py"
```

---

## Task 8: Build, smoke-test, submit

**Files:**

- `submission.py` (regenerated)

- [ ] **Step 1: Rebuild submission.py**

```bash
uv run python build.py
```

Expected:

```
Written submission.py (XXXX bytes)
OK: agent() function found in submission.py
```

- [ ] **Step 2: Verify key symbols in submission.py**

```bash
grep -n "plan_moves\|PARAMS\|classify_own\|detect_threats\|handle_threats" submission.py
```

Expected: each function name appears at a `def` line in the output.

- [ ] **Step 3: Run a local game**

```bash
uv run python run_game.py
```

Expected: game runs to step 499, no exceptions thrown.

- [ ] **Step 4: Commit rebuilt artifact and submit**

```bash
git add submission.py
git commit -m "build: regenerate submission.py with tiered strategy"
```

Then submit (user provides fresh API token):

```bash
KAGGLE_API_TOKEN='<token>' uv run kaggle competitions submit \
  -c orbit-wars -f submission.py \
  -m "feat: tiered classifier strategy with threat-reactive defense"
```
