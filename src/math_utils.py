import math

from kaggle_environments.envs.orbit_wars.orbit_wars import (
    CENTER,
    ROTATION_RADIUS_LIMIT,
    SUN_RADIUS,
    Planet,
)

# Board edges, mirroring the engine's authoritative BOARD_SIZE (= 100.0). Kept
# as literals rather than importing BOARD_SIZE so build.py's flat bundle needs
# no extra kaggle symbol; test_board_bounds_match_engine_board_size pins them to
# the engine value so they can't silently drift. Used for off-board bound checks
# (e.g. comet intercept).
BOARD_MIN = 0.0
BOARD_MAX = 100.0


def orbital_radius(planet: Planet) -> float:
    """Distance from the planet to the sun at the center (50, 50)."""
    dx = planet.x - CENTER
    dy = planet.y - CENTER
    return math.sqrt(dx * dx + dy * dy)


def is_stationary(planet: Planet) -> bool:
    """True if the planet sits outside the rotation limit and never moves."""
    return orbital_radius(planet) + SUN_RADIUS >= ROTATION_RADIUS_LIMIT


def predict_planet_position(
    planet: Planet, angular_velocity: float, turns: int
) -> tuple[float, float]:
    """
    Predict where a planet will be after `turns` turns.

    Orbiting planets rotate around the sun at (50, 50) with a constant
    angular_velocity (radians/turn). Static planets (orbital_radius + SUN_RADIUS >=
    ROTATION_RADIUS_LIMIT, the same boundary as is_stationary) don't move —
    return current position unchanged. A zero angular_velocity likewise means
    no movement.

    Matches the engine formula (orbit_wars.py:586):
        angle = initial_angle + angular_velocity * step
    cos/sin periodicity handles large horizons naturally — no modulo needed.
    """
    radius = orbital_radius(planet)
    if radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT or angular_velocity == 0:
        return (planet.x, planet.y)
    current_angle = math.atan2(planet.y - CENTER, planet.x - CENTER)
    future_angle = current_angle + angular_velocity * turns
    return (
        CENTER + radius * math.cos(future_angle),
        CENTER + radius * math.sin(future_angle),
    )


def angle_to_target(
    from_x: float, from_y: float, target_x: float, target_y: float
) -> float:
    """
    Return the angle in radians from (from_x, from_y) toward (target_x, target_y).

    Kaggle's coordinate system: origin top-left, y increases downward.
    The action format uses standard math angles (0 = right, pi/2 = down).
    """
    return math.atan2(target_y - from_y, target_x - from_x)


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def fleet_speed(num_ships: int, max_speed: float = 6.0) -> float:
    """Fleet speed on the logarithmic curve from the spec, clamped to max_speed.

    Mirrors the engine (orbit_wars.py:521-529): the log curve is capped with
    min(speed, max_speed) so large fleets never drift above the engine's speed.
    """
    if num_ships <= 1:
        return 1.0
    speed = 1.0 + (max_speed - 1.0) * (math.log(num_ships) / math.log(1000)) ** 1.5
    return min(speed, max_speed)


def path_crosses_sun(x1: float, y1: float, x2: float, y2: float) -> bool:
    """True if the segment from (x1,y1) to (x2,y2) passes within SUN_RADIUS of CENTER."""
    dx = x2 - x1
    dy = y2 - y1
    fx = x1 - CENTER
    fy = y1 - CENTER
    d_len_sq = dx * dx + dy * dy
    if d_len_sq == 0:
        return math.sqrt(fx * fx + fy * fy) < SUN_RADIUS
    t = max(0.0, min(1.0, -(fx * dx + fy * dy) / d_len_sq))
    closest_x = fx + t * dx
    closest_y = fy + t * dy
    return closest_x * closest_x + closest_y * closest_y < SUN_RADIUS * SUN_RADIUS


def turns_to_arrive(
    from_x: float, from_y: float, target_x: float, target_y: float, num_ships: int
) -> int:
    """Estimate turns for a fleet to reach a target using current positions."""
    d = distance(from_x, from_y, target_x, target_y)
    speed = fleet_speed(num_ships)
    return max(1, math.ceil(d / speed))


def is_enemy(owner: int, player: int) -> bool:
    """True for any non-neutral, non-player owner (neutral == -1)."""
    return owner not in (-1, player)


def sum_owned(units, player: int, attr: str = "ships", enemy: bool = False) -> int:
    """Sum `attr` over units owned by `player`, or by any enemy when enemy=True."""
    if enemy:
        return sum(getattr(u, attr) for u in units if is_enemy(u.owner, player))
    return sum(getattr(u, attr) for u in units if u.owner == player)
