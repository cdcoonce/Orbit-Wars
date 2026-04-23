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
    "medium_value_production": 2,
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
    if prod >= PARAMS["medium_value_production"]:
        return "MEDIUM"
    return "LOW"


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


def my_planets(planets: list[Planet], player: int) -> list[Planet]:
    return [p for p in planets if p.owner == player]


def neutral_planets(planets: list[Planet]) -> list[Planet]:
    return [p for p in planets if p.owner == -1]


def enemy_planets(planets: list[Planet], player: int) -> list[Planet]:
    return [p for p in planets if p.owner not in (-1, player)]


def intercept(
    source: Planet, target: Planet, angular_velocity: float, ships_to_send: int
) -> tuple[float, float, int]:
    """Return (future_x, future_y, eta) using one iteration to correct for
    the distance mismatch between current and predicted target position."""
    eta = turns_to_arrive(source.x, source.y, target.x, target.y, ships_to_send)
    future_x, future_y = predict_planet_position(target, angular_velocity, eta)
    eta = turns_to_arrive(source.x, source.y, future_x, future_y, ships_to_send)
    future_x, future_y = predict_planet_position(target, angular_velocity, eta)
    return future_x, future_y, eta


def can_capture(ships_to_send: int, target: Planet, eta: int) -> bool:
    """True if our fleet will outnumber the target on arrival.
    Neutral planets don't produce ships (only owned planets do per game engine),
    so only add production*eta for enemy planets."""
    if target.owner == -1:
        expected_defenders = target.ships
    else:
        expected_defenders = target.ships + target.production * eta
    return ships_to_send > expected_defenders


def target_score(
    source: Planet, target: Planet, angular_velocity: float, ships_to_send: int
) -> float:
    """Score a candidate target. Higher = more desirable. Returns -inf if uncapturable.
    Uses eta (turns to arrive) in denominator to penalise travel time directly."""
    future_x, future_y, eta = intercept(source, target, angular_velocity, ships_to_send)
    if not can_capture(ships_to_send, target, eta):
        return float("-inf")
    return target.production / (eta + 1)


def greedy_expand(
    planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
) -> list[list]:
    """
    Phase 1 strategy: greedy expansion.

    Each owned planet with enough ships sends half its garrison toward the
    highest-scoring capturable target (neutral first, then enemy). Uses orbit
    prediction with iterated ETA to aim at where the target will actually be.
    """
    owned = my_planets(planets, player)
    targets = neutral_planets(planets) + enemy_planets(planets, player)

    if not owned or not targets:
        return []

    moves = []
    for source in owned:
        if source.ships < 15:
            continue

        ships_to_send = source.ships // 2

        best_score = float("-inf")
        best = None
        for t in targets:
            s = target_score(source, t, angular_velocity, ships_to_send)
            if s > best_score:
                best_score = s
                best = t

        if best is None:
            continue

        future_x, future_y, _ = intercept(source, best, angular_velocity, ships_to_send)
        angle = angle_to_target(source.x, source.y, future_x, future_y)
        moves.append([source.id, angle, ships_to_send])

    return moves
