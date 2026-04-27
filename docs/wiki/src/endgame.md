## Overview

`src/endgame.py` provides two functions that implement the late-game defensive mode. When the bot has a commanding lead near the end of the game, it stops expanding and only responds to direct threats — protecting the win rather than risking ships on unnecessary attacks.

Cross-links: [Strategy](strategy.md) | [Config](config.md) | [Gotchas](../Gotchas.md) | [Home](../Home.md)

---

## Functions

### `total_ships(planets, fleets, player) -> int`

```python
def total_ships(planets: list, fleets: list, player: int) -> int:
    planet_ships = sum(p.ships for p in planets if p.owner == player)
    fleet_ships  = sum(f.ships for f in fleets  if f.owner == player)
    return planet_ships + fleet_ships
```

Counts all ships belonging to `player`: ships sitting on owned planets plus ships in in-transit fleets. Neutral planets (`owner == -1`) and enemy planets/fleets are excluded. Returns `0` on empty inputs.

---

### `should_play_defensive(planets, fleets, player, turn, threshold_turn, lead_margin) -> bool`

```python
def should_play_defensive(
    planets: list,
    fleets: list,
    player: int,
    turn: int,
    threshold_turn: int,
    lead_margin: float,
) -> bool:
```

Returns `True` when **both** conditions are satisfied simultaneously:

1. `turn >= threshold_turn` — the game is in the endgame window (default `threshold_turn=451`, meaning turns 451–499).
2. `my_ships / enemy_ships >= lead_margin` — our total ships (planets + fleets) exceed the enemy's total by at least `lead_margin` ratio (default `lead_margin=1.41265`; full value in `config.py`).

**Enemy ship count:** sum of ships on planets and in fleets where `owner not in (-1, player)`. This catches any non-neutral, non-self owner regardless of the specific player ID.

**Evaluation order / early exits:**

```
turn < threshold_turn  → False  (not in endgame yet)
enemy_ships == 0       → False  (ZeroDivisionError guard — see Gotcha below)
my/enemy < lead_margin → False  (ratio below threshold — may be losing or not winning by enough)
                       → True   (endgame + commanding lead)
```

**Effect on `plan_moves`:** when `should_play_defensive` returns `True`, `plan_moves` returns only the output of `handle_threats` — no expansion moves are generated. If there are no active threats, the bot passes the turn entirely (`[]`).

---

## Gotchas

**ZeroDivisionError guard:** when `enemy_ships == 0` (opponent has been completely eliminated), the function returns `False` rather than attempting `my_ships / 0`. This is NOT "you're winning so hard defensive mode doesn't apply" — it is purely a safety guard. In practice, a completely eliminated opponent means the game is effectively over anyway. See [Gotchas](../Gotchas.md#zerodivisionerror-guard-in-endgame).

**Both conditions are required:** a large lead before `threshold_turn` does NOT trigger defensive mode. A small lead after `threshold_turn` does NOT trigger it either. Only the intersection activates the short-circuit. This prevents the bot from going passive too early when the game is still in flux.

---

## PARAMS Defaults

| Parameter                | Default   | PARAM_SPACE range |
| ------------------------ | --------- | ----------------- |
| `endgame_threshold_turn` | `451`     | `(380, 490)`      |
| `endgame_lead_margin`    | `1.41265` | `(1.05, 2.0)`     |

Lower `endgame_threshold_turn` = longer endgame window = more conservative late game. Higher `endgame_lead_margin` = requires a larger lead before going passive = more aggressive throughout.
