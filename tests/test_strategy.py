import math  # noqa: F401
import pytest  # noqa: F401
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet  # noqa: F401

from src.strategy import PARAMS, Threat, is_stationary  # noqa: F401
from src.strategy import ETA_CONVERGENCE_ITERS
from src.strategy import aggression
from src.strategy import _intercept_comet_linear
from src.strategy import _effective_distance_power
from src.strategy import can_capture, intercept
from src.strategy import _try_send
from src.strategy import _drain_excess
from src.math_utils import _min_dist_pt_to_segment
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


# --- _try_send ---


def test_try_send_valid_send_returns_move():
    source = make_planet(id=0, x=50.0, y=10.0)
    target = make_planet(id=1, owner=-1, x=70.0, y=50.0, ships=5)
    move = _try_send(source, target, 20, angular_velocity=0.03)
    assert move is not None
    future_x, future_y, _eta = intercept(source, target, 0.03, 20)
    expected_angle = angle_to_target(source.x, source.y, future_x, future_y)
    assert move == [source.id, expected_angle, 20]


def test_try_send_none_when_uninterceptable():
    # Comet target with no velocity data yet — intercept() returns (None, None, None).
    source = make_planet(id=0, x=10.0, y=50.0)
    comet = make_planet(id=5, owner=-1, x=60.0, y=50.0, ships=0)
    move = _try_send(
        source, comet, 20, angular_velocity=0.03, comet_ids={5}, comet_velocities={}
    )
    assert move is None


def test_try_send_validate_none_on_can_capture_failure():
    source = make_planet(id=0, x=50.0, y=10.0)
    enemy = make_planet(id=1, owner=1, x=70.0, y=50.0, ships=100, production=5)
    move = _try_send(source, enemy, 1, angular_velocity=0.03, validate=True)
    assert move is None


def test_try_send_validate_none_on_sun_crossing_path():
    # x=90: orbital_radius=40, 40+SUN_RADIUS(10)=50 >= ROTATION_RADIUS_LIMIT(50) → static,
    # so intercept aims at the current position — a straight line through the sun's center.
    source = make_planet(id=0, x=10.0, y=50.0)
    target = make_planet(id=1, owner=-1, x=90.0, y=50.0, ships=0)
    move = _try_send(source, target, 10, angular_velocity=0.03, validate=True)
    assert move is None


def test_try_send_aim_skips_intercept(monkeypatch):
    """aim= reuses caller-supplied geometry, so intercept() is never called —
    this is what keeps the primary launch down to one intercept per candidate."""
    import src.strategy as strat

    source = make_planet(id=0, x=50.0, y=10.0)
    target = make_planet(id=1, owner=-1, x=70.0, y=50.0, ships=5)

    def boom(*args, **kwargs):
        raise AssertionError("intercept() must not be called when aim= is supplied")

    monkeypatch.setattr(strat, "intercept", boom)
    move = strat._try_send(source, target, 20, angular_velocity=0.03, aim=(70.0, 50.0))
    assert move == [source.id, angle_to_target(source.x, source.y, 70.0, 50.0), 20]


def test_try_send_aim_with_validate_raises():
    """Revalidating needs the eta only intercept() returns, so aim=+validate=True
    is a programming error rather than a silently unvalidated send."""
    source = make_planet(id=0, x=50.0, y=10.0)
    target = make_planet(id=1, owner=-1, x=70.0, y=50.0, ships=5)
    with pytest.raises(ValueError):
        _try_send(
            source, target, 20, angular_velocity=0.03, validate=True, aim=(70.0, 50.0)
        )


# --- classify_own ---


def test_classify_own_threatened():
    planet = make_planet(id=1, ships=50, production=5)
    assert classify_own(planet, {1}) == "THREATENED"


def test_classify_own_threatened_overrides_fortress():
    planet = make_planet(
        id=1,
        ships=PARAMS["fortress_min_ships"],
        production=PARAMS["fortress_min_production"],
    )
    assert classify_own(planet, {1}) == "THREATENED"


def test_classify_own_fortress():
    planet = make_planet(
        ships=PARAMS["fortress_min_ships"],
        production=PARAMS["fortress_min_production"],
    )
    assert classify_own(planet, set()) == "FORTRESS"


def test_classify_own_factory():
    planet = make_planet(ships=10, production=PARAMS["factory_min_production"])
    assert classify_own(planet, set()) == "FACTORY"


def test_classify_own_outpost():
    planet = make_planet(ships=10, production=1)
    assert classify_own(planet, set()) == "OUTPOST"


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


def test_classify_neutral_ratio_equal_to_weak_ratio_is_hard():
    params = {**PARAMS, "weak_ratio": 2.0}
    target = make_planet(owner=-1, ships=5)
    assert classify_neutral(target, 10, params=params) == "HARD_NEUTRAL"


def test_classify_neutral_ratio_just_above_weak_ratio_is_easy():
    params = {**PARAMS, "weak_ratio": 2.0}
    target = make_planet(owner=-1, ships=5)
    assert classify_neutral(target, 11, params=params) == "EASY_NEUTRAL"


def test_classify_neutral_zero_ships_ignores_ships_to_send():
    params = {**PARAMS, "weak_ratio": 2.0}
    target = make_planet(owner=-1, ships=0)
    assert classify_neutral(target, 1000, params=params) == "EASY_NEUTRAL"


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


def test_classify_enemy_ratio_equal_to_weak_ratio_is_contested():
    params = {**PARAMS, "weak_ratio": 2.0, "contested_ratio": 1.0}
    target = make_planet(owner=1, ships=5, production=0)
    eta = 10
    # expected_defenders = 5; ratio = 10/5 = 2.0 == weak_ratio
    assert classify_enemy(target, 10, eta, params=params) == "CONTESTED_ENEMY"


def test_classify_enemy_ratio_equal_to_contested_ratio_is_hardened():
    params = {**PARAMS, "weak_ratio": 2.0, "contested_ratio": 1.5}
    target = make_planet(owner=1, ships=10, production=0)
    eta = 10
    # expected_defenders = 10; ratio = 15/10 = 1.5 == contested_ratio
    assert classify_enemy(target, 15, eta, params=params) == "HARDENED_ENEMY"


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


def test_detect_threats_aggregation_dict_not_named_agg():
    # Enforce the rename: the threat-aggregation dict inside detect_threats must not
    # use the overloaded name `agg` (which elsewhere means aggression: float).
    import inspect
    import ast

    source = inspect.getsource(detect_threats)
    tree = ast.parse(source)
    # Collect all local variable names assigned within detect_threats.
    assigned_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    assert "agg" not in assigned_names, (
        "detect_threats still uses 'agg' as a local variable name; "
        "rename the aggregation dict to something self-documenting "
        "(e.g. 'inbound_by_planet' or 'threat_agg')"
    )


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


def test_detect_threats_segment_catches_between_samples():
    # A fast fleet (1000 ships → speed=6) passes between integer-sample positions.
    # Planet at (95, 50): orbital_radius=45, 45+SUN_RADIUS(10)=55 >= ROTATION_RADIUS_LIMIT(50) → static.
    # Fleet at (86, 57) heading right:
    #   t=1 → (92, 57), dist=sqrt(9+49)=sqrt(58)≈7.62 > threat_radius (~7.36) — missed by point check
    #   t=2 → (98, 57), dist=sqrt(58)≈7.62 > threat_radius              — missed by point check
    #   closest approach at t=1.5: fleet at (95, 57), dist=7.0 < threat_radius — caught by segment check
    planet = make_planet(id=1, owner=0, x=95.0, y=50.0)
    fleet = make_fleet(owner=1, x=86.0, y=57.0, angle=0.0, ships=1000)
    threats = detect_threats([planet], [fleet], player=0, angular_velocity=0.03)
    assert any(t.planet_id == 1 for t in threats), (
        "segment-based check must detect a fleet whose closest approach falls between "
        "integer samples; point-based check misses it"
    )


def test_detect_threats_hoists_planet_position_prediction(monkeypatch):
    # predict_planet_position depends only on (planet, t), not on the enemy fleet,
    # so it must be computed once per (planet, t) and reused across every fleet —
    # not recomputed for each fleet. With F=3 fleets, W=threat_eta_window, P=2
    # planets, call count must be W*P, not F*W*P.
    import src.strategy as strategy

    planet_a = make_planet(id=1, owner=0, x=90.0, y=50.0)
    planet_b = make_planet(id=2, owner=0, x=-90.0, y=50.0)
    # All fleets head away (angle=pi) from both planets so no match ever occurs,
    # guaranteeing the full t-range is walked for every planet with no early exit.
    fleet_a = make_fleet(id=0, owner=1, x=70.0, y=50.0, angle=math.pi, ships=10)
    fleet_b = make_fleet(id=1, owner=1, x=72.0, y=50.0, angle=math.pi, ships=12)
    fleet_c = make_fleet(id=2, owner=1, x=74.0, y=50.0, angle=math.pi, ships=14)

    calls = []
    original = strategy.predict_planet_position

    def spy(planet, av, t):
        calls.append((planet.id, t))
        return original(planet, av, t)

    monkeypatch.setattr(strategy, "predict_planet_position", spy)

    strategy.detect_threats(
        [planet_a, planet_b],
        [fleet_a, fleet_b, fleet_c],
        player=0,
        angular_velocity=0.03,
    )

    window = PARAMS["threat_eta_window"]
    assert len(calls) == window * 2, (
        f"expected {window * 2} predict_planet_position calls (W*P, independent "
        f"of fleet count), got {len(calls)}"
    )


def test_detect_threats_skips_precompute_without_enemy_fleets(monkeypatch):
    # With no enemy fleets present (empty list, or only own fleets), the
    # planet_positions precompute must be skipped entirely — predict_planet_position
    # should never be called — since the loop below has nothing to check against.
    import src.strategy as strategy

    planet = make_planet(id=1, owner=0, x=90.0, y=50.0)
    own_fleet = make_fleet(owner=0, x=70.0, y=50.0, angle=0.0, ships=10)

    calls = []
    original = strategy.predict_planet_position

    def spy(planet, av, t):
        calls.append((planet.id, t))
        return original(planet, av, t)

    monkeypatch.setattr(strategy, "predict_planet_position", spy)

    threats_empty = strategy.detect_threats(
        [planet], [], player=0, angular_velocity=0.03
    )
    threats_own_only = strategy.detect_threats(
        [planet], [own_fleet], player=0, angular_velocity=0.03
    )

    assert calls == [], (
        f"expected predict_planet_position to be skipped when no enemy fleets "
        f"are present, got {len(calls)} calls"
    )
    assert threats_empty == []
    assert threats_own_only == []


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


def test_handle_threats_skips_reinforcement_below_min_garrison():
    # min_garrison is reused here as a minimum reinforcement size (see comment at
    # strategy.py handle_threats): ships_to_send=5 < min_garrison=6, so the guard
    # skips this reinforcement even though the source's own garrison is untouched.
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 6,
        "defense_reinforce_fraction": 0.1,
        "defense_incoming_multiplier": 0.0,
        "eta_buffer": 5,
    }
    flat = int(50 * 0.1)  # 5 — below min_garrison(6)
    assert flat < params["min_garrison"]
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert moves == []


def test_handle_threats_reinforces_when_at_min_garrison_boundary():
    # Companion to the skip test above: ships_to_send == min_garrison exactly
    # clears the guard (`< min_garrison` only rejects strictly smaller sends),
    # so a reinforcement move IS emitted.
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=50, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 5,
        "defense_reinforce_fraction": 0.1,
        "defense_incoming_multiplier": 0.0,
        "eta_buffer": 5,
    }
    flat = int(50 * 0.1)  # 5 — exactly at min_garrison(5)
    assert flat == params["min_garrison"]
    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert len(moves) == 1
    assert moves[0][0] == 2
    assert moves[0][2] == flat


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


def test_handle_threats_missing_defense_incoming_multiplier_raises():
    """defense_incoming_multiplier is present in PARAMS and PARAM_SPACE, so a
    params dict missing it must fail loudly (KeyError), not silently apply a
    0.0 multiplier — see issue #245."""
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=70.0, y=50.0, ships=100, production=4)
    threats = [Threat(planet_id=1, incoming_ships=100, eta=20)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {k: v for k, v in PARAMS.items() if k != "defense_incoming_multiplier"}
    with pytest.raises(KeyError):
        handle_threats(
            threats,
            [threatened, fortress],
            own_classes,
            angular_velocity=0.03,
            params=params,
        )


def test_handle_threats_skips_reinforcement_whose_path_crosses_sun():
    """handle_threats' sun-skip (strategy.py `if path_crosses_sun(...): continue`)
    is only reachable after the ETA and min_garrison gates pass — this test proves
    it fires on its own, not as a byproduct of one of those other gates.

    Geometry: fortress at (10, 50), threatened planet at (90, 50) — both static
    (x=90: orbital_radius=40, 40+SUN_RADIUS(10)=50 >= ROTATION_RADIUS_LIMIT(50)),
    so intercept() aims straight at (90, 50) and the source->intercept segment is
    the horizontal line y=50, which passes directly through CENTER (50, 50) —
    the same direct-hit geometry as test_try_send_validate_none_on_sun_crossing_path.

    Gates satisfied so the sun check is the *only* reason for rejection:
      - min_garrison: fortress.ships=100, min_garrison=10, defense_reinforce_fraction=0.5
        -> ships_to_send=50, well over min_garrison.
      - eta: threat.eta=200 is deliberately huge (the "large threat.eta" from the
        issue) so the real intercept ETA for an 80-unit trip (well under 80 turns
        even at the slowest fleet speed) clears `eta <= threat.eta - eta_buffer(5) = 195`.
    """
    threatened = make_planet(id=1, owner=0, x=90.0, y=50.0, ships=20, production=2)
    fortress = make_planet(id=2, owner=0, x=10.0, y=50.0, ships=100, production=4)
    threats = [Threat(planet_id=1, incoming_ships=30, eta=200)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.5,
        "eta_buffer": 5,
    }
    # Precondition: the straight-line path this geometry produces does cross the sun.
    assert path_crosses_sun(fortress.x, fortress.y, threatened.x, threatened.y) is True

    moves = handle_threats(
        threats,
        [threatened, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert moves == []

    # Contrast: same source, same ETA/garrison margins, geometry shifted off the
    # sun line (y=90 instead of y=50 — CENTER's y-distance is now 40 > SUN_RADIUS).
    # The reinforcement now fires, proving the suppression above is sun-specific
    # rather than an unrelated ETA or garrison gate silently rejecting it.
    threatened_clear = make_planet(id=1, owner=0, x=90.0, y=90.0, ships=20, production=2)
    fortress_clear = make_planet(id=2, owner=0, x=10.0, y=90.0, ships=100, production=4)
    assert (
        path_crosses_sun(fortress_clear.x, fortress_clear.y, threatened_clear.x, threatened_clear.y)
        is False
    )
    clear_moves = handle_threats(
        threats,
        [threatened_clear, fortress_clear],
        own_classes,
        angular_velocity=0.03,
        params=params,
    )
    assert len(clear_moves) == 1
    assert clear_moves[0][0] == fortress_clear.id


def test_handle_threats_comet_target_uses_linear_velocity_intercept():
    """handle_threats must thread comet_ids/comet_velocities into its intercept()
    call so a reinforcement aimed at an owned comet under threat uses the
    linear-velocity path (intercept()'s comet branch) instead of silently
    falling back to orbital-iteration prediction (comet_ids=frozenset() default)
    — see issue #202. Analogous to test_comet_intercept_uses_linear_velocity but
    exercised through handle_threats.

    Geometry mirrors the sun-clear case above (y=90, off the CENTER line) so the
    sun-crossing gate can't interfere.
    """
    comet = make_planet_at(id=1, x=60.0, y=90.0, owner=0, ships=5, production=1)
    fortress = make_planet_at(id=2, x=10.0, y=90.0, owner=0, ships=100, production=4)
    # Diagonal drift (not purely horizontal) so the linear-predicted aim point
    # is off the source->comet's initial ray — otherwise the linear and the
    # orbital-fallback (static) aim points would coincidentally share an angle
    # from the source even though their positions differ.
    vel = (-1.0, -1.0)
    comet_ids = {1}
    comet_velocities = {1: vel}

    # defense_incoming_multiplier=0.0 collapses magnitude to 0, so ships_to_send
    # is a pure function of defense_reinforce_fraction, predictable without
    # re-deriving handle_threats' internal formula.
    params = {
        **PARAMS,
        "min_garrison": 10,
        "defense_reinforce_fraction": 0.5,
        "defense_incoming_multiplier": 0.0,
        "eta_buffer": 0,
    }
    ships_to_send = int(fortress.ships * params["defense_reinforce_fraction"])

    # Oracle: what the linear-velocity comet path actually predicts.
    expected_fx, expected_fy, expected_eta = intercept(
        fortress,
        comet,
        angular_velocity=0.03,
        ships_to_send=ships_to_send,
        comet_ids=comet_ids,
        comet_velocities=comet_velocities,
    )
    assert expected_fx is not None

    # Contrast: what the orbital-iteration fallback (no comet threading) would
    # predict instead -- must differ, or this test can't distinguish the fix
    # from the pre-fix default-args fallback.
    orbital_fx, orbital_fy, _ = intercept(
        fortress, comet, angular_velocity=0.03, ships_to_send=ships_to_send
    )
    assert (expected_fx, expected_fy) != (orbital_fx, orbital_fy)

    threats = [Threat(planet_id=1, incoming_ships=30, eta=expected_eta)]
    own_classes = {1: "THREATENED", 2: "FORTRESS"}

    moves = handle_threats(
        threats,
        [comet, fortress],
        own_classes,
        angular_velocity=0.03,
        params=params,
        comet_ids=comet_ids,
        comet_velocities=comet_velocities,
    )

    assert len(moves) == 1
    source_id, angle, ships_sent = moves[0]
    assert source_id == fortress.id
    assert ships_sent == ships_to_send
    assert angle == angle_to_target(fortress.x, fortress.y, expected_fx, expected_fy)
    assert angle != angle_to_target(fortress.x, fortress.y, orbital_fx, orbital_fy)


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


def test_plan_expansion_missing_lookahead_blend_raises():
    """lookahead_blend is present in PARAMS and PARAM_SPACE, so a params dict
    missing it must fail loudly (KeyError), not silently degrade to
    greedy-only expansion — see issue #245."""
    fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=1, production=1)
    own_classes = {0: "FORTRESS"}
    params = {k: v for k, v in PARAMS.items() if k != "lookahead_blend"}
    with pytest.raises(KeyError):
        plan_expansion(
            [fortress],
            [],
            [soft_enemy],
            own_classes,
            angular_velocity=0.03,
            params=params,
        )


def test_plan_expansion_missing_optional_frac_key_still_plans():
    """The frac_* lookup at src/strategy.py is intentionally optional (some
    (src_class, tgt_class) combos have no frac key per SKIP_COMBOS) — a params
    dict missing the frac_* key for the pair being evaluated must skip that
    target gracefully (fraction is None -> continue), not raise KeyError, and
    the rest of plan_expansion must still run — unaffected by the strict
    indexing of defense_incoming_multiplier/lookahead_blend."""
    outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    easy_low = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=5, production=1)
    own_classes = {0: "OUTPOST"}
    params = {**PARAMS, "min_garrison": 10, "weak_ratio": 1.5}
    del params["frac_outpost_easy_neutral"]
    moves = plan_expansion(
        [outpost], [easy_low], [], own_classes, angular_velocity=0.03, params=params
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


# --- _drain_excess ---


def test_drain_excess_drains_to_second_target():
    """Leftover ships after the primary send drain into the next-best,
    not-yet-targeted candidate."""
    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=100, production=4)
    high = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=5)
    low = make_planet(id=2, owner=-1, x=68.0, y=50.0, ships=0, production=2)
    frac = PARAMS["frac_fortress_easy_neutral"]
    candidates = [
        (10.0, 10.0, high, frac, 0.0, 0.0),
        (5.0, 5.0, low, frac, 0.0, 0.0),
    ]
    first_send = max(1, int(source.ships * frac))
    ships_remaining = source.ships - first_send

    moves = _drain_excess(
        source, candidates, high.id, ships_remaining, min_garrison=10, agg=1.0,
        angular_velocity=0.03,
    )

    assert len(moves) == 1
    assert moves[0][0] == source.id
    extra_send = max(1, int(ships_remaining * frac))
    assert moves[0][2] == extra_send


def test_drain_excess_clamps_at_min_garrison():
    """When the leftover fleet sits just above min_garrison, the drain send is
    clamped to (ships_remaining - min_garrison) rather than over-draining."""
    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=35, production=4)
    high = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=5)
    low = make_planet(id=2, owner=-1, x=68.0, y=50.0, ships=0, production=2)
    frac = PARAMS["frac_fortress_easy_neutral"]
    candidates = [
        (10.0, 10.0, high, frac, 0.0, 0.0),
        (5.0, 5.0, low, frac, 0.0, 0.0),
    ]
    first_send = max(1, int(source.ships * frac))
    ships_remaining = source.ships - first_send
    min_garrison = 10
    unclamped = max(1, int(ships_remaining * frac))
    assert unclamped > ships_remaining - min_garrison  # floor branch is exercised

    moves = _drain_excess(
        source, candidates, high.id, ships_remaining, min_garrison=min_garrison,
        agg=1.0, angular_velocity=0.03,
    )

    assert len(moves) == 1
    assert moves[0][2] == ships_remaining - min_garrison


def test_plan_expansion_drain_ranks_by_greedy_not_blended():
    """Drain loop sorts by raw greedy score c[0], not the blended score used for
    primary selection.  Under lookahead_blend > 0 the primary and drain targets
    can therefore differ: primary = blended-best, drain = greedy-best of remaining.

    Setup: target_a is close with moderate production (high greedy score, low
    lookahead); target_b is farther with high production (low greedy score, high
    lookahead score once its fleet arrives within the 5-step window).  With
    lookahead_blend ≈ 0.9 the primary flips from a to b, yet the drain still
    visits a first because the drain sorts by greedy c[0].

    If this divergence is judged unintended, this test is the red test for
    aligning the drain ranking to the blended score; do not change behavior here.
    """
    # radius=10 ensures both fleets land within the 5-step lookahead window.
    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=300, production=4)
    target_a = make_planet(
        id=1, owner=-1, x=85.0, y=50.0, ships=0, production=3, radius=10
    )
    target_b = make_planet(
        id=2, owner=-1, x=50.0, y=70.0, ships=0, production=10, radius=10
    )
    own_classes = {0: "FORTRESS"}
    all_planets = [source, target_a, target_b]

    base = {
        **PARAMS,
        "min_garrison": 10,
        "min_garrison_early": 10,
        "garrison_ramp_turns": 1,
    }
    greedy_params = {**base, "lookahead_blend": 0.0}
    blend_params = {**base, "lookahead_blend": 0.9032, "lookahead_turns": 5}

    # blend=0: primary → a (greedy-best: close, moderate production)
    moves_greedy = plan_expansion(
        [source],
        [target_a, target_b],
        [],
        own_classes,
        angular_velocity=0.03,
        params=greedy_params,
        turn=0,
    )
    # blend=0.9032 + lookahead: primary → b (lookahead-best: high production),
    # drain → a (greedy-best of remaining — drain ignores blend).
    moves_blend = plan_expansion(
        [source],
        [target_a, target_b],
        [],
        own_classes,
        angular_velocity=0.03,
        params=blend_params,
        turn=0,
        initial_planets=all_planets,
        fleets=[],
        player=0,
    )

    frac = PARAMS["frac_fortress_easy_neutral"]
    first_send = max(1, int(source.ships * frac))
    ships_after = source.ships - first_send
    extra_send = max(1, int(ships_after * frac))

    # Greedy primary is target_a (highest greedy score).
    fx_a_p, fy_a_p, _ = intercept(source, target_a, 0.03, first_send)
    assert moves_greedy[0][1] == pytest.approx(
        angle_to_target(source.x, source.y, fx_a_p, fy_a_p)
    )

    # Blended primary is target_b (lookahead dominates at blend ≈ 0.9).
    assert len(moves_blend) == 2
    fx_b_p, fy_b_p, _ = intercept(source, target_b, 0.03, first_send)
    assert moves_blend[0][1] == pytest.approx(
        angle_to_target(source.x, source.y, fx_b_p, fy_b_p)
    )

    # Drain still ranks by greedy c[0] — target_a (greedy-best) gets the drain fleet.
    fx_a_d, fy_a_d, _ = intercept(source, target_a, 0.03, extra_send)
    assert moves_blend[1][1] == pytest.approx(
        angle_to_target(source.x, source.y, fx_a_d, fy_a_d)
    )


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


def test_plan_expansion_skips_target_whose_path_crosses_sun():
    # Source and target sit opposite each other across the sun (both at
    # orbital_radius=40, stationary): the straight-line intercept path runs
    # through CENTER (50,50), well within SUN_RADIUS — plan_expansion must
    # drop the only candidate rather than suicide the fleet into the sun.
    source = make_planet(id=0, owner=0, x=90.0, y=50.0, ships=60, production=2)
    target = make_planet(id=1, owner=-1, x=10.0, y=50.0, ships=0, production=1)
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion([source], [target], [], own_classes, angular_velocity=0.03)
    assert moves == []


def test_plan_expansion_sends_when_path_is_clear_of_sun():
    # Positive control: same source and orbital radius, target rotated 90
    # degrees around the sun so the straight-line path clears the exclusion
    # zone (closest approach to CENTER is ~28.3, outside SUN_RADIUS=10) —
    # proving the prior test's no-move result is specifically the sun-crossing
    # skip, not some other rejection.
    source = make_planet(id=0, owner=0, x=90.0, y=50.0, ships=60, production=2)
    target = make_planet(id=1, owner=-1, x=50.0, y=90.0, ships=0, production=1)
    own_classes = {0: "OUTPOST"}
    moves = plan_expansion([source], [target], [], own_classes, angular_velocity=0.03)
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


def test_plan_moves_threads_comet_ids_and_velocities_into_handle_threats(monkeypatch):
    """plan_moves must forward its own comet_ids/comet_velocities through to
    handle_threats — see issue #202. Spies on handle_threats to capture the
    forwarded args rather than re-deriving comet intercept geometry."""
    import src.strategy as strategy

    owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    comet_ids = {5}
    comet_velocities = {5: (1.0, 0.0)}

    calls = []
    original = strategy.handle_threats

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(strategy, "handle_threats", spy)

    strategy.plan_moves(
        [owned],
        fleets=[],
        player=0,
        angular_velocity=0.03,
        comet_ids=comet_ids,
        comet_velocities=comet_velocities,
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    forwarded = list(args) + list(kwargs.values())
    assert comet_ids in forwarded
    assert comet_velocities in forwarded


def test_plan_expansion_late_game_agg_scales_sends_and_inflates_floor():
    """With agg < 1 (late-game regime), plan_expansion applies agg in two directions:
    (a) every send is multiplied by agg (scaled down), and
    (b) the garrison floor is divided by agg (inflated up).

    Two targets are required so the drain loop runs: after the primary send,
    ships_remaining sits between the plain floor and the inflated floor, making
    the clamping difference observable.  This test fails if the '/ agg' at
    strategy.py is removed because the drain then uses the plain floor and leaves
    fewer ships than the inflated floor."""
    agg = 0.5
    params = {
        **PARAMS,
        "min_garrison": 10,
        "min_garrison_early": 10,
        "garrison_ramp_turns": 1,
    }
    turn = 100  # past ramp → _effective_min_garrison returns min_garrison (10)
    # Source ships chosen so ships_remaining after the primary send (9) equals 21,
    # which sits between the plain floor (10) and the inflated floor (int(10/0.5)=20).
    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=30, production=4)
    high = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=5)
    low = make_planet(id=2, owner=-1, x=68.0, y=50.0, ships=0, production=2)
    own_classes = {0: "FORTRESS"}

    moves_agg = plan_expansion(
        [source], [high, low], [], own_classes, angular_velocity=0.03,
        agg=agg, params=params, turn=turn,
    )
    moves_full = plan_expansion(
        [source], [high, low], [], own_classes, angular_velocity=0.03,
        agg=1.0, params=params, turn=turn,
    )

    assert len(moves_agg) >= 1, "Expected at least one expansion move with agg=0.5"

    # (a) Primary send is scaled down by agg.
    fraction = params["frac_fortress_easy_neutral"]
    expected_primary = max(1, int(source.ships * fraction * agg))
    assert moves_agg[0][2] == expected_primary
    assert moves_agg[0][2] < moves_full[0][2], (
        "agg=0.5 primary send must be smaller than agg=1.0 primary send"
    )

    # (b) After all sends the source retains at least the inflated floor.
    # inflated_floor = int(effective_min_garrison / agg) = int(10 / 0.5) = 20.
    # Removing '/ agg' from strategy.py makes the drain use floor=10 instead,
    # leaving ~15 ships (< 20), which causes this assertion to fail.
    inflated_floor = int(params["min_garrison"] / agg)
    total_sent = sum(m[2] for m in moves_agg)
    assert source.ships - total_sent >= inflated_floor, (
        f"source left with {source.ships - total_sent} ships, "
        f"below the inflated floor {inflated_floor} (= min_garrison / agg)"
    )


# --- plan_expansion structural ---


def test_plan_expansion_lookahead_guard_not_duplicated():
    """The lookahead-enablement condition must be computed once in plan_expansion
    and threaded into its helpers as a parameter, rather than being recomputed
    verbatim in each helper. Duplication means the copies can silently drift out
    of sync — this scans the whole module, not just plan_expansion's own source,
    since the guard actually lives in the helper functions plan_expansion calls."""
    import inspect
    import src.strategy as strat

    src = inspect.getsource(strat)
    guard = "blend > 0 and initial_planets is not None and fleets is not None"
    count = src.count(guard)
    assert count <= 1, (
        f"The guard '{guard}' appears {count} times in strategy.py — "
        "hoist it into a single `use_lookahead` flag computed once in "
        "plan_expansion and threaded into its helpers as a parameter."
    )


def test_plan_expansion_primary_fleet_reuses_intercept_geometry(monkeypatch):
    """Primary fleet geometry is reused from the scoring-loop intercept result,
    not recomputed — intercept() is called exactly once for the winning candidate."""
    import src.strategy as strat

    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=5, production=1)
    own_classes = {0: "FORTRESS"}

    call_count = []
    real_intercept = strat.intercept

    def counting_intercept(src, tgt, av, ships, comet_ids=frozenset(), comet_velocities=None):
        result = real_intercept(src, tgt, av, ships, comet_ids, comet_velocities)
        call_count.append((src.id, tgt.id, ships))
        return result

    monkeypatch.setattr(strat, "intercept", counting_intercept)

    moves = plan_expansion(
        [source], [target], [], own_classes, angular_velocity=0.03
    )

    assert len(moves) == 1, "Expected one move to be generated"
    # intercept must be called exactly once: the scoring-loop result is reused for the
    # primary fleet launch rather than recomputed.
    assert len(call_count) == 1, (
        f"Expected intercept called once for winning candidate, got {len(call_count)}: {call_count}"
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


def test_turn_ramp_zero_ramp_turns_returns_end():
    from src.strategy import _turn_ramp

    assert _turn_ramp(0, 0, 4.0, 2.0) == 2.0
    assert _turn_ramp(50, 0, 4.0, 2.0) == 2.0


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

    def test_linear_intercept_overshoot_uses_math_utils_distance(self, monkeypatch):
        """_intercept_comet_linear overshoot check must use distance(), not inline math.sqrt."""
        import src.strategy as mod

        calls = []
        real_distance = mod.distance
        monkeypatch.setattr(
            mod, "distance", lambda *a: (calls.append(a), real_distance(*a))[1]
        )

        result = _intercept_comet_linear(0.0, 50.0, 50.0, 50.0, 0.0, 0.0, 10)

        assert result is not None
        assert calls, (
            "distance() was not called — _intercept_comet_linear still uses inline math.sqrt"
        )


# --- _blended_best ---


class TestBlendedBest:
    """Direct unit tests for the lookahead/greedy blend-normalization selection.

    candidates are (greedy_score, lookahead_score, target, fraction, future_x, future_y) tuples;
    target is opaque to the helper, so plain strings stand in for planets.
    The function returns (target, fraction, future_x, future_y) so the caller can reuse
    the already-computed intercept geometry.
    """

    def test_single_candidate_returns_it(self):
        from src.strategy import _blended_best

        candidates = [(3.0, 99.0, "only", 0.5, 1.0, 2.0)]
        assert _blended_best(candidates, blend=0.7) == ("only", 0.5, 1.0, 2.0)

    def test_blend_zero_picks_greedy_winner(self):
        from src.strategy import _blended_best

        # "lo" has the higher lookahead score but blend=0.0 must ignore it.
        candidates = [
            (10.0, 0.0, "hi", 0.4, 1.0, 2.0),
            (1.0, 100.0, "lo", 0.6, 3.0, 4.0),
        ]
        assert _blended_best(candidates, blend=0.0) == ("hi", 0.4, 1.0, 2.0)

    def test_all_equal_greedy_uses_lookahead_without_dividing_by_zero(self):
        from src.strategy import _blended_best

        # hi_g == lo_g would be a ZeroDivisionError without the 1e-9 guard;
        # greedy terms collapse to ~0, so lookahead decides the winner.
        candidates = [
            (5.0, 1.0, "weak_look", 0.3, 1.0, 2.0),
            (5.0, 9.0, "strong_look", 0.7, 3.0, 4.0),
        ]
        assert _blended_best(candidates, blend=0.5) == ("strong_look", 0.7, 3.0, 4.0)

    def test_all_equal_lookahead_uses_greedy_without_dividing_by_zero(self):
        from src.strategy import _blended_best

        nl_values = []

        class RecordingScore(float):
            """Lookahead score that records the nl quotient computed from it."""

            def __sub__(self, other):
                return RecordingScore(float(self) - float(other))

            def __add__(self, other):
                return RecordingScore(float(self) + float(other))

            def __truediv__(self, other):
                quotient = float(self) / float(other)
                nl_values.append(quotient)
                return quotient

        # hi_l == lo_l would be a ZeroDivisionError without the 1e-9 guard;
        # lookahead terms (nl) collapse to 0 for every candidate, so greedy
        # score decides the winner. Only the lookahead scores are
        # RecordingScore, so the recorded quotients are exactly the
        # per-candidate nl values — ng is computed from plain floats.
        candidates = [
            (1.0, RecordingScore(5.0), "weak_greedy", 0.3, 1.0, 2.0),
            (9.0, RecordingScore(5.0), "strong_greedy", 0.7, 3.0, 4.0),
        ]
        assert _blended_best(candidates, blend=0.5) == ("strong_greedy", 0.7, 3.0, 4.0)
        assert nl_values == [0.0, 0.0], (
            f"nl must collapse to 0 for every candidate when hi_l == lo_l, got {nl_values}"
        )

    def test_blended_winner_differs_from_greedy_winner(self):
        from src.strategy import _blended_best

        # Greedy winner is "g" (greedy 10), but with blend weighted toward
        # lookahead, normalized scores favor "l" (lookahead 10).
        candidates = [
            (10.0, 0.0, "g", 0.4, 1.0, 2.0),
            (0.0, 10.0, "l", 0.6, 3.0, 4.0),
        ]
        assert _blended_best(candidates, blend=0.0) == ("g", 0.4, 1.0, 2.0)
        assert _blended_best(candidates, blend=0.8) == ("l", 0.6, 3.0, 4.0)

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


# --- plan_expansion candidates comment ---


def test_generate_candidates_comment_lists_six_fields():
    """The candidates accumulator comment must name every tuple field.

    Renamed from test_plan_expansion_candidates_comment_lists_six_fields in #115.
    The assertion is unchanged — it inspects source text for the `candidates = []`
    comment, and #115 moved that line out of plan_expansion into
    _generate_candidates, so the test has to follow the code it pins. Keeping the
    plan_expansion name would point readers at a function that no longer contains
    the comment being checked.
    """
    import inspect

    from src.strategy import _generate_candidates

    src_lines = inspect.getsource(_generate_candidates).splitlines()
    # Locate the specific inline comment on the candidates accumulator.
    comment_line = next(
        (line for line in src_lines if "candidates = []" in line and "list of" in line),
        None,
    )
    assert comment_line is not None, (
        "candidates = [] comment line not found in _generate_candidates"
    )
    # The comment must list all six tuple fields so readers aren't misled
    # about the shape passed to _blended_best.
    for field in ("greedy_score", "lookahead_score", "target", "fraction", "future_x", "future_y"):
        assert field in comment_line, (
            f"_generate_candidates candidates comment is missing '{field}'; "
            "update the comment to match the 6-tuple actually appended"
        )


# --- _build_opponent_fn ---


def test_build_opponent_fn_none_when_blend_zero():
    from src.strategy import _build_opponent_fn

    planets = [make_planet(id=0, owner=0, ships=20)]
    fleets = []
    result = _build_opponent_fn(
        planets,
        fleets,
        turn=0,
        player=0,
        angular_velocity=0.03,
        params=PARAMS,
        use_lookahead=False,
    )
    assert result is None


def test_build_opponent_fn_none_when_inputs_missing():
    from src.strategy import _build_opponent_fn

    result = _build_opponent_fn(
        None,
        None,
        turn=0,
        player=0,
        angular_velocity=0.03,
        params=PARAMS,
        use_lookahead=False,
    )
    assert result is None


def test_build_opponent_fn_returns_frozen_plan_moves_result():
    from src.strategy import _build_opponent_fn, build_state, plan_moves

    planets = [
        make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20),
        make_planet(id=1, owner=1, x=30.0, y=50.0, ships=20),
        make_planet(id=2, owner=-1, x=50.0, y=90.0, ships=5),
    ]
    fleets = []
    turn = 0
    player = 0
    angular_velocity = 0.03

    opponent_fn = _build_opponent_fn(
        planets, fleets, turn, player, angular_velocity, PARAMS, use_lookahead=True
    )
    assert opponent_fn is not None

    opp_player = 1 - player
    greedy_params_opp = {**PARAMS, "lookahead_blend": 0.0}
    base = build_state(planets, fleets, turn)
    expected_moves = plan_moves(
        base.planets,
        base.fleets,
        opp_player,
        angular_velocity,
        turn=turn,
        params=greedy_params_opp,
        initial_planets=planets,
    )

    assert opponent_fn(state=None) == expected_moves


# --- _generate_candidates ---


def test_generate_candidates_soft_enemy_produces_one_candidate():
    from src.strategy import _generate_candidates, _effective_distance_power

    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
    soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=1, production=1)
    dist_power = _effective_distance_power(turn=0, params=PARAMS)

    candidates = _generate_candidates(
        source,
        "FORTRESS",
        [soft_enemy],
        dist_power,
        agg=1.0,
        angular_velocity=0.03,
        params=PARAMS,
        comet_ids=frozenset(),
        comet_velocities=None,
        opponent_fn=None,
        initial_planets=None,
        fleets=None,
        player=0,
        turn=0,
        use_lookahead=False,
    )

    assert len(candidates) == 1
    greedy_score, lookahead_score, target, fraction, future_x, future_y = candidates[0]
    assert target is soft_enemy
    assert fraction == PARAMS["frac_fortress_soft_enemy"]
    assert lookahead_score == greedy_score  # blend=0.0 fallback


def test_generate_candidates_skip_combo_produces_none():
    """(OUTPOST, HARD_NEUTRAL) is a SKIP_COMBOS pair (src/config.py) — the
    outpost's probe ratio against a heavily-defended neutral must classify as
    HARD_NEUTRAL, which is skipped outright with no candidate emitted."""
    from src.strategy import _generate_candidates, _effective_distance_power
    from src.config import SKIP_COMBOS

    assert ("OUTPOST", "HARD_NEUTRAL") in SKIP_COMBOS

    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
    hard_neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=100, production=2)
    dist_power = _effective_distance_power(turn=0, params=PARAMS)

    candidates = _generate_candidates(
        source,
        "OUTPOST",
        [hard_neutral],
        dist_power,
        agg=1.0,
        angular_velocity=0.03,
        params=PARAMS,
        comet_ids=frozenset(),
        comet_velocities=None,
        opponent_fn=None,
        initial_planets=None,
        fleets=None,
        player=0,
        turn=0,
        use_lookahead=False,
    )

    assert candidates == []


def test_generate_candidates_excludes_target_failing_can_capture():
    """The target classifies as SOFT_ENEMY against the full-fleet probe (so it
    clears SKIP_COMBOS and has a frac_* key), but a deliberately tiny fraction
    sends so few ships that the actual (slower, single-ship) intercept arrives
    with a smaller fleet than the target can defend with — can_capture must
    reject it and no candidate is emitted."""
    from src.strategy import _generate_candidates, _effective_distance_power

    source = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=100, production=4)
    soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=5, production=1)
    dist_power = _effective_distance_power(turn=0, params=PARAMS)
    params = {**PARAMS, "frac_fortress_soft_enemy": 0.01}

    candidates = _generate_candidates(
        source,
        "FORTRESS",
        [soft_enemy],
        dist_power,
        agg=1.0,
        angular_velocity=0.03,
        params=params,
        comet_ids=frozenset(),
        comet_velocities=None,
        opponent_fn=None,
        initial_planets=None,
        fleets=None,
        player=0,
        turn=0,
        use_lookahead=False,
    )

    assert candidates == []


# --- ETA_CONVERGENCE_ITERS shared constant ---


def test_eta_convergence_iters_used_in_both_intercept_loops():
    import inspect

    # Both ETA fixed-point loops must reference the shared constant, not bare literals.
    for fn in (intercept, _intercept_comet_linear):
        src = inspect.getsource(fn)
        assert "range(8)" not in src, (
            f"{fn.__name__} still uses bare range(8); replace with range(ETA_CONVERGENCE_ITERS)"
        )
        assert "range(10)" not in src, (
            f"{fn.__name__} still uses bare range(10); replace with range(ETA_CONVERGENCE_ITERS)"
        )
        assert "ETA_CONVERGENCE_ITERS" in src, (
            f"{fn.__name__} does not reference ETA_CONVERGENCE_ITERS"
        )


# --- _min_dist_pt_to_segment ---


def test_min_dist_pt_to_segment_zero_length_segment_uses_point_distance():
    # sx1==sx2 and sy1==sy2: d_len_sq == 0 branch, straight point-to-point distance.
    dist = _min_dist_pt_to_segment(0.0, 0.0, 3.0, 4.0, 3.0, 4.0)
    assert dist == pytest.approx(5.0)


def test_min_dist_pt_to_segment_clamps_before_start():
    # Projection falls before t=0, so distance clamps to the start endpoint (0, 0).
    dist = _min_dist_pt_to_segment(-5.0, 3.0, 0.0, 0.0, 10.0, 0.0)
    assert dist == pytest.approx(math.sqrt(34.0))


def test_min_dist_pt_to_segment_clamps_past_end():
    # Projection falls past t=1, so distance clamps to the end endpoint (10, 0).
    dist = _min_dist_pt_to_segment(15.0, 3.0, 0.0, 0.0, 10.0, 0.0)
    assert dist == pytest.approx(math.sqrt(34.0))


def test_min_dist_pt_to_segment_interior_projection_uses_perpendicular_distance():
    # Perpendicular foot lands inside the segment (above the midpoint), so the
    # result is the straight perpendicular distance, not a clamped endpoint.
    dist = _min_dist_pt_to_segment(5.0, 3.0, 0.0, 0.0, 10.0, 0.0)
    assert dist == pytest.approx(3.0)
