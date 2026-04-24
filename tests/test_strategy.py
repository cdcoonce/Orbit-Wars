import math  # noqa: F401
import pytest  # noqa: F401
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet  # noqa: F401

from src.strategy import PARAMS, Threat, is_stationary, value_tier  # noqa: F401
from src.strategy import can_capture, intercept
from src.strategy import classify_own
from src.strategy import classify_enemy, classify_neutral
from src.strategy import detect_threats
from src.strategy import handle_threats
from src.strategy import plan_expansion


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
    # expected_defenders = 15; use midpoint between contested and weak ratios
    midpoint = (PARAMS["contested_ratio"] + PARAMS["weak_ratio"]) / 2
    ships_to_send = int(15 * midpoint) + 1
    assert PARAMS["contested_ratio"] < ships_to_send / 15 < PARAMS["weak_ratio"]
    assert classify_enemy(target, ships_to_send, eta) == "CONTESTED_ENEMY"


def test_classify_enemy_zero_defenders():
    target = make_planet(owner=1, ships=0, production=0)
    assert classify_enemy(target, ships_to_send=1, eta=10) == "SOFT_ENEMY"


def test_classify_enemy_hardened():
    target = make_planet(owner=1, ships=5, production=1)
    eta = 10
    # expected_defenders = 15; ratio below contested_ratio
    ships_to_send = int(15 * PARAMS["contested_ratio"]) - 1
    assert classify_enemy(target, ships_to_send, eta) == "HARDENED_ENEMY"



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


# --- handle_threats ---

def test_handle_threats_reinforces_when_able():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    # Fortress at (70, 50): distance=20, arrives in ~8 turns <= threat.eta(20)-buffer(5)=15
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


def test_handle_threats_already_used_not_reused():
    # Two threats, only one eligible fortress — should only produce one move
    threatened1 = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    threatened2 = make_planet(id=3, owner=0, x=88.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [
        Threat(planet_id=1, incoming_ships=30, eta=20),
        Threat(planet_id=3, incoming_ships=30, eta=20),
    ]
    own_classes = {1: "THREATENED", 2: "FORTRESS", 3: "THREATENED"}
    moves = handle_threats(
        threats, [threatened1, fortress, threatened2], own_classes, angular_velocity=0.03
    )
    # Fortress assigned to first threat, then blocked for second → only 1 move
    assert len(moves) == 1
    assert moves[0][0] == 2


# --- plan_expansion ---

def test_plan_expansion_fortress_attacks_soft_enemy():
    fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "FORTRESS"}
    moves = plan_expansion([fortress], [], [soft_enemy], own_classes, angular_velocity=0.03)
    assert len(moves) == 1
    assert moves[0][0] == 0
    expected_ships = max(1, int(60 * PARAMS["send_fractions"][("FORTRESS", "SOFT_ENEMY")]))
    assert moves[0][2] == expected_ships


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


def test_plan_expansion_outpost_skips_easy_neutral_high_value():
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    # ships=0 → EASY_NEUTRAL via dispatch matrix; production=4 → HIGH value → OUTPOST gate blocks
    high_value_neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=4)
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion([outpost], [high_value_neutral], [], own_classes, angular_velocity=0.03)
    assert len(moves) == 0


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
