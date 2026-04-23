from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .math_utils import angle_to_target, distance, predict_planet_position, turns_to_arrive


def my_planets(planets: list[Planet], player: int) -> list[Planet]:
    return [p for p in planets if p.owner == player]


def neutral_planets(planets: list[Planet]) -> list[Planet]:
    return [p for p in planets if p.owner == -1]


def enemy_planets(planets: list[Planet], player: int) -> list[Planet]:
    return [p for p in planets if p.owner not in (-1, player)]


def target_score(source: Planet, target: Planet, angular_velocity: float, ships_to_send: int) -> float:
    """Score a candidate target. Higher = more desirable."""
    eta = turns_to_arrive(source.x, source.y, target.x, target.y, ships_to_send)
    future_x, future_y = predict_planet_position(target, angular_velocity, eta)
    d = distance(source.x, source.y, future_x, future_y)
    # Favor high-production planets that are close. Add 1 to avoid div/zero.
    return target.production / (d + 1)


def greedy_expand(
    planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
) -> list[list]:
    """
    Phase 1 strategy: greedy expansion.

    Each owned planet with enough ships sends half its garrison toward the
    highest-scoring target (neutral first, then enemy). Uses orbit prediction
    to aim at where the target will be when the fleet arrives.
    """
    owned = my_planets(planets, player)
    targets = neutral_planets(planets) + enemy_planets(planets, player)

    if not owned or not targets:
        return []

    moves = []
    for source in owned:
        garrison_threshold = 10
        if source.ships < garrison_threshold:
            continue

        ships_to_send = source.ships // 2

        best = max(targets, key=lambda t: target_score(source, t, angular_velocity, ships_to_send))

        eta = turns_to_arrive(source.x, source.y, best.x, best.y, ships_to_send)
        future_x, future_y = predict_planet_position(best, angular_velocity, eta)
        angle = angle_to_target(source.x, source.y, future_x, future_y)

        moves.append([source.id, angle, ships_to_send])

    return moves
