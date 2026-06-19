import math
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.math_utils import (
    BOARD_MAX,
    BOARD_MIN,
    angle_to_target,
    distance,
    fleet_speed,
    is_enemy,
    is_stationary,
    orbital_radius,
    path_crosses_sun,
    predict_planet_position,
    sum_owned,
    turns_to_arrive,
)
from kaggle_environments import make
from kaggle_environments.envs.orbit_wars.orbit_wars import (
    BOARD_SIZE,
    CENTER,
    ROTATION_RADIUS_LIMIT,
    SUN_RADIUS,
    Planet,
)


def test_board_bounds_match_engine_board_size():
    """BOARD_MIN/BOARD_MAX stay tied to the engine's authoritative BOARD_SIZE."""
    assert BOARD_MIN == 0.0
    assert BOARD_MAX == BOARD_SIZE


def make_planet(x: float, y: float, production: int = 1, owner: int = -1) -> Planet:
    return Planet(
        id=0, owner=owner, x=x, y=y, radius=1.0, ships=10, production=production
    )


def engine_max_speed() -> float:
    """The engine's authoritative max fleet speed (configuration.shipSpeed)."""
    config = make("orbit_wars").configuration
    try:
        return float(config["shipSpeed"])
    except (KeyError, TypeError):
        return float(config.shipSpeed)


def engine_fleet_speed(num_ships: int, max_speed: float) -> float:
    """Authoritative engine speed formula, pinned to orbit_wars.py:521-529.

    speed = 1.0 + (shipSpeed - 1.0) * (log(ships) / log(1000)) ** 1.5
    then clamped with min(speed, max_speed).
    """
    if num_ships <= 1:
        return 1.0
    speed = 1.0 + (max_speed - 1.0) * (math.log(num_ships) / math.log(1000)) ** 1.5
    return min(speed, max_speed)


# --- distance ---


def test_distance_same_point():
    assert distance(0, 0, 0, 0) == 0.0


def test_distance_known():
    assert distance(0, 0, 3, 4) == pytest.approx(5.0)


# --- fleet_speed ---


def test_fleet_speed_one_ship():
    assert fleet_speed(1) == pytest.approx(1.0)


def test_fleet_speed_increases_with_size():
    assert fleet_speed(100) > fleet_speed(10)
    assert fleet_speed(1000) > fleet_speed(100)


def test_fleet_speed_max():
    assert fleet_speed(1000) == pytest.approx(6.0)


def test_fleet_speed_never_exceeds_max():
    # The engine clamps with min(speed, max_speed); large fleets must not drift above it.
    for n in [1, 2, 1000, 1001, 2000, 10000, 1_000_000]:
        assert fleet_speed(n) <= 6.0 + 1e-9


def test_fleet_speed_matches_engine_formula():
    # Pin our helper to the engine's authoritative speed formula across a range
    # that crosses the 1000-ship clamp threshold.
    max_speed = engine_max_speed()
    for n in [2, 10, 50, 100, 500, 1000, 1001, 2000, 10000]:
        assert fleet_speed(n) == pytest.approx(engine_fleet_speed(n, max_speed))


def test_engine_max_speed_default_pinned():
    # Guards the max_speed=6.0 default our helper hardcodes against engine spec drift.
    assert engine_max_speed() == pytest.approx(6.0)


# --- engine constants (pin against spec drift) ---


def test_engine_constants_pinned():
    assert CENTER == pytest.approx(50.0)
    assert SUN_RADIUS == pytest.approx(10.0)
    assert ROTATION_RADIUS_LIMIT == pytest.approx(50.0)


# --- orbital_radius ---


def test_orbital_radius_known():
    # x=90, y=50 → 40 units from center (50, 50)
    assert orbital_radius(make_planet(x=90.0, y=50.0)) == pytest.approx(40.0)


# --- is_stationary ---


def test_is_stationary_true():
    # orbital_radius=40, 40 + SUN_RADIUS(10) = 50 >= ROTATION_RADIUS_LIMIT(50) → static
    assert is_stationary(make_planet(x=90.0, y=50.0)) is True


def test_is_stationary_false():
    # orbital_radius=20, 20 + 10 = 30 < 50 → orbits
    assert is_stationary(make_planet(x=70.0, y=50.0)) is False


# --- predict_planet_position ---


def test_static_planet_unchanged():
    # A planet far from center should not move
    planet = make_planet(x=90.0, y=50.0)
    x, y = predict_planet_position(planet, angular_velocity=0.03, turns=100)
    assert x == pytest.approx(90.0)
    assert y == pytest.approx(50.0)


def test_orbiting_planet_zero_turns():
    # Zero turns → same position regardless of velocity
    planet = make_planet(x=60.0, y=50.0)  # 10 units from center, orbiting
    x, y = predict_planet_position(planet, angular_velocity=0.03, turns=0)
    assert x == pytest.approx(60.0)
    assert y == pytest.approx(50.0)


def test_orbiting_planet_full_revolution():
    # After round(2π / angular_velocity) turns the planet returns approximately to
    # start. The engine adds av*turns directly (no modulo), so there is a small
    # drift of up to av radians due to integer rounding of the period — abs=0.2
    # accommodates that drift for av=0.05 (max position error ≈ radius*av ≈ 0.17).
    planet = make_planet(x=60.0, y=50.0)
    av = 0.05
    full_rev = round(2 * math.pi / av)
    x, y = predict_planet_position(planet, angular_velocity=av, turns=full_rev)
    assert x == pytest.approx(60.0, abs=0.2)
    assert y == pytest.approx(50.0, abs=0.2)


def test_orbiting_planet_zero_angular_velocity():
    # A non-stationary planet with zero angular velocity doesn't move —
    # return current position instead of dividing by zero.
    planet = make_planet(x=60.0, y=50.0)  # orbits, so it passes the stationary guard
    x, y = predict_planet_position(planet, angular_velocity=0.0, turns=5)
    assert x == pytest.approx(60.0)
    assert y == pytest.approx(50.0)


def test_orbiting_planet_large_angular_velocity():
    # The old code returned current position for av > 4π because round(2π/av)==0
    # triggered a division-by-zero guard on turns % period.  The engine formula
    # has no such guard — large angular_velocity just produces a large angle
    # advance and cos/sin periodicity handles it naturally.  Verify we match
    # the engine: future_angle = initial_angle + av * turns.
    planet = make_planet(x=60.0, y=50.0)  # orbits, so it passes the stationary guard
    av = 13.0
    turns = 5
    initial_angle = math.atan2(planet.y - CENTER, planet.x - CENTER)
    radius = math.sqrt((planet.x - CENTER) ** 2 + (planet.y - CENTER) ** 2)
    future_angle = initial_angle + av * turns
    expected_x = CENTER + radius * math.cos(future_angle)
    expected_y = CENTER + radius * math.sin(future_angle)
    x, y = predict_planet_position(planet, angular_velocity=av, turns=turns)
    assert x == pytest.approx(expected_x, abs=1e-9)
    assert y == pytest.approx(expected_y, abs=1e-9)


def test_predict_planet_position_long_horizon_matches_engine_formula():
    # Regression: turns > one orbital period exposed the old modulo drift.
    # Engine (orbit_wars.py:586): angle = initial_angle + angular_velocity * step
    # For av=0.05 the rounded period is 126; turns=200 > 126 puts us in the
    # second orbit, where turns%period diverges from angular_velocity*turns.
    planet = make_planet(x=60.0, y=50.0)  # radius=10, initial_angle=0
    av = 0.05
    turns = 200  # > round(2*pi/0.05) = 126
    initial_angle = math.atan2(planet.y - CENTER, planet.x - CENTER)
    radius = math.sqrt((planet.x - CENTER) ** 2 + (planet.y - CENTER) ** 2)
    future_angle = initial_angle + av * turns  # engine formula
    expected_x = CENTER + radius * math.cos(future_angle)
    expected_y = CENTER + radius * math.sin(future_angle)
    x, y = predict_planet_position(planet, angular_velocity=av, turns=turns)
    assert x == pytest.approx(expected_x, abs=1e-9)
    assert y == pytest.approx(expected_y, abs=1e-9)


def test_orbital_radius_computed_once_for_orbiting_planet():
    # Regression: the old code called orbital_radius twice for orbiting planets —
    # once inside is_stationary and again explicitly. Verify it is called at most once.
    planet = make_planet(x=60.0, y=50.0)  # orbiting, not stationary
    with patch("src.math_utils.orbital_radius", wraps=orbital_radius) as mock_r:
        predict_planet_position(planet, angular_velocity=0.05, turns=10)
    assert mock_r.call_count == 1, (
        f"orbital_radius called {mock_r.call_count} times, expected 1"
    )


def test_predict_planet_position_docstring_matches_sun_radius_guard():
    # The static-planet guard is `radius + SUN_RADIUS >= ROTATION_RADIUS_LIMIT`,
    # not `orbital_radius >= ROTATION_RADIUS_LIMIT`. The docstring must name
    # SUN_RADIUS and cross-reference is_stationary so the two stay linked.
    doc = predict_planet_position.__doc__ or ""
    assert "SUN_RADIUS" in doc, "docstring must mention SUN_RADIUS in the static guard"
    assert "is_stationary" in doc, "docstring must cross-reference is_stationary"


# --- path_crosses_sun (zero-length segment) ---


def test_path_crosses_sun_coincident_point_inside_sun():
    # When start == end, d_len_sq == 0; function checks distance from CENTER.
    # CENTER is 50.0, so (CENTER, CENTER) is distance 0 — well within SUN_RADIUS.
    assert path_crosses_sun(CENTER, CENTER, CENTER, CENTER) is True


def test_path_crosses_sun_coincident_point_outside_sun():
    # When start == end, d_len_sq == 0; function checks distance from CENTER.
    # (1.0, 1.0) is ~69 units from CENTER(50,50), well beyond SUN_RADIUS(10).
    assert path_crosses_sun(1.0, 1.0, 1.0, 1.0) is False


# --- import hygiene ---


def test_fleet_not_imported_into_math_utils():
    import src.math_utils as m

    assert not hasattr(m, "Fleet"), (
        "Fleet is unused in math_utils and should not be imported"
    )


# --- angle_to_target ---


def test_angle_right():
    # Target directly to the right → angle 0
    assert angle_to_target(0, 0, 1, 0) == pytest.approx(0.0)


def test_angle_down():
    # Target directly below (y increases downward) → angle pi/2
    assert angle_to_target(0, 0, 0, 1) == pytest.approx(math.pi / 2)


def test_angle_left():
    assert angle_to_target(0, 0, -1, 0) == pytest.approx(math.pi) or angle_to_target(
        0, 0, -1, 0
    ) == pytest.approx(-math.pi)


# --- turns_to_arrive ---


def test_turns_to_arrive_same_position_returns_one():
    # max(1, ...) floor: zero distance must not return 0 turns.
    assert turns_to_arrive(0.0, 0.0, 0.0, 0.0, 1) == 1


def test_turns_to_arrive_ceil_rounding():
    # A distance just above an exact speed multiple must round up, not truncate.
    num_ships = 10
    speed = fleet_speed(num_ships)
    exact_turns = 5
    d = speed * exact_turns + 0.001
    assert turns_to_arrive(0.0, 0.0, d, 0.0, num_ships) == exact_turns + 1


def test_turns_to_arrive_larger_fleet_no_slower_than_single_ship():
    # fleet_speed grows with fleet size, so larger fleets arrive in no more turns
    # than a 1-ship fleet covering the same distance.
    single_ship_turns = turns_to_arrive(0.0, 0.0, 30.0, 0.0, 1)
    for n in [10, 100, 1000]:
        assert turns_to_arrive(0.0, 0.0, 30.0, 0.0, n) <= single_ship_turns


# --- is_enemy ---


def _unit(owner: int, ships: int = 0, production: int = 0) -> SimpleNamespace:
    return SimpleNamespace(owner=owner, ships=ships, production=production)


def test_is_enemy_other_player():
    assert is_enemy(2, 0) is True


def test_is_enemy_player_not_enemy():
    assert is_enemy(0, 0) is False


def test_is_enemy_neutral_not_enemy():
    assert is_enemy(-1, 0) is False


# --- sum_owned ---


def test_sum_owned_player_ships():
    units = [_unit(0, ships=5), _unit(1, ships=3), _unit(-1, ships=10)]
    assert sum_owned(units, player=0) == 5


def test_sum_owned_enemy_ships_excludes_neutral_and_player():
    # player=0, neutral=-1 must both be excluded; only owner=1 and owner=2 count
    units = [_unit(0, ships=5), _unit(1, ships=3), _unit(2, ships=7), _unit(-1, ships=10)]
    assert sum_owned(units, player=0, enemy=True) == 10


def test_sum_owned_neutral_only_is_zero():
    units = [_unit(-1, ships=5), _unit(-1, ships=3)]
    assert sum_owned(units, player=0, enemy=True) == 0


def test_sum_owned_empty_collection_is_zero():
    assert sum_owned([], player=0) == 0
    assert sum_owned([], player=0, enemy=True) == 0


def test_sum_owned_production_attribute():
    units = [_unit(0, production=4), _unit(1, production=2), _unit(-1, production=9)]
    assert sum_owned(units, player=0, attr="production") == 4
    assert sum_owned(units, player=0, attr="production", enemy=True) == 2
