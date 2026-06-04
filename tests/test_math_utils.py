import math

import pytest

from src.math_utils import (
    angle_to_target,
    distance,
    fleet_speed,
    is_stationary,
    orbital_radius,
    predict_planet_position,
    turns_to_arrive,
)
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet


def make_planet(x: float, y: float, production: int = 1, owner: int = -1) -> Planet:
    return Planet(id=0, owner=owner, x=x, y=y, radius=1.0, ships=10, production=production)


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
    # After 2π / angular_velocity turns, planet should return to start
    planet = make_planet(x=60.0, y=50.0)
    av = 0.05
    full_rev = round(2 * math.pi / av)
    x, y = predict_planet_position(planet, angular_velocity=av, turns=full_rev)
    assert x == pytest.approx(60.0, abs=0.1)
    assert y == pytest.approx(50.0, abs=0.1)


# --- angle_to_target ---

def test_angle_right():
    # Target directly to the right → angle 0
    assert angle_to_target(0, 0, 1, 0) == pytest.approx(0.0)


def test_angle_down():
    # Target directly below (y increases downward) → angle pi/2
    assert angle_to_target(0, 0, 0, 1) == pytest.approx(math.pi / 2)


def test_angle_left():
    assert angle_to_target(0, 0, -1, 0) == pytest.approx(math.pi) or \
           angle_to_target(0, 0, -1, 0) == pytest.approx(-math.pi)
