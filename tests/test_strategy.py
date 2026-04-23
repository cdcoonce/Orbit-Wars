import math  # noqa: F401
import pytest  # noqa: F401
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet  # noqa: F401

from src.strategy import PARAMS, Threat, is_stationary, value_tier, classify_own  # noqa: F401
from src.strategy import can_capture, intercept


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


# --- can_capture ---

def test_can_capture_neutral_ignores_production():
    # Neutral planet: only ships count, production is ignored
    neutral = make_planet(owner=-1, ships=10, production=5)
    eta = 20
    assert can_capture(11, neutral, eta) is True
    assert can_capture(10, neutral, eta) is False  # must be strictly greater


def test_can_capture_enemy_includes_production():
    # Enemy planet: ships + production * eta
    enemy = make_planet(owner=1, ships=5, production=2)
    eta = 5  # expected = 5 + 2*5 = 15
    assert can_capture(16, enemy, eta) is True
    assert can_capture(15, enemy, eta) is False  # must exceed, not equal


# --- intercept ---

def test_intercept_returns_three_tuple():
    source = make_planet(id=0, x=50.0, y=10.0)
    target = make_planet(id=1, x=70.0, y=50.0)
    result = intercept(source, target, angular_velocity=0.03, ships_to_send=20)
    assert len(result) == 3
    future_x, future_y, eta = result
    assert isinstance(future_x, float)
    assert isinstance(future_y, float)
    assert isinstance(eta, int)
    assert eta >= 1


# --- classify_own ---

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
