import math

from kaggle_environments.envs.orbit_wars.orbit_wars import (
    CENTER,
    ROTATION_RADIUS_LIMIT,
    SUN_RADIUS,
    Fleet,
    Planet,
)

SUN_CENTER = (CENTER, CENTER)  # (50.0, 50.0)


def predict_planet_position(
    planet: Planet, angular_velocity: float, turns: int
) -> tuple[float, float]:
    """
    Predict where a planet will be after `turns` turns.

    Orbiting planets rotate around the sun at (50, 50) with a constant
    angular_velocity (radians/turn). Static planets (orbital radius >=
    ROTATION_RADIUS_LIMIT) don't move — return current position unchanged.

    TODO: implement this function.
    Hints:
      - Compute the planet's current angle from the sun center using atan2
      - Add angular_velocity * turns to get the future angle
      - Convert back to (x, y) using the orbital radius and future angle
      - Guard against static planets using ROTATION_RADIUS_LIMIT
    """
    dx = planet.x - CENTER
    dy = planet.y - CENTER
    orbital_radius = math.sqrt(dx * dx + dy * dy)
    if orbital_radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT:
        return (planet.x, planet.y)
    period = round(2 * math.pi / angular_velocity)
    normalized_turns = turns % period
    current_angle = math.atan2(dy, dx)
    future_angle = current_angle + angular_velocity * normalized_turns
    return (
        CENTER + orbital_radius * math.cos(future_angle),
        CENTER + orbital_radius * math.sin(future_angle),
    )


def angle_to_target(
    from_x: float, from_y: float, target_x: float, target_y: float
) -> float:
    """
    Return the angle in radians from (from_x, from_y) toward (target_x, target_y).

    Kaggle's coordinate system: origin top-left, y increases downward.
    The action format uses standard math angles (0 = right, pi/2 = down).

    TODO: implement this function.
    Hint: atan2(dy, dx) — but think carefully about which direction is "down".
    """
    return math.atan2(target_y - from_y, target_x - from_x)


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def fleet_speed(num_ships: int, max_speed: float = 6.0) -> float:
    """Fleet speed on the logarithmic curve from the spec."""
    if num_ships <= 1:
        return 1.0
    return 1.0 + (max_speed - 1.0) * (math.log(num_ships) / math.log(1000)) ** 1.5


def turns_to_arrive(
    from_x: float, from_y: float, target_x: float, target_y: float, num_ships: int
) -> int:
    """Estimate turns for a fleet to reach a target using current positions."""
    d = distance(from_x, from_y, target_x, target_y)
    speed = fleet_speed(num_ships)
    return max(1, math.ceil(d / speed))
