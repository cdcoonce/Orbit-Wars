import math  # noqa: F401
import pytest  # noqa: F401
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet  # noqa: F401

from src.strategy import PARAMS, Threat, is_stationary  # noqa: F401
from src.strategy import aggression
from src.strategy import _intercept_comet_linear
from src.strategy import _effective_distance_power
from src.strategy import can_capture, intercept
from src.math_utils import path_crosses_sun
from src.math_utils import angle_to_target
from src.math_utils import predict_planet_position, turns_to_arrive
from src.strategy import classify_own
from src.strategy import classify_enemy, classify_neutral
from src.strategy import detect_threats
from src.strategy import handle_threats
from src.strategy import plan_expansion
from src.strategy import plan_moves


def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5, ships=20, production=2):
    return Planet(id, owner, x, y, radius, ships, production)


# --- is_stationary ---


def test_is_stationary_true():
    # x=90: orbital_radius=40, 40+SUN_RADIUS(10)=50 >= ROTATION_RADIUS_LIMIT(50) → static
    assert is_stationary(make_planet(x=90.0, y=50.0)) is True


def test_is_stationary_false():
    # x=70: orbital_radius=20, 20+10=30 < 50 → orbits
    assert is_stationary(make_planet(x=70.0, y=50.0)) is False


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


def test_intercept_converges_to_orbiting_target_future_position():
    """The convergence loop aims at the target's *future* orbit position, not its
    current one, and returns a self-consistent (position, eta) fixed point."""
    av = 0.02
    source = make_planet(id=0, x=20.0, y=50.0)
    # x=70: orbital_radius=20, 20+SUN_RADIUS(10)=30 < ROTATION_RADIUS_LIMIT(50) → orbits
    target = make_planet(id=1, x=70.0, y=50.0)
    ships = 20

    future_x, future_y, eta = intercept(source, target, av, ships)

    # Returned point equals the orbit prediction for the returned eta.
    expected_x, expected_y = predict_planet_position(target, av, eta)
    assert abs(future_x - expected_x) < 1e-9
    assert abs(future_y - expected_y) < 1e-9

    # The fast-orbiting target actually moved, so aiming at the current position
    # would have been wrong — this proves the loop did real work.
    assert abs(future_x - target.x) > 1e-6 or abs(future_y - target.y) > 1e-6

    # ETA is self-consistent with the aim point it produced.
    assert turns_to_arrive(source.x, source.y, future_x, future_y, ships) == eta


def test_intercept_stationary_target_returns_current_position():
    """Contrast case: a target outside ROTATION_RADIUS_LIMIT never moves, so the
    loop returns its unchanged current position."""
    av = 0.03
    source = make_planet(id=0, x=10.0, y=50.0)
    # x=90: orbital_radius=40, 40+SUN_RADIUS(10)=50 >= ROTATION_RADIUS_LIMIT(50) → static
    target = make_planet(id=1, x=90.0, y=50.0)

    future_x, future_y, _eta = intercept(source, target, av, 30)

    assert future_x == target.x
    assert future_y == target.y


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
    # Use explicit ratios with a clear gap so integer arithmetic stays in range
    params = {**PARAMS, "contested_ratio": 1.1, "weak_ratio": 2.0}
    ships_to_send = int(15 * 1.5)  # 22/15=1.47, between 1.1 and 2.0
    assert (
        classify_enemy(target, ships_to_send, eta, params=params) == "CONTESTED_ENEMY"
    )


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


def test_detect_threats_aggregates_converging_fleets():
    # Two enemy fleets converging on the same static planet within the ETA window
    # collapse into a SINGLE threat: incoming_ships sums, eta is the earliest sighting.
    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    fleet_a = make_fleet(id=0, owner=1, x=62.0, y=50.0, angle=0.0, ships=10)
    fleet_b = make_fleet(id=1, owner=1, x=64.0, y=50.0, angle=0.0, ships=15)

    # Derive each fleet's solo sighting eta from the function itself (self-consistent).
    eta_a = detect_threats([planet], [fleet_a], player=0, angular_velocity=0.03)[0].eta
    eta_b = detect_threats([planet], [fleet_b], player=0, angular_velocity=0.03)[0].eta

    threats = detect_threats(
        [planet], [fleet_a, fleet_b], player=0, angular_velocity=0.03
    )
    assert len(threats) == 1
    assert threats[0].planet_id == 1
    assert threats[0].incoming_ships == fleet_a.ships + fleet_b.ships  # 25, summed
    assert threats[0].eta == min(eta_a, eta_b)  # earliest sighting preserved


def test_detect_threats_aggregates_fleets_with_colliding_ids():
    # Two distinct fleet objects sharing id=-1 (sim-spawned sentinel) must BOTH
    # contribute their ships — the dedup key must be object-identity-based, not
    # .id-based, or the second fleet is silently dropped (regression for lookahead path).
    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    fleet_a = make_fleet(id=-1, owner=1, x=62.0, y=50.0, angle=0.0, ships=10)
    fleet_b = make_fleet(id=-1, owner=1, x=64.0, y=50.0, angle=0.0, ships=15)

    threats = detect_threats(
        [planet], [fleet_a, fleet_b], player=0, angular_velocity=0.03
    )
    assert len(threats) == 1
    assert threats[0].planet_id == 1
    assert threats[0].incoming_ships == fleet_a.ships + fleet_b.ships  # 25, not 10


def test_detect_threats_single_fleet_unchanged():
    # Regression: a single inbound fleet produces exactly one threat with the fleet's
    # ships and first-sighting eta — byte-for-byte identical to pre-aggregation behavior.
    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    fleet = make_fleet(owner=1, x=70.0, y=50.0, angle=0.0, ships=10)
    threats = detect_threats([planet], [fleet], player=0, angular_velocity=0.03)
    assert len(threats) == 1
    assert threats[0].planet_id == 1
    assert threats[0].incoming_ships == fleet.ships
    assert threats[0].eta == 7


def test_handle_threats_scales_against_combined_incoming():
    # Downstream: feeding two converging fleets through detect_threats yields a single
    # threat whose summed incoming_ships drives magnitude-aware reinforcement — handle_threats
    # reinforces once against the COMBINED strength, not just one fleet's ships.
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=95.0, y=50.0, ships=100, production=4)
    fleet_a = make_fleet(id=0, owner=1, x=62.0, y=50.0, angle=0.0, ships=10)
    fleet_b = make_fleet(id=1, owner=1, x=64.0, y=50.0, angle=0.0, ships=15)

    threats = detect_threats(
        [threatened], [fleet_a, fleet_b], player=0, angular_velocity=0.03
    )
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.1,
        "eta_buffer": 5,
        "defense_incoming_multiplier": 0.5,
    }
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    flat = int(100 * 0.1)  # 10 — flat fraction of the fortress garrison
    combined = int(25 * 0.5)  # 12 — magnitude scaled by SUMMED incoming (10+15)
    single = int(15 * 0.5)  # 7  — what one fleet alone would have driven
    assert len(moves) == 1
    assert moves[0][0] == 2
    assert moves[0][2] == combined
    assert moves[0][2] > flat
    assert moves[0][2] > single


# --- handle_threats ---


def test_handle_threats_reinforces_when_able():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    # Fortress at (70, 50): distance=20, arrives in ~8 turns <= threat.eta(20)-buffer(5)=15
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.5,
        "eta_buffer": 5,
    }
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert len(moves) == 1
    assert moves[0][0] == 2


def test_handle_threats_skips_when_too_slow():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    # Far fortress at (10, 50): distance=80, ETA ~31 > threat.eta(20)-buffer(5)=15
    far_fortress = make_planet(id=2, owner=0, x=10.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    moves = handle_threats(
        threats, [threatened, far_fortress], own_classes, angular_velocity=0.03
    )
    assert len(moves) == 0


def test_handle_threats_skips_outpost():
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    outpost = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=1)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "OUTPOST"}
    moves = handle_threats(
        threats, [threatened, outpost], own_classes, angular_velocity=0.03
    )
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
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.5,
        "eta_buffer": 5,
    }
    moves = handle_threats(
        threats,
        [threatened1, fortress, threatened2],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    # Fortress assigned to first threat, then blocked for second → only 1 move
    assert len(moves) == 1
    assert moves[0][0] == 2


def test_handle_threats_identical_at_zero_multiplier():
    # At defense_incoming_multiplier == 0.0 the magnitude term is zero, so
    # reinforcement is exactly the flat fraction of the source's ships — byte-for-byte
    # identical to the pre-feature behavior no matter how large the incoming attack is.
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=200, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.5,
        "eta_buffer": 5,
        "defense_incoming_multiplier": 0.0,
    }
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert len(moves) == 1
    assert moves[0][2] == int(50 * 0.5)  # flat fraction only — incoming_ships ignored


def test_handle_threats_scales_reinforcement_with_incoming_when_enabled():
    # With the knob > 0, a large incoming attack pulls more reinforcement than the
    # flat fraction alone would send (magnitude = incoming * multiplier wins the max()).
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=100, production=4)
    threats = [Threat(planet_id=1, incoming_ships=100, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.1,
        "eta_buffer": 5,
        "defense_incoming_multiplier": 0.5,
    }
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    flat = int(100 * 0.1)  # 10
    magnitude = int(100 * 0.5)  # 50 — the attack-scaled term
    assert len(moves) == 1
    assert moves[0][2] == magnitude
    assert moves[0][2] > flat


def test_handle_threats_larger_incoming_reinforces_at_least_as_much():
    # Holding the source garrison constant and the knob > 0, a bigger attack must
    # never pull *less* reinforcement than a smaller one (monotonic in incoming_ships).
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=100, production=4)
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.1,
        "eta_buffer": 5,
        "defense_incoming_multiplier": 0.5,
    }
    small = handle_threats(
        [Threat(planet_id=1, incoming_ships=30, eta=20)],
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    large = handle_threats(
        [Threat(planet_id=1, incoming_ships=100, eta=20)],
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert small and large
    assert large[0][2] >= small[0][2]


def test_handle_threats_flat_baseline_can_leave_source_below_min_garrison():
    """Flat baseline overrides the garrison guard when flat > source.ships - min_garrison.

    Concrete reproduction (from issue #125):
      source.ships=50, defense_reinforce_fraction=0.6  → flat=30
      min_garrison=26                                  → source.ships - min_garrison=24
      max(30, min(30, 24)) = 30                        (flat wins)
      30 >= 26 (send-size check passes)  →  move fires, source left with 20 < 26

    This is *current documented behavior*: the outer max(flat, ...) deliberately
    preserves the legacy flat-fraction floor, so the garrison dip is intentional.
    If leaving the source below min_garrison should be prevented, this test is the
    red test for that fix — change the assertion on `remaining < min_garrison` to
    `remaining >= min_garrison`.
    """
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 26,
        "defense_reinforce_fraction": 0.6,
        "eta_buffer": 5,
    }
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    flat = int(50 * 0.6)  # 30 — legacy flat baseline
    garrison_headroom = (
        50 - params["min_garrison"]
    )  # 24 — ships available above min_garrison
    # Precondition: flat exceeds garrison headroom, so the outer max overrides the inner cap.
    assert flat > garrison_headroom, (
        "precondition: flat must exceed ships - min_garrison"
    )
    # The move fires: send-size (30) >= min_garrison (26), so the guard at line 155 passes.
    assert len(moves) == 1
    assert moves[0][0] == 2
    assert moves[0][2] == flat  # sends full flat baseline, not the garrison-capped 24
    # Source is left with 20 ships — below min_garrison (26).
    remaining = fortress.ships - moves[0][2]
    assert remaining < params["min_garrison"]


# --- plan_expansion ---


def test_plan_expansion_fortress_attacks_soft_enemy():
    fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "FORTRESS"}
    moves = plan_expansion(
        [fortress], [], [soft_enemy], own_classes, angular_velocity=0.03
    )
    assert len(moves) == 1
    assert moves[0][0] == 0
    expected_ships = max(1, int(60 * PARAMS["frac_fortress_soft_enemy"]))
    assert moves[0][2] == expected_ships


def test_plan_expansion_outpost_skips_hard_neutral():
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    hard_neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=100, production=2)
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion(
        [outpost], [hard_neutral], [], own_classes, angular_velocity=0.03
    )
    assert len(moves) == 0


def test_plan_expansion_outpost_takes_easy_low_neutral():
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    easy_low = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=5, production=1)
    own_classes = {0: "OUTPOST"}
    params = {**PARAMS, "min_garrison": 10, "weak_ratio": 1.5}
    moves = plan_expansion(
        [outpost], [easy_low], [], own_classes, angular_velocity=0.03, params=params
    )
    assert len(moves) == 1
    assert moves[0][0] == 0


def test_plan_expansion_skips_below_min_garrison():
    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
    }
    planet = make_planet(
        id=0, owner=0, x=70.0, y=50.0, ships=params["min_garrison"] - 1
    )
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "FORTRESS"}
    moves = plan_expansion(
        [planet],
        [target],
        [],
        own_classes,
        angular_velocity=0.03,
        params=params,
        turn=100,
    )
    assert len(moves) == 0


# --- plan_expansion multi-target ship draining ---


def test_plan_expansion_drains_excess_to_second_target():
    """One source with surplus ships funds the top target, then drains the
    remainder into a second, lower-scored target (two moves, one source)."""
    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=100, production=4)
    high = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=5)
    low = make_planet(id=2, owner=-1, x=68.0, y=50.0, ships=0, production=2)
    own_classes = {0: "FORTRESS"}
    # Low garrison + plenty of ships so a single source can fund two captures.
    params = {
        **PARAMS,
        "min_garrison": 10,
        "min_garrison_early": 10,
        "garrison_ramp_turns": 1,
    }
    moves = plan_expansion(
        [source],
        [high, low],
        [],
        own_classes,
        angular_velocity=0.03,
        params=params,
        turn=100,
    )

    assert len(moves) == 2
    assert all(m[0] == source.id for m in moves)
    # Two distinct targets -> two distinct headings from the same source.
    assert moves[0][1] != moves[1][1]
    # Higher-scored target is funded first, from the full fleet -> the larger send.
    assert moves[0][2] > moves[1][2]
    first_send = max(1, int(source.ships * PARAMS["frac_fortress_easy_neutral"]))
    fx, fy, _ = intercept(source, high, 0.03, first_send)
    assert moves[0][1] == pytest.approx(angle_to_target(source.x, source.y, fx, fy))
    # min_garrison floor respected after draining both fleets.
    assert source.ships - sum(m[2] for m in moves) >= params["min_garrison"]


def test_plan_expansion_drain_clamps_at_min_garrison():
    """When the remaining fleet sits just above min_garrison, the drain send is
    clamped to (ships_remaining - min_garrison) so the source is not over-drained."""
    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=35, production=4)
    high = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=5)
    low = make_planet(id=2, owner=-1, x=68.0, y=50.0, ships=0, production=2)
    own_classes = {0: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "min_garrison_early": 10,
        "garrison_ramp_turns": 1,
    }
    moves = plan_expansion(
        [source],
        [high, low],
        [],
        own_classes,
        angular_velocity=0.03,
        params=params,
        turn=100,
    )

    assert len(moves) == 2
    # Primary takes int(35 * frac) ships, leaving 13 (just above the floor of 10).
    first_send = max(1, int(source.ships * PARAMS["frac_fortress_easy_neutral"]))
    ships_remaining = source.ships - first_send
    # Unclamped, the drain would send int(ships_remaining * frac); the clamp caps it
    # at (ships_remaining - min_garrison) so the source keeps exactly min_garrison.
    unclamped = max(1, int(ships_remaining * PARAMS["frac_fortress_easy_neutral"]))
    assert (
        unclamped > ships_remaining - params["min_garrison"]
    )  # floor branch is exercised
    assert moves[1][2] == ships_remaining - params["min_garrison"]
    assert source.ships - sum(m[2] for m in moves) == params["min_garrison"]


# --- garrison ramp ---


def test_garrison_ramp_at_turn_zero_uses_early_value():
    from src.strategy import _effective_min_garrison

    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
    }
    assert _effective_min_garrison(0, params) == 5


def test_garrison_ramp_at_full_turn_uses_full_value():
    from src.strategy import _effective_min_garrison

    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
    }
    assert _effective_min_garrison(50, params) == 30


def test_garrison_ramp_midpoint():
    from src.strategy import _effective_min_garrison

    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
    }
    assert _effective_min_garrison(25, params) == 17  # int(5 + 0.5 * 25) = 17


def test_garrison_ramp_beyond_ramp_turns_clamps_to_full():
    from src.strategy import _effective_min_garrison

    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
    }
    assert _effective_min_garrison(200, params) == 30


def test_early_game_attacks_with_low_ships():
    """At turn 0, a planet below min_garrison but above min_garrison_early can attack."""
    planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=8, production=2)
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=1)
    own_classes = {0: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
        "weak_ratio": 1.5,
    }
    moves = plan_expansion(
        [planet],
        [target],
        [],
        own_classes,
        angular_velocity=0.03,
        params=params,
        turn=0,
    )
    assert len(moves) == 1


def test_late_game_holds_below_full_garrison():
    """At turn 100 (past ramp), same planet with 8 ships is below full min_garrison and skips."""
    planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=8, production=2)
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=1)
    own_classes = {0: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 30,
        "min_garrison_early": 5,
        "garrison_ramp_turns": 50,
        "weak_ratio": 1.5,
    }
    moves = plan_expansion(
        [planet],
        [target],
        [],
        own_classes,
        angular_velocity=0.03,
        params=params,
        turn=100,
    )
    assert len(moves) == 0


def test_plan_expansion_skips_threatened():
    planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "THREATENED"}
    moves = plan_expansion([planet], [target], [], own_classes, angular_velocity=0.03)
    assert len(moves) == 0


def test_plan_expansion_outpost_attacks_easy_neutral_any_value():
    # OUTPOSTs no longer have a value-tier gate — can_capture + distance_power handle selectivity.
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    high_value_neutral = make_planet(
        id=1, owner=-1, x=72.0, y=50.0, ships=0, production=4
    )
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion(
        [outpost], [high_value_neutral], [], own_classes, angular_velocity=0.03
    )
    assert len(moves) == 1


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


def test_plan_moves_defending_source_does_not_also_expand():
    """A planet that reinforces a threatened ally must NOT also launch an expansion
    fleet in the same turn — doing so would double-spend its garrison.

    plan_moves filters defense sources out of the expansion pass (strategy.py
    `defense_used`). This builds a board where the fortress is the only viable
    reinforcer AND the only planet with an attractive neutral in range, so the
    exclusion is genuinely exercised: without it the fortress would appear twice.

    Geometry note: the enemy must be far + slow so detect_threats reports a LARGE
    threat.eta, while the fortress sits CLOSE to the threatened planet (small
    intercept eta) — otherwise handle_threats' `eta <= threat.eta - eta_buffer`
    gate rejects the reinforcement and the exclusion is never reached. The enemy's
    flight path (the x=90 line) stays 15 units clear of the fortress, so the
    fortress is not itself flagged THREATENED.
    """
    # Threatened ally, static at (90, 50).
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    # Slow 5-ship enemy descending the x=90 line from (90, 25): reaches the
    # threatened planet's threat_radius at ~turn 12 (threat.eta ≈ 12).
    enemy_fleet = make_fleet(owner=1, x=90.0, y=25.0, angle=math.pi / 2, ships=5)
    # Fortress 15 units from the threatened planet → reinforces in ~6 turns,
    # comfortably under threat.eta(12) - eta_buffer(5) = 7.
    fortress = make_planet(id=2, owner=0, x=75.0, y=50.0, ships=50, production=4)
    # Attractive easy neutral next to the fortress — the expansion target it would
    # otherwise launch toward (this is what the exclusion must suppress).
    neutral = make_planet(id=3, owner=-1, x=77.0, y=50.0, ships=0, production=1)

    planets = [threatened, fortress, neutral]
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.5,
        "eta_buffer": 5,
    }
    moves = plan_moves(
        planets, [enemy_fleet], player=0, angular_velocity=0.03, params=params
    )

    # The exclusion is actually exercised: the fortress did issue a defensive move.
    assert any(m[0] == fortress.id for m in moves), (
        "expected the fortress to issue a defensive reinforcement"
    )
    # ...and therefore must not appear a second time as an expansion source.
    fortress_move_count = sum(1 for m in moves if m[0] == fortress.id)
    assert fortress_move_count == 1, (
        f"fortress double-spent its garrison: appeared in {fortress_move_count} moves"
    )


# --- plan_expansion structural ---


def test_plan_expansion_lookahead_guard_not_duplicated():
    """plan_expansion must hoist the lookahead-enablement condition into a single
    flag rather than repeating the guard verbatim at two call sites.  Duplication
    means the two sites can silently drift out of sync."""
    import inspect
    from src.strategy import plan_expansion

    src = inspect.getsource(plan_expansion)
    guard = "blend > 0 and initial_planets is not None and fleets is not None"
    count = src.count(guard)
    assert count <= 1, (
        f"The guard '{guard}' appears {count} times in plan_expansion — "
        "hoist it into a single `use_lookahead` flag instead."
    )


# --- path_crosses_sun ---


def test_path_crosses_sun_direct_hit():
    # Segment passes straight through CENTER (50, 50)
    assert path_crosses_sun(10.0, 50.0, 90.0, 50.0) is True


def test_path_crosses_sun_clear_path():
    # Segment far from the sun (both points at y=90, well outside SUN_RADIUS)
    assert path_crosses_sun(10.0, 90.0, 90.0, 90.0) is False


def test_path_crosses_sun_endpoint_inside():
    # One endpoint is inside the sun
    assert path_crosses_sun(50.0, 50.0, 90.0, 50.0) is True


def test_path_crosses_sun_grazes_edge():
    from kaggle_environments.envs.orbit_wars.orbit_wars import SUN_RADIUS

    # Segment passes exactly at SUN_RADIUS distance — should NOT cross (< not <=)
    assert path_crosses_sun(50.0 - SUN_RADIUS, 0.0, 50.0 - SUN_RADIUS, 100.0) is False


# --- _turn_ramp ---


def test_turn_ramp_at_start_returns_start():
    from src.strategy import _turn_ramp

    assert _turn_ramp(0, 100, 4.0, 2.0) == 4.0


def test_turn_ramp_at_ramp_turns_returns_end():
    from src.strategy import _turn_ramp

    assert _turn_ramp(100, 100, 4.0, 2.0) == 2.0


def test_turn_ramp_clamps_beyond_ramp_turns():
    from src.strategy import _turn_ramp

    assert _turn_ramp(200, 100, 4.0, 2.0) == 2.0


def test_turn_ramp_midpoint_is_linear():
    from src.strategy import _turn_ramp

    assert _turn_ramp(50, 100, 4.0, 2.0) == 3.0


# --- _effective_distance_power ---


def test_effective_distance_power_ramp():
    params = {
        "distance_power_early": 4.0,
        "distance_power_late": 2.0,
        "distance_ramp_turns": 100,
    }
    assert _effective_distance_power(0, params) == 4.0
    assert _effective_distance_power(100, params) == 2.0
    assert _effective_distance_power(200, params) == 2.0  # clamped post-ramp
    mid = _effective_distance_power(50, params)
    assert 2.0 < mid < 4.0


def test_distance_power_penalizes_farther_planets():
    prod = 3
    eta_near, eta_far = 2, 8
    # With steep early-game exponent, far planet is much worse relative to near
    early_ratio = (prod / (eta_near + 1) ** 4.0) / (prod / (eta_far + 1) ** 4.0)
    late_ratio = (prod / (eta_near + 1) ** 2.0) / (prod / (eta_far + 1) ** 2.0)
    # Steeper power → larger ratio (near planet scores proportionally more)
    assert early_ratio > late_ratio


# --- comet intercept ---


def make_planet_at(id=0, x=50.0, y=50.0, owner=-1, ships=0, production=1, radius=3):
    return Planet(id, owner, x, y, radius, ships, production)


class TestInterceptComet:
    def test_comet_intercept_uses_linear_velocity(self):
        """With velocity data, comet intercept predicts linearly, not circularly."""
        source = make_planet_at(id=0, x=10.0, y=50.0, owner=0, ships=40)
        comet = make_planet_at(id=5, x=60.0, y=50.0)
        # Comet moving downward — stays on board throughout intercept window
        vel = (0.0, -1.0)
        result = intercept(
            source,
            comet,
            angular_velocity=0.03,
            ships_to_send=40,
            comet_ids={5},
            comet_velocities={5: vel},
        )
        assert result != (None, None, None)
        fx, fy, eta = result
        assert 0.0 <= fx <= 100.0
        assert 0.0 <= fy <= 100.0
        assert eta >= 1

    def test_comet_no_velocity_returns_none(self):
        """Without velocity data (first sighting), intercept returns sentinel None."""
        source = make_planet_at(id=0, x=10.0, y=50.0, owner=0, ships=20)
        comet = make_planet_at(id=5, x=60.0, y=50.0)
        result = intercept(
            source,
            comet,
            angular_velocity=0.03,
            ships_to_send=20,
            comet_ids={5},
            comet_velocities={},
        )
        assert result == (None, None, None)

    def test_comet_offboard_prediction_returns_none(self):
        """If linear extrapolation exits the board, return None (don't fire)."""
        source = make_planet_at(id=0, x=50.0, y=50.0, owner=0, ships=1)
        # Comet at (98, 50) moving right — exits board immediately
        comet = make_planet_at(id=5, x=98.0, y=50.0)
        vel = (4.0, 0.0)
        result = intercept(
            source,
            comet,
            angular_velocity=0.03,
            ships_to_send=1,
            comet_ids={5},
            comet_velocities={5: vel},
        )
        assert result == (None, None, None)

    def test_linear_intercept_iterative_helper(self):
        """_intercept_comet_linear converges for a straightforward pursuit."""
        # Source at (0, 50), stationary comet at (50, 50) — fleet can always catch it
        result = _intercept_comet_linear(0.0, 50.0, 50.0, 50.0, 0.0, 0.0, 10)
        assert result is not None
        fx, fy, eta = result
        assert eta >= 1
        assert 0.0 <= fx <= 100.0

    def test_linear_intercept_aim_point_offboard_returns_none(self):
        """Helper rejects a comet whose predicted aim point leaves the board."""
        # Source at (0, 50), slow fleet (ships=1, speed=1) → eta=50 turns. A comet
        # at (50, 50) racing right at vx=10 is predicted at x=50+10*50=550 → off-board.
        result = _intercept_comet_linear(0.0, 50.0, 50.0, 50.0, 10.0, 0.0, 1)
        assert result is None

    def test_linear_intercept_overshoot_endpoint_returns_none(self):
        """Helper rejects when the aim point is in-bounds but the fleet overshoots off-board."""
        # Comet at (98, 50) drifting down (vy=1); a 1000-ship fleet (speed=6) aims at
        # the in-bounds point (98, 67), but eta*speed rounds up past the distance so the
        # straight-line endpoint lands at x≈100.5 — off the board.
        result = _intercept_comet_linear(0.0, 50.0, 98.0, 50.0, 0.0, 1.0, 1000)
        assert result is None

    def test_regular_planet_intercept_unchanged(self):
        """Passing comet_ids that don't match target still uses orbit prediction."""
        source = make_planet_at(id=0, x=10.0, y=50.0, owner=0, ships=30)
        target = make_planet_at(id=1, x=70.0, y=50.0)
        fx_no_comet, _, eta_no = intercept(source, target, 0.03, 30)
        fx_with_comet, _, eta_with = intercept(
            source,
            target,
            0.03,
            30,
            comet_ids={99},  # target.id=1 is not in comet_ids
            comet_velocities={99: (3.0, 0.0)},
        )
        assert abs(fx_no_comet - fx_with_comet) < 1e-9
        assert eta_no == eta_with


# --- _blended_best ---


class TestBlendedBest:
    """Direct unit tests for the lookahead/greedy blend-normalization selection.

    candidates are (greedy_score, lookahead_score, target, fraction) tuples;
    target is opaque to the helper, so plain strings stand in for planets.
    """

    def test_single_candidate_returns_it(self):
        from src.strategy import _blended_best

        candidates = [(3.0, 99.0, "only", 0.5)]
        assert _blended_best(candidates, blend=0.7) == ("only", 0.5)

    def test_blend_zero_picks_greedy_winner(self):
        from src.strategy import _blended_best

        # "lo" has the higher lookahead score but blend=0.0 must ignore it.
        candidates = [
            (10.0, 0.0, "hi", 0.4),
            (1.0, 100.0, "lo", 0.6),
        ]
        assert _blended_best(candidates, blend=0.0) == ("hi", 0.4)

    def test_all_equal_greedy_uses_lookahead_without_dividing_by_zero(self):
        from src.strategy import _blended_best

        # hi_g == lo_g would be a ZeroDivisionError without the 1e-9 guard;
        # greedy terms collapse to ~0, so lookahead decides the winner.
        candidates = [
            (5.0, 1.0, "weak_look", 0.3),
            (5.0, 9.0, "strong_look", 0.7),
        ]
        assert _blended_best(candidates, blend=0.5) == ("strong_look", 0.7)

    def test_blended_winner_differs_from_greedy_winner(self):
        from src.strategy import _blended_best

        # Greedy winner is "g" (greedy 10), but with blend weighted toward
        # lookahead, normalized scores favor "l" (lookahead 10).
        candidates = [
            (10.0, 0.0, "g", 0.4),
            (0.0, 10.0, "l", 0.6),
        ]
        assert _blended_best(candidates, blend=0.0) == ("g", 0.4)
        assert _blended_best(candidates, blend=0.8) == ("l", 0.6)

    def test_loop_variables_use_descriptive_names(self):
        import inspect
        from src.strategy import _blended_best

        src = inspect.getsource(_blended_best)
        # PEP8 E741: `l` is indistinguishable from `1`/`I`. The loop unpacking
        # in the blended-normalization path must use descriptive names.
        assert " l," not in src, (
            "_blended_best still uses ambiguous single-letter `l` as a loop variable"
        )
        assert " g," not in src, (
            "_blended_best still uses ambiguous single-letter `g` as a loop variable"
        )


# --- aggression ---

_AGG_PARAMS = {"game_length": 100, "aggression_max": 0.9, "aggression_min": 0.3}


def test_aggression_at_turn_zero_returns_max():
    assert aggression(0, _AGG_PARAMS) == pytest.approx(0.9)


def test_aggression_at_game_length_returns_min():
    assert aggression(100, _AGG_PARAMS) == pytest.approx(0.3)


def test_aggression_beyond_game_length_clamps_to_min():
    # min(turn, game_length) guard prevents going below aggression_min
    assert aggression(200, _AGG_PARAMS) == pytest.approx(0.3)


def test_aggression_midpoint_interpolates_linearly():
    # t = 50/100 = 0.5; value = 0.9 + 0.5*(0.3 - 0.9) = 0.6
    assert aggression(50, _AGG_PARAMS) == pytest.approx(0.6)
