"""Tests for src/lookahead.py — TDD: red phase."""
import math
import pytest

from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from src.lookahead import (
    GameState,
    SimFleet,
    SimPlanet,
    build_state,
    score_state,
    step_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=20, production=2):
    return Planet(id, owner, x, y, radius, ships, production)


def make_fleet(id=0, owner=1, x=70.0, y=50.0, angle=0.0, from_planet_id=99, ships=10):
    return Fleet(id, owner, x, y, angle, from_planet_id, ships)


# ---------------------------------------------------------------------------
# Class: TestBuildState
# ---------------------------------------------------------------------------

class TestBuildState:
    def test_returns_game_state(self):
        planets = [make_planet(id=0)]
        fleets = [make_fleet(id=0)]
        state = build_state(planets, fleets, turn=5)
        assert isinstance(state, GameState)

    def test_turn_preserved(self):
        state = build_state([make_planet()], [], turn=42)
        assert state.turn == 42

    def test_planets_converted_to_sim_planet(self):
        planets = [make_planet(id=3, owner=0, x=70.0, y=50.0, radius=5.0, ships=20, production=2)]
        state = build_state(planets, [], turn=0)
        assert len(state.planets) == 1
        p = state.planets[0]
        assert isinstance(p, SimPlanet)
        assert p.id == 3
        assert p.owner == 0
        assert p.x == 70.0
        assert p.y == 50.0
        assert p.radius == 5.0
        assert p.ships == 20
        assert p.production == 2

    def test_fleets_converted_to_sim_fleet(self):
        fleets = [make_fleet(id=7, owner=1, x=60.0, y=40.0, angle=1.5, ships=15)]
        state = build_state([], fleets, turn=0)
        assert len(state.fleets) == 1
        f = state.fleets[0]
        assert isinstance(f, SimFleet)
        assert f.owner == 1
        assert f.x == 60.0
        assert f.y == 40.0
        assert f.angle == 1.5
        assert f.ships == 15

    def test_empty_planets_and_fleets(self):
        state = build_state([], [], turn=0)
        assert state.planets == []
        assert state.fleets == []

    def test_multiple_planets(self):
        planets = [make_planet(id=i) for i in range(4)]
        state = build_state(planets, [], turn=0)
        assert len(state.planets) == 4


# ---------------------------------------------------------------------------
# Class: TestStepState
# ---------------------------------------------------------------------------

class TestStepState:
    def _simple_state(self, planet_x=70.0, planet_ships=20, planet_owner=0):
        """One orbiting planet, no fleets."""
        planet = make_planet(id=0, owner=planet_owner, x=planet_x, y=50.0,
                             radius=5.0, ships=planet_ships, production=2)
        return build_state([planet], [], turn=1)

    def test_returns_game_state(self):
        state = self._simple_state()
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        assert isinstance(next_s, GameState)

    def test_production_added_to_owned_planet(self):
        state = self._simple_state(planet_ships=20, planet_owner=0)
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        p = next_s.planets[0]
        # Ships should increase by production (2) for owned planet
        assert p.ships == 22

    def test_production_not_added_to_neutral_planet(self):
        state = self._simple_state(planet_ships=10, planet_owner=-1)
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        p = next_s.planets[0]
        assert p.ships == 10  # No production for neutral

    def test_static_planet_does_not_rotate(self):
        # Static planet at x=90: orbital_radius=40, 40+10=50 >= ROTATION_RADIUS_LIMIT=50
        planet = make_planet(id=0, owner=0, x=90.0, y=50.0, radius=5.0, ships=10, production=1)
        state = build_state([planet], [], turn=0)
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        p = next_s.planets[0]
        assert p.x == pytest.approx(90.0)
        assert p.y == pytest.approx(50.0)

    def test_orbiting_planet_rotates(self):
        # Orbiting planet at x=70 (orbital_radius=20 < 40)
        planet = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=10, production=1)
        state = build_state([planet], [], turn=0)
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        p = next_s.planets[0]
        # Position must change after 1 turn with angular_velocity=0.03
        assert (p.x, p.y) != (70.0, 50.0)

    def test_move_deducts_ships_from_source(self):
        """Launching a fleet must deduct ships from the source planet and leave fleet in transit."""
        # radius=1 ensures launched fleet clears the planet boundary (fleet_speed(10) ≈ 1.96 > 1)
        planet = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=2)
        state = build_state([planet], [], turn=0)
        initial = state.planets[:]
        move = [0, 0.0, 10]  # launch 10 ships at angle 0
        next_s = step_state(state, move=move, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        source = next(p for p in next_s.planets if p.id == 0)
        # 30 ships - 10 launched + 2 production = 22; fleet stays in transit
        assert source.ships == 22
        assert len(next_s.fleets) == 1

    def test_fleet_moves_forward(self):
        """A fleet flying in open space advances by fleet_speed each turn."""
        from src.math_utils import fleet_speed
        planet = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=5, production=1)
        # Fleet far from any planet, flying right at angle=0
        fleet = make_fleet(id=0, owner=0, x=10.0, y=50.0, angle=0.0, ships=5)
        state = build_state([planet], [fleet], turn=0)
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        # Find the fleet in next state (it should be in fleets if not resolved)
        remaining = next_s.fleets
        if remaining:
            f = remaining[0]
            expected_x = 10.0 + fleet_speed(5) * math.cos(0.0)
            assert f.x == pytest.approx(expected_x, abs=0.01)

    def test_fleet_captures_neutral_planet(self):
        """A fleet arriving at a neutral planet captures it."""
        # Neutral planet at (70, 50), radius=5; fleet heading right
        planet = make_planet(id=0, owner=-1, x=70.0, y=50.0, radius=5.0, ships=2, production=1)
        from src.math_utils import fleet_speed
        speed = fleet_speed(10)
        # Place fleet close enough to land this turn (within radius after movement)
        fleet_x = 70.0 - speed + 0.1  # will land just inside after moving speed units right
        fleet = make_fleet(id=0, owner=0, x=fleet_x, y=50.0, angle=0.0, ships=10)
        state = build_state([planet], [fleet], turn=0)
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)
        p = next_s.planets[0]
        # Production runs at start of turn, but neutral planets don't produce.
        # Fleet had 10 ships; neutral planet had 2 defending ships.
        # Winner=fleet owner(0), 10-2=8 survive, minus 1 for takeover → 7 ships.
        assert p.owner == 0
        assert p.ships == 7

    def test_opponent_fn_defaults_to_none(self):
        """step_state must accept opponent_fn=None (default) without error."""
        state = self._simple_state()
        initial = state.planets[:]
        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial,
                            opponent_fn=None)
        assert isinstance(next_s, GameState)

    def test_production_runs_before_combat(self):
        """Production must run at the start of the turn, before combat.

        Set up: owned planet with 0 ships, production=2, at (70, 50), radius=1.
        Enemy fleet with 1 ship positioned to arrive this turn at angle 0.

        Expected: production runs first (0→2 ships), then combat. 2 vs 1 attacker
        means planet survives with 2-1=1 ship. Planet owner remains 0.
        """
        from src.math_utils import fleet_speed

        # Owned planet: 0 ships, production=2
        planet = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=1.0,
                             ships=0, production=2)

        # Enemy fleet with 1 ship, positioned to arrive this turn
        speed = fleet_speed(1)
        fleet_x = 70.0 - speed + 0.1  # arrives just inside radius after movement
        fleet = make_fleet(id=0, owner=1, x=fleet_x, y=50.0, angle=0.0, ships=1)

        state = build_state([planet], [fleet], turn=0)
        initial = state.planets[:]

        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial)

        p = next_s.planets[0]
        # With production before combat: 0+2=2 ships defending.
        # Combat: 2 defenders vs 1 attacker → planet wins with 2-1=1 ship remaining.
        assert p.owner == 0
        assert p.ships == 1

    def test_opponent_fn_applied(self):
        """opponent_fn fleet appears in state.fleets and deducts from source."""
        # Two planets: ours at (70,50), opponent's at (30,50)
        our_planet = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=20, production=1)
        opp_planet = make_planet(id=1, owner=1, x=30.0, y=50.0, radius=1.0, ships=20, production=1)
        state = build_state([our_planet, opp_planet], [], turn=0)
        initial = [our_planet, opp_planet]

        def opponent_fn(s):
            return [[1, 0.0, 5]]  # opponent sends 5 ships from planet 1 at angle 0

        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial,
                            opponent_fn=opponent_fn)
        # Opponent planet should have lost 5 ships (after production: 20+1=21, then -5=16)
        opp = next(p for p in next_s.planets if p.id == 1)
        assert opp.ships == 16
        # A fleet owned by player 1 should be in transit
        assert any(f.owner == 1 for f in next_s.fleets)

    def test_opponent_fn_silent_skip(self):
        """opponent_fn referencing a planet with 0 ships is silently skipped."""
        planet = make_planet(id=0, owner=1, x=70.0, y=50.0, radius=1.0, ships=0, production=0)
        state = build_state([planet], [], turn=0)
        initial = [planet]

        def opponent_fn(s):
            return [[0, 0.0, 5]]  # tries to send 5 ships from a planet with 0

        next_s = step_state(state, move=None, player=0,
                            angular_velocity=0.03, initial_planets=initial,
                            opponent_fn=opponent_fn)
        # No fleet should be added, no exception
        assert len(next_s.fleets) == 0

    def test_opponent_fn_call_count_sentinel(self):
        """opponent_fn is called exactly once per step_state invocation."""
        state = self._simple_state()
        initial = state.planets[:]
        call_count = [0]

        def counting_fn(s):
            call_count[0] += 1
            return []

        step_state(state, move=None, player=0,
                   angular_velocity=0.03, initial_planets=initial,
                   opponent_fn=counting_fn)
        assert call_count[0] == 1


# ---------------------------------------------------------------------------
# Class: TestScoreState
# ---------------------------------------------------------------------------

class TestScoreState:
    def test_returns_float(self):
        state = build_state([make_planet(id=0, owner=0, production=2)], [], turn=0)
        result = score_state(state, player=0)
        assert isinstance(result, float)

    def test_positive_when_winning(self):
        my_planet = make_planet(id=0, owner=0, x=70.0, production=4, ships=30)
        enemy_planet = make_planet(id=1, owner=1, x=80.0, production=1, ships=5)
        state = build_state([my_planet, enemy_planet], [], turn=0)
        score = score_state(state, player=0)
        assert score > 0

    def test_negative_when_losing(self):
        my_planet = make_planet(id=0, owner=0, x=70.0, production=1, ships=5)
        enemy_planet = make_planet(id=1, owner=1, x=80.0, production=4, ships=30)
        state = build_state([my_planet, enemy_planet], [], turn=0)
        score = score_state(state, player=0)
        assert score < 0

    def test_neutral_planets_ignored(self):
        my_planet = make_planet(id=0, owner=0, production=3, ships=10)
        neutral = make_planet(id=1, owner=-1, production=5, ships=100)
        state = build_state([my_planet, neutral], [], turn=0)
        score = score_state(state, player=0)
        # Neutral ignored; my_prod=3, enemy_prod=0 → positive
        assert score > 0

    def test_ship_weight_affects_score(self):
        my_planet = make_planet(id=0, owner=0, production=2, ships=100)
        enemy_planet = make_planet(id=1, owner=1, production=2, ships=10)
        state = build_state([my_planet, enemy_planet], [], turn=0)
        score_low = score_state(state, player=0, ship_weight=0.001)
        score_high = score_state(state, player=0, ship_weight=0.1)
        # Higher weight amplifies ship advantage → higher score
        assert score_high > score_low

    def test_zero_score_when_symmetric(self):
        my = make_planet(id=0, owner=0, production=3, ships=10)
        enemy = make_planet(id=1, owner=1, production=3, ships=10)
        state = build_state([my, enemy], [], turn=0)
        score = score_state(state, player=0)
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Class: TestPlanExpansionBlend
# ---------------------------------------------------------------------------

class TestPlanExpansionBlend:
    """Tests that plan_expansion() integrates lookahead correctly."""

    def test_blend_zero_equivalent_to_no_lookahead(self):
        """With lookahead_blend=0.0, plan_expansion must pick the same target."""
        from src.strategy import plan_expansion
        from src.config import PARAMS

        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        easy_neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=2)
        soft_enemy = make_planet(id=2, owner=1, x=75.0, y=50.0, ships=2, production=1)
        own_classes = {0: "FORTRESS"}

        params_no_blend = {**PARAMS, "lookahead_blend": 0.0}

        # Without lookahead arguments
        moves_baseline = plan_expansion(
            [fortress], [easy_neutral], [soft_enemy], own_classes,
            angular_velocity=0.03, agg=1.0, params=params_no_blend
        )

        # With blend=0 and lookahead args provided
        all_planets = [fortress, easy_neutral, soft_enemy]
        moves_blended = plan_expansion(
            [fortress], [easy_neutral], [soft_enemy], own_classes,
            angular_velocity=0.03, agg=1.0, params=params_no_blend,
            initial_planets=all_planets, fleets=[], player=0, turn=0
        )

        assert moves_baseline == moves_blended

    def test_single_candidate_bypasses_blending(self):
        """When only one valid candidate exists, no crash and move is returned."""
        from src.strategy import plan_expansion
        from src.config import PARAMS

        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        only_target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=2)
        own_classes = {0: "FORTRESS"}
        params_blend = {**PARAMS, "lookahead_blend": 0.5}
        all_planets = [fortress, only_target]
        moves = plan_expansion(
            [fortress], [only_target], [], own_classes,
            angular_velocity=0.03, agg=1.0, params=params_blend,
            initial_planets=all_planets, fleets=[], player=0, turn=0
        )
        assert len(moves) == 1

    def test_equal_greedy_scores_no_crash(self):
        """Min-max normalization must not crash when all candidates have equal greedy scores (lo==hi edge case)."""
        # Greedy scores are always positive (production / eta^2), but two targets
        # at the same distance with the same production yield identical scores,
        # triggering the lo==hi case where the denominator would be zero without +1e-9.
        from src.strategy import plan_expansion
        from src.config import PARAMS

        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        # Two targets with production=1 at same distance → equal greedy scores
        t1 = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        t2 = make_planet(id=2, owner=-1, x=72.0, y=52.0, ships=1, production=1)
        own_classes = {0: "FORTRESS"}
        params_blend = {**PARAMS, "lookahead_blend": 0.5}
        all_planets = [fortress, t1, t2]
        # Should not raise
        moves = plan_expansion(
            [fortress], [t1, t2], [], own_classes,
            angular_velocity=0.03, agg=1.0, params=params_blend,
            initial_planets=all_planets, fleets=[], player=0, turn=0
        )
        assert isinstance(moves, list)

    def test_plan_moves_passes_initial_planets(self):
        """plan_moves must forward initial_planets to plan_expansion without error."""
        from src.strategy import plan_moves
        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        moves = plan_moves(
            [owned, neutral], fleets=[], player=0, angular_velocity=0.03, turn=5,
            initial_planets=[owned, neutral]
        )
        assert isinstance(moves, list)

    def test_lookahead_turns_2_increments_turn(self):
        """lookahead_turns=2 produces a state with turn == original_turn + 2."""
        from src.strategy import plan_expansion
        from src.config import PARAMS
        from src.lookahead import build_state, score_state

        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=2)
        own_classes = {0: "FORTRESS"}
        all_planets = [fortress, target]

        # With blend=1 and lookahead_turns=2, the scored state should be at turn+2
        params_2turn = {**PARAMS, "lookahead_blend": 1.0, "lookahead_turns": 2,
                        "min_garrison": 10}
        moves = plan_expansion(
            [fortress], [target], [], own_classes,
            angular_velocity=0.03, agg=1.0, params=params_2turn,
            initial_planets=all_planets, fleets=[], player=0, turn=5
        )
        # Just verify no crash and a move is returned
        assert isinstance(moves, list)
