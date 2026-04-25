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
    path_crosses_sun,
    predict_planet_position,
    turns_to_arrive,
)
from .config import PARAMS, SKIP_COMBOS

Threat = namedtuple("Threat", ["planet_id", "incoming_ships", "eta"])


def aggression(turn: int, params: dict = PARAMS) -> float:
    t = min(turn, params["game_length"]) / params["game_length"]
    return params["aggression_max"] - t * (params["aggression_max"] - params["aggression_min"])


def is_stationary(planet: Planet) -> bool:
    dx = planet.x - CENTER
    dy = planet.y - CENTER
    orbital_radius = math.sqrt(dx * dx + dy * dy)
    return orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT


def value_tier(planet: Planet, params: dict = PARAMS) -> str:
    prod = planet.production
    if is_stationary(planet):
        prod += params["stationary_value_bonus"]
    if prod >= params["high_value_production"]:
        return "HIGH"
    if prod >= params["medium_value_production"]:
        return "MEDIUM"
    return "LOW"


def classify_own(planet: Planet, threats: list, params: dict = PARAMS) -> str:
    if any(t.planet_id == planet.id for t in threats):
        return "THREATENED"
    if (
        planet.ships >= params["fortress_min_ships"]
        and planet.production >= params["fortress_min_production"]
    ):
        return "FORTRESS"
    if planet.production >= params["factory_min_production"]:
        return "FACTORY"
    return "OUTPOST"


def classify_neutral(target: Planet, ships_to_send: int, params: dict = PARAMS) -> str:
    if target.ships == 0:
        return "EASY_NEUTRAL"
    ratio = ships_to_send / target.ships
    if ratio > params["weak_ratio"]:
        return "EASY_NEUTRAL"
    return "HARD_NEUTRAL"


def classify_enemy(target: Planet, ships_to_send: int, eta: int, params: dict = PARAMS) -> str:
    expected_defenders = target.ships + target.production * eta
    if expected_defenders == 0:
        return "SOFT_ENEMY"
    ratio = ships_to_send / expected_defenders
    if ratio > params["weak_ratio"]:
        return "SOFT_ENEMY"
    if ratio > params["contested_ratio"]:
        return "CONTESTED_ENEMY"
    return "HARDENED_ENEMY"


def detect_threats(
    my_planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
    params: dict = PARAMS,
) -> list:
    threats = []
    seen: set[tuple[int, int]] = set()
    for fleet in fleets:
        if fleet.owner == player:
            continue
        speed = fleet_speed(fleet.ships)
        for t in range(1, params["threat_eta_window"] + 1):
            fleet_x = fleet.x + t * speed * math.cos(fleet.angle)
            fleet_y = fleet.y + t * speed * math.sin(fleet.angle)
            for planet in my_planets:
                if (fleet.id, planet.id) in seen:
                    continue
                px, py = predict_planet_position(planet, angular_velocity, t)
                if distance(fleet_x, fleet_y, px, py) < params["threat_radius"]:
                    threats.append(Threat(planet_id=planet.id, incoming_ships=fleet.ships, eta=t))
                    seen.add((fleet.id, planet.id))
    return threats


def handle_threats(
    threats: list,
    owned: list[Planet],
    own_classes: dict,
    angular_velocity: float,
    params: dict = PARAMS,
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
                # classify_own returns "THREATENED" (not "FORTRESS") when a fleet is inbound,
                # so THREATENED planets are naturally excluded here
                continue
            ships_to_send = int(source.ships * params["defense_reinforce_fraction"])
            if ships_to_send < params["min_garrison"]:
                continue
            future_x, future_y, eta = intercept(source, target, angular_velocity, ships_to_send)
            if eta <= threat.eta - params["eta_buffer"]:
                if path_crosses_sun(source.x, source.y, future_x, future_y):
                    continue
                angle = angle_to_target(source.x, source.y, future_x, future_y)
                moves.append([source.id, angle, ships_to_send])
                already_used.add(source.id)
                break
    return moves


def plan_expansion(
    owned: list[Planet],
    neutrals: list[Planet],
    enemies: list[Planet],
    own_classes: dict,
    angular_velocity: float,
    agg: float = 1.0,
    params: dict = PARAMS,
) -> list[list]:
    moves = []
    targets = neutrals + enemies
    min_garrison = int(params["min_garrison"] / agg)

    for source in owned:
        src_class = own_classes.get(source.id, "OUTPOST")
        if src_class == "THREATENED":
            continue
        if source.ships < min_garrison:
            continue

        probe_ships = source.ships // 2
        best_score = float("-inf")
        best_target = None
        best_fraction = None

        for target in targets:
            if target.owner == -1:
                if src_class == "OUTPOST" and value_tier(target, params) != "LOW":
                    continue
                tgt_class = classify_neutral(target, probe_ships, params)
            else:
                _, _, probe_eta = intercept(source, target, angular_velocity, probe_ships)
                tgt_class = classify_enemy(target, probe_ships, probe_eta, params)

            if (src_class, tgt_class) in SKIP_COMBOS:
                continue
            fraction = params.get(f"frac_{src_class.lower()}_{tgt_class.lower()}")
            if fraction is None:
                continue

            ships_to_send = max(1, int(source.ships * fraction * agg))
            future_x, future_y, eta = intercept(source, target, angular_velocity, ships_to_send)
            if not can_capture(ships_to_send, target, eta):
                continue
            if path_crosses_sun(source.x, source.y, future_x, future_y):
                continue

            bonus = params["stationary_value_bonus"] if is_stationary(target) else 0
            score = (target.production + bonus) / (eta + 1) ** 2
            if score > best_score:
                best_score = score
                best_target = target
                best_fraction = fraction

        if best_target is None:
            continue

        ships_to_send = max(1, int(source.ships * best_fraction * agg))
        future_x, future_y, _ = intercept(source, best_target, angular_velocity, ships_to_send)
        angle = angle_to_target(source.x, source.y, future_x, future_y)
        moves.append([source.id, angle, ships_to_send])

    return moves


def plan_moves(
    planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
    turn: int = 0,
    params: dict = PARAMS,
) -> list[list]:
    owned = my_planets(planets, player)
    neutrals = neutral_planets(planets)
    enemies = enemy_planets(planets, player)

    if not owned:
        return []

    agg = aggression(turn, params)
    threats = detect_threats(owned, fleets, player, angular_velocity, params)
    own_classes = {p.id: classify_own(p, threats, params) for p in owned}

    defense_moves = handle_threats(threats, owned, own_classes, angular_velocity, params)
    defense_used = {m[0] for m in defense_moves}

    expansion_owned = [p for p in owned if p.id not in defense_used]
    expansion_classes = {k: v for k, v in own_classes.items() if k not in defense_used}
    expansion_moves = plan_expansion(expansion_owned, neutrals, enemies, expansion_classes, angular_velocity, agg, params)

    return defense_moves + expansion_moves


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
