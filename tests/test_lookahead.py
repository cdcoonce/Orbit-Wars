"""Tests for src/lookahead.py — TDD: red phase."""

import copy
import math
import pytest

from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from src.lookahead import (
    GameState,
    SimFleet,
    SimPlanet,
    _resolve_combat,
    build_state,
    score_state,
    step_state,
    step_state_multi,
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
        planets = [
            make_planet(
                id=3, owner=0, x=70.0, y=50.0, radius=5.0, ships=20, production=2
            )
        ]
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
        planet = make_planet(
            id=0,
            owner=planet_owner,
            x=planet_x,
            y=50.0,
            radius=5.0,
            ships=planet_ships,
            production=2,
        )
        return build_state([planet], [], turn=1)

    def test_returns_game_state(self):
        state = self._simple_state()
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        assert isinstance(next_s, GameState)

    def test_production_added_to_owned_planet(self):
        state = self._simple_state(planet_ships=20, planet_owner=0)
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        p = next_s.planets[0]
        # Ships should increase by production (2) for owned planet
        assert p.ships == 22

    def test_production_not_added_to_neutral_planet(self):
        state = self._simple_state(planet_ships=10, planet_owner=-1)
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        p = next_s.planets[0]
        assert p.ships == 10  # No production for neutral

    def test_static_planet_does_not_rotate(self):
        # Static planet at x=90: orbital_radius=40, 40+10=50 >= ROTATION_RADIUS_LIMIT=50
        planet = make_planet(
            id=0, owner=0, x=90.0, y=50.0, radius=5.0, ships=10, production=1
        )
        state = build_state([planet], [], turn=0)
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        p = next_s.planets[0]
        assert p.x == pytest.approx(90.0)
        assert p.y == pytest.approx(50.0)

    def test_orbiting_planet_rotates(self):
        # Orbiting planet at x=70 (orbital_radius=20 < 40)
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=10, production=1
        )
        state = build_state([planet], [], turn=0)
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        p = next_s.planets[0]
        # Position must change after 1 turn with angular_velocity=0.03
        assert (p.x, p.y) != (70.0, 50.0)

    def test_move_deducts_ships_from_source(self):
        """Launching a fleet must deduct ships from the source planet and leave fleet in transit."""
        # radius=1 ensures launched fleet clears the planet boundary (fleet_speed(10) ≈ 1.96 > 1)
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=2
        )
        state = build_state([planet], [], turn=0)
        move = [0, 0.0, 10]  # launch 10 ships at angle 0
        next_s = step_state(state, move=move, player=0, angular_velocity=0.03)
        source = next(p for p in next_s.planets if p.id == 0)
        # 30 ships - 10 launched + 2 production = 22; fleet stays in transit
        assert source.ships == 22
        assert len(next_s.fleets) == 1

    def test_sim_spawned_fleet_id_sentinel_does_not_collide_with_neutral_owner(self):
        """A sim-spawned fleet's default id must not equal -1, the neutral-owner sentinel."""
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=2
        )
        state = build_state([planet], [], turn=0)
        move = [0, 0.0, 10]
        next_s = step_state(state, move=move, player=0, angular_velocity=0.03)
        assert len(next_s.fleets) == 1
        assert next_s.fleets[0].id != -1

    def test_slow_fleet_stays_in_transit_after_launch(self):
        """Slow fleet (fleet_speed < source.radius) must not re-land on the origin planet.

        Without the spawn-offset fix the fleet starts at the planet center and
        after one move step (fleet_speed ≈ 1.56) is still inside the source
        radius (5.0), so step-5 incorrectly lands it back and the launch
        becomes a silent no-op.  With the fix the fleet is spawned at
        source.radius + 0.1 along the launch angle, clearing the boundary.
        """
        from src.math_utils import fleet_speed

        ships_to_send = 5
        source_radius = 5.0
        assert fleet_speed(ships_to_send) < source_radius, (
            "precondition: fleet speed must be less than source radius"
        )

        source = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=source_radius, ships=30, production=2
        )
        # Far target — fleet must not reach it in one step either
        target = make_planet(
            id=1, owner=-1, x=200.0, y=50.0, radius=5.0, ships=0, production=0
        )
        state = build_state([source, target], [], turn=0)
        move = [0, 0.0, ships_to_send]  # launch slow fleet rightward
        next_s = step_state(state, move=move, player=0, angular_velocity=0.0)

        src = next(p for p in next_s.planets if p.id == 0)
        # 30 - 5 launched + 2 production = 27; fleet must remain in transit
        assert src.ships == 27
        assert len(next_s.fleets) == 1, (
            "slow fleet must stay in transit, not re-land on source planet"
        )

    def test_fleet_moves_forward(self):
        """A fleet flying in open space advances by fleet_speed each turn."""
        from src.math_utils import fleet_speed

        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=5, production=1
        )
        # Fleet far from any planet, flying right at angle=0
        fleet = make_fleet(id=0, owner=0, x=10.0, y=50.0, angle=0.0, ships=5)
        state = build_state([planet], [fleet], turn=0)
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        # Find the fleet in next state (it should be in fleets if not resolved)
        remaining = next_s.fleets
        if remaining:
            f = remaining[0]
            expected_x = 10.0 + fleet_speed(5) * math.cos(0.0)
            assert f.x == pytest.approx(expected_x, abs=0.01)

    def test_fleet_captures_neutral_planet(self):
        """A fleet arriving at a neutral planet captures it."""
        # Neutral planet at (70, 50), radius=5; fleet heading right
        planet = make_planet(
            id=0, owner=-1, x=70.0, y=50.0, radius=5.0, ships=2, production=1
        )
        from src.math_utils import fleet_speed

        speed = fleet_speed(10)
        # Place fleet close enough to land this turn (within radius after movement)
        fleet_x = (
            70.0 - speed + 0.1
        )  # will land just inside after moving speed units right
        fleet = make_fleet(id=0, owner=0, x=fleet_x, y=50.0, angle=0.0, ships=10)
        state = build_state([planet], [fleet], turn=0)
        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)
        p = next_s.planets[0]
        # Production runs at start of turn, but neutral planets don't produce.
        # Fleet had 10 ships; neutral planet had 2 defending ships.
        # Winner=fleet owner(0), 10-2=8 survive, minus 1 for takeover → 7 ships.
        assert p.owner == 0
        assert p.ships == 7

    def test_opponent_fn_defaults_to_none(self):
        """step_state must accept opponent_fn=None (default) without error."""
        state = self._simple_state()
        next_s = step_state(
            state, move=None, player=0, angular_velocity=0.03, opponent_fn=None
        )
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
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=0, production=2
        )

        # Enemy fleet with 1 ship, positioned to arrive this turn
        speed = fleet_speed(1)
        fleet_x = 70.0 - speed + 0.1  # arrives just inside radius after movement
        fleet = make_fleet(id=0, owner=1, x=fleet_x, y=50.0, angle=0.0, ships=1)

        state = build_state([planet], [fleet], turn=0)

        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)

        p = next_s.planets[0]
        # With production before combat: 0+2=2 ships defending.
        # Combat: 2 defenders vs 1 attacker → planet wins with 2-1=1 ship remaining.
        assert p.owner == 0
        assert p.ships == 1

    def test_opponent_fn_applied(self):
        """opponent_fn fleet appears in state.fleets and deducts from source."""
        # Two planets: ours at (70,50), opponent's at (30,50)
        our_planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=20, production=1
        )
        opp_planet = make_planet(
            id=1, owner=1, x=30.0, y=50.0, radius=1.0, ships=20, production=1
        )
        state = build_state([our_planet, opp_planet], [], turn=0)

        def opponent_fn(s):
            return [[1, 0.0, 5]]  # opponent sends 5 ships from planet 1 at angle 0

        next_s = step_state(
            state, move=None, player=0, angular_velocity=0.03, opponent_fn=opponent_fn
        )
        # Opponent planet should have lost 5 ships (after production: 20+1=21, then -5=16)
        opp = next(p for p in next_s.planets if p.id == 1)
        assert opp.ships == 16
        # A fleet owned by player 1 should be in transit
        assert any(f.owner == 1 for f in next_s.fleets)

    def test_opponent_fn_silent_skip(self):
        """opponent_fn referencing a planet with 0 ships is silently skipped."""
        planet = make_planet(
            id=0, owner=1, x=70.0, y=50.0, radius=1.0, ships=0, production=0
        )
        state = build_state([planet], [], turn=0)

        def opponent_fn(s):
            return [[0, 0.0, 5]]  # tries to send 5 ships from a planet with 0

        next_s = step_state(
            state, move=None, player=0, angular_velocity=0.03, opponent_fn=opponent_fn
        )
        # No fleet should be added, no exception
        assert len(next_s.fleets) == 0

    def test_own_move_insufficient_ships_no_fleet_no_deduction(self):
        """Own move requesting more ships than available at launch time is silently skipped.

        Launch now runs before production (matching the engine's step order), so
        the guard checks the source's PRE-production ship count. Source starts at
        10 ships, production=3. Move requests 14 (> 10 pre-production) → guard
        fires, no fleet spawned, no deduction. Production still runs afterward,
        so the final total is 10 + 3 = 13.
        """
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=10, production=3
        )
        state = build_state([planet], [], turn=0)
        move = [0, 0.0, 14]  # request 14 ships; only 10 available pre-production
        next_s = step_state(state, move=move, player=0, angular_velocity=0.03)

        source = next(p for p in next_s.planets if p.id == 0)
        assert len(next_s.fleets) == 0
        assert source.ships == 13  # 10 + 3 production; no deduction because guard fired

    def test_opponent_fn_insufficient_ships_no_fleet_no_deduction(self):
        """opponent_fn move requesting more ships than available at launch time is silently skipped.

        Launch now runs before production (matching the engine's step order), so
        the guard checks the source's PRE-production ship count. Opponent source
        starts at 10 ships, production=3. opponent_fn requests 14 (> 10
        pre-production) → guard fires, no opponent fleet spawned, no deduction.
        Production still runs afterward, so the final total is 10 + 3 = 13.
        """
        opp_planet = make_planet(
            id=0, owner=1, x=70.0, y=50.0, radius=1.0, ships=10, production=3
        )
        state = build_state([opp_planet], [], turn=0)

        def opponent_fn(s):
            return [[0, 0.0, 14]]  # request 14 ships; only 10 available pre-production

        next_s = step_state(
            state, move=None, player=0, angular_velocity=0.03, opponent_fn=opponent_fn
        )

        opp_source = next(p for p in next_s.planets if p.id == 0)
        assert len(next_s.fleets) == 0
        assert opp_source.ships == 13  # 10 + 3 production; no deduction because guard fired

    def test_opponent_fn_call_count_sentinel(self):
        """opponent_fn is called exactly once per step_state invocation."""
        state = self._simple_state()
        call_count = [0]

        def counting_fn(s):
            call_count[0] += 1
            return []

        step_state(
            state, move=None, player=0, angular_velocity=0.03, opponent_fn=counting_fn
        )
        assert call_count[0] == 1

    def test_exact_tie_keeps_owned_planet(self):
        """A defended owned planet that exactly ties an attack stays owned.

        Set up: owned planet (owner=0) with 0 ships and production=2, so it
        defends with 2 ships after production. Enemy fleet with exactly 2 ships
        arrives this turn → 2 vs 2 tie. Ties break to the current owner, so the
        planet must stay owner=0 (with 0 ships left), not fall to neutral.
        """
        from src.math_utils import fleet_speed

        # Owned planet: 0 ships, production=2 → 2 defenders after production
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=0, production=2
        )

        # Enemy fleet with 2 ships, positioned to arrive this turn
        speed = fleet_speed(2)
        fleet_x = 70.0 - speed + 0.1  # arrives just inside radius after movement
        fleet = make_fleet(id=0, owner=1, x=fleet_x, y=50.0, angle=0.0, ships=2)

        state = build_state([planet], [fleet], turn=0)

        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)

        p = next_s.planets[0]
        # Exact tie (2 vs 2) breaks to the incumbent owner: planet held, 0 ships.
        assert p.owner == 0
        assert p.ships == 0

    def test_exact_tie_keeps_neutral_planet_neutral(self):
        """A neutral planet that exactly ties an attack stays neutral.

        Neutral planets (owner=-1) don't produce, so a planet with 2 ships
        ties an attacker with 2 ships → 2 vs 2. The neutral defender wins the
        tie-break but has no incumbent player, so the planet stays neutral
        with 0 ships (unchanged from existing behavior).
        """
        from src.math_utils import fleet_speed

        # Neutral planet with 2 defending ships
        planet = make_planet(
            id=0, owner=-1, x=70.0, y=50.0, radius=1.0, ships=2, production=1
        )

        # Attacker fleet with 2 ships, positioned to arrive this turn
        speed = fleet_speed(2)
        fleet_x = 70.0 - speed + 0.1  # arrives just inside radius after movement
        fleet = make_fleet(id=0, owner=0, x=fleet_x, y=50.0, angle=0.0, ships=2)

        state = build_state([planet], [fleet], turn=0)

        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)

        p = next_s.planets[0]
        # Tie on a neutral planet: stays neutral with 0 ships.
        assert p.owner == -1
        assert p.ships == 0

    def test_launch_uses_pre_rotation_position_for_orbiting_source(self):
        """Launch must fire from the source planet's PRE-rotation position, matching
        the engine's step order (Fleet Launch happens before Planet Movement & Sweep
        in orbit_wars.py's interpreter). The simulator previously rotated the planet
        first, so the spawned fleet started from a point the engine would never use.
        """
        from kaggle_environments.envs.orbit_wars.orbit_wars import (
            ROTATION_RADIUS_LIMIT,
            SUN_RADIUS,
        )
        from src.math_utils import fleet_speed, orbital_radius, predict_planet_position

        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=30, production=2
        )
        assert orbital_radius(planet) + SUN_RADIUS < ROTATION_RADIUS_LIMIT, (
            "precondition: source planet must be orbiting (not stationary)"
        )
        orig_x, orig_y = planet.x, planet.y

        angular_velocity = 0.05
        rot_x, rot_y = predict_planet_position(planet, angular_velocity, 1)
        assert (rot_x, rot_y) != (orig_x, orig_y), (
            "precondition: the source planet must actually move this turn"
        )

        state = build_state([planet], [], turn=0)
        angle = 0.7
        ships = 10
        move = [0, angle, ships]
        next_s = step_state(
            state, move=move, player=0, angular_velocity=angular_velocity
        )

        assert len(next_s.fleets) == 1
        fleet = next_s.fleets[0]
        # step_state also advances the fleet this turn (the engine's Fleet
        # Movement follows Fleet Launch), so back that movement out to recover
        # the spawn point process_moves would have produced.
        speed = fleet_speed(ships)
        spawn_x = fleet.x - speed * math.cos(angle)
        spawn_y = fleet.y - speed * math.sin(angle)

        # Engine formula: from_planet[2] + cos(angle) * (from_planet[4] + 0.1)
        offset = planet.radius + 0.1
        assert spawn_x == pytest.approx(orig_x + math.cos(angle) * offset)
        assert spawn_y == pytest.approx(orig_y + math.sin(angle) * offset)

        # And NOT the post-rotation position the old ordering used.
        assert spawn_x != pytest.approx(rot_x + math.cos(angle) * offset)
        assert spawn_y != pytest.approx(rot_y + math.sin(angle) * offset)

    def test_incumbent_largest_stack_but_loses_to_combined_attackers(self):
        """Multi-party: the incumbent is the largest SINGLE stack yet loses to
        the COMBINED attackers (surviving < 0) → the planet goes neutral.

        owner=0 holds 10 ships; owner=1 and owner=2 each send 6 (combined 12 >
        10). The winner-by-largest-single-stack is owner 0, but surviving =
        10 - 12 = -2, so no one holds the planet. It must NOT be retained by the
        incumbent (the bug: an `elif winner == planet.owner` that fired on
        surviving < 0); it falls to neutral.
        """
        from src.math_utils import fleet_speed

        # Incumbent owned planet: 10 ships, production=0 → exactly 10 defenders.
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=10, production=0
        )

        # Two attackers from DIFFERENT owners, each 6 ships, arriving this turn.
        speed = fleet_speed(6)
        fleet_x = 70.0 - speed + 0.1
        f1 = make_fleet(id=0, owner=1, x=fleet_x, y=50.0, angle=0.0, ships=6)
        f2 = make_fleet(id=1, owner=2, x=fleet_x, y=50.0, angle=0.0, ships=6)

        state = build_state([planet], [f1, f2], turn=0)

        next_s = step_state(state, move=None, player=0, angular_velocity=0.03)

        p = next_s.planets[0]
        # Largest single stack (10) loses to combined 6+6=12 → neutral, 0 ships.
        assert p.owner == -1
        assert p.ships == 0


# ---------------------------------------------------------------------------
# Class: TestResolveCombat — direct unit tests for the extracted helper
# ---------------------------------------------------------------------------


class TestResolveCombat:
    """Direct unit tests for _resolve_combat — one test per branch."""

    def _planet(self, owner=0, ships=10):
        return SimPlanet(
            id=0, owner=owner, x=0.0, y=0.0, radius=5.0, ships=ships, production=2
        )

    def _fleet(self, owner=1, ships=5):
        return SimFleet(owner=owner, x=0.0, y=0.0, angle=0.0, ships=ships)

    def test_new_owner_with_foothold_cost(self):
        """Attacker wins: new owner takes planet with surviving - 1 ships (foothold cost)."""
        planet = self._planet(owner=0, ships=5)
        arrivals = [self._fleet(owner=1, ships=10)]
        _resolve_combat(planet, arrivals)
        assert planet.owner == 1
        assert planet.ships == 4  # surviving = 10 - 5 = 5, minus 1 foothold cost

    def test_defender_holds(self):
        """Defender wins: planet owner unchanged, surviving ships remain."""
        planet = self._planet(owner=0, ships=10)
        arrivals = [self._fleet(owner=1, ships=5)]
        _resolve_combat(planet, arrivals)
        assert planet.owner == 0
        assert planet.ships == 5  # surviving = 10 - 5 = 5

    def test_exact_tie_incumbent_holds(self):
        """Exact tie (surviving == 0) breaks to incumbent; planet held with 0 ships."""
        planet = self._planet(owner=0, ships=5)
        arrivals = [self._fleet(owner=1, ships=5)]
        _resolve_combat(planet, arrivals)
        assert planet.owner == 0
        assert planet.ships == 0

    def test_combined_attackers_win_goes_neutral(self):
        """Largest single stack (incumbent) loses to combined attackers → neutral."""
        planet = self._planet(owner=0, ships=10)
        arrivals = [
            self._fleet(owner=1, ships=6),
            self._fleet(owner=2, ships=6),
        ]
        _resolve_combat(planet, arrivals)
        # Incumbent (10) loses to combined 6+6=12 → neutral with 0 ships
        assert planet.owner == -1
        assert planet.ships == 0

    def test_multi_party_attacker_wins_total_others_aggregates_all_losers(self):
        """Multi-party surviving > 0, non-incumbent winner: total_others must sum
        BOTH the incumbent garrison AND the rival attacker — not just one of them.

        owner=0 holds 3 ships; owner=1 sends 10; owner=2 sends 5.
        winner=1 (10), total_others = 3 + 5 = 8, surviving = 2 > 0.
        Planet goes to owner=1 with surviving - 1 = 1 ship (foothold cost).
        A 1v1 reading (total_others = 3 only) would yield surviving = 7 → 6 ships,
        proving the aggregation across all losers is exercised by the chosen numbers.
        """
        planet = self._planet(owner=0, ships=3)
        arrivals = [
            self._fleet(owner=1, ships=10),
            self._fleet(owner=2, ships=5),
        ]
        _resolve_combat(planet, arrivals)
        assert planet.owner == 1
        assert planet.ships == 1  # surviving = 10 - (3 + 5) = 2, minus 1 foothold cost

    def test_two_equal_non_incumbent_attackers_on_neutral_stays_neutral(self):
        """Two non-incumbent attackers tie for the largest stack on a neutral
        planet: the arbitrary tie-break picks one of them as `winner`, but
        surviving == 0 and winner != planet.owner (-1), so the planet must
        fall through to the neutral branch rather than be retained.
        """
        planet = self._planet(owner=-1, ships=0)
        arrivals = [
            self._fleet(owner=1, ships=6),
            self._fleet(owner=2, ships=6),
        ]
        _resolve_combat(planet, arrivals)
        assert planet.owner == -1
        assert planet.ships == 0

    def test_two_equal_attackers_beat_smaller_incumbent_goes_neutral(self):
        """Two equal non-incumbent attackers combine to push a smaller
        incumbent garrison to surviving < 0: the planet must go neutral,
        not be retained by the incumbent.

        owner=0 holds 5 ships; owners 1 and 2 each send 6 (combined 12 > 5).
        winner is one of the two equal attackers, total_others = 5 + 6 = 11,
        surviving = 6 - 11 = -5 < 0 → neutral, 0 ships.
        """
        planet = self._planet(owner=0, ships=5)
        arrivals = [
            self._fleet(owner=1, ships=6),
            self._fleet(owner=2, ships=6),
        ]
        _resolve_combat(planet, arrivals)
        assert planet.owner == -1
        assert planet.ships == 0


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

    def test_owned_in_transit_fleet_raises_score(self):
        my_planet = make_planet(id=0, owner=0, production=2, ships=10)
        enemy_planet = make_planet(id=1, owner=1, production=2, ships=10)
        my_fleet = make_fleet(id=0, owner=0, ships=8)
        state_without_fleet = build_state([my_planet, enemy_planet], [], turn=0)
        state_with_fleet = build_state(
            [my_planet, enemy_planet], [my_fleet], turn=0
        )
        score_without = score_state(state_without_fleet, player=0, ship_weight=0.1)
        score_with = score_state(state_with_fleet, player=0, ship_weight=0.1)
        assert score_with > score_without

    def test_enemy_in_transit_fleet_lowers_score_symmetrically(self):
        my_planet = make_planet(id=0, owner=0, production=2, ships=10)
        enemy_planet = make_planet(id=1, owner=1, production=2, ships=10)
        enemy_fleet = make_fleet(id=0, owner=1, ships=8)
        state_without_fleet = build_state([my_planet, enemy_planet], [], turn=0)
        state_with_fleet = build_state(
            [my_planet, enemy_planet], [enemy_fleet], turn=0
        )
        score_without = score_state(state_without_fleet, player=0, ship_weight=0.1)
        score_with = score_state(state_with_fleet, player=0, ship_weight=0.1)
        assert score_without - score_with == pytest.approx(0.1 * 8)


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
        easy_neutral = make_planet(
            id=1, owner=-1, x=72.0, y=50.0, ships=1, production=2
        )
        soft_enemy = make_planet(id=2, owner=1, x=75.0, y=50.0, ships=2, production=1)
        own_classes = {0: "FORTRESS"}

        params_no_blend = {**PARAMS, "lookahead_blend": 0.0}

        # Without lookahead arguments
        moves_baseline = plan_expansion(
            [fortress],
            [easy_neutral],
            [soft_enemy],
            own_classes,
            angular_velocity=0.03,
            agg=1.0,
            params=params_no_blend,
        )

        # With blend=0 and lookahead args provided
        all_planets = [fortress, easy_neutral, soft_enemy]
        moves_blended = plan_expansion(
            [fortress],
            [easy_neutral],
            [soft_enemy],
            own_classes,
            angular_velocity=0.03,
            agg=1.0,
            params=params_no_blend,
            initial_planets=all_planets,
            fleets=[],
            player=0,
            turn=0,
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
            [fortress],
            [only_target],
            [],
            own_classes,
            angular_velocity=0.03,
            agg=1.0,
            params=params_blend,
            initial_planets=all_planets,
            fleets=[],
            player=0,
            turn=0,
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
            [fortress],
            [t1, t2],
            [],
            own_classes,
            angular_velocity=0.03,
            agg=1.0,
            params=params_blend,
            initial_planets=all_planets,
            fleets=[],
            player=0,
            turn=0,
        )
        assert isinstance(moves, list)

    def test_plan_moves_passes_initial_planets(self):
        """plan_moves must forward initial_planets to plan_expansion without error."""
        from src.strategy import plan_moves

        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        moves = plan_moves(
            [owned, neutral],
            fleets=[],
            player=0,
            angular_velocity=0.03,
            turn=5,
            initial_planets=[owned, neutral],
        )
        assert isinstance(moves, list)

    def test_lookahead_turns_2_increments_turn(self):
        """lookahead_turns=2 scores differently from lookahead_turns=1 when turn 2 matters."""
        from src.strategy import plan_expansion
        from src.config import PARAMS
        from src.lookahead import build_state, score_state, step_state

        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=2)
        all_planets = [fortress, target]
        own_classes = {0: "FORTRESS"}

        # Build a state and manually run step_state twice to get turn=7 state
        state_1turn = build_state(all_planets, [], turn=5)
        state_1turn = step_state(state_1turn, None, 0, 0.03)
        score_after_1 = score_state(state_1turn, player=0)

        state_2turn = build_state(all_planets, [], turn=5)
        state_2turn = step_state(state_2turn, None, 0, 0.03)
        state_2turn = step_state(state_2turn, None, 0, 0.03)
        score_after_2 = score_state(state_2turn, player=0)

        # Scores must differ (production compounds — 2-turn score != 1-turn score)
        assert score_after_2 != score_after_1

        # Also verify plan_expansion with lookahead_turns=2 runs without crash
        params_2turn = {
            **PARAMS,
            "lookahead_blend": 1.0,
            "lookahead_turns": 2,
            "min_garrison": 10,
        }
        moves = plan_expansion(
            [fortress],
            [target],
            [],
            own_classes,
            angular_velocity=0.03,
            agg=1.0,
            params=params_2turn,
            initial_planets=all_planets,
            fleets=[],
            player=0,
            turn=5,
        )
        assert isinstance(moves, list)

    def test_lookahead_turns_2_with_in_transit_fleet(self):
        """lookahead_turns=2 with an in-transit fleet must not crash (SimFleet.id required)."""
        from src.strategy import plan_expansion
        from src.config import PARAMS

        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        target = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=2)
        all_planets = [fortress, target]
        own_classes = {0: "FORTRESS"}
        # Enemy fleet far away, stays in transit across both simulated turns
        in_transit = make_fleet(id=7, owner=1, x=10.0, y=50.0, angle=0.0, ships=3)

        params_2turn = {
            **PARAMS,
            "lookahead_blend": 1.0,
            "lookahead_turns": 2,
            "min_garrison": 10,
        }
        # This would crash with AttributeError before the SimFleet.id fix
        moves = plan_expansion(
            [fortress],
            [target],
            [],
            own_classes,
            angular_velocity=0.03,
            agg=1.0,
            params=params_2turn,
            initial_planets=all_planets,
            fleets=[in_transit],
            player=0,
            turn=5,
        )
        assert isinstance(moves, list)

    def test_opponent_fn_precomputed_once_per_call(self):
        """opponent plan_moves is computed once per plan_expansion CALL, not per source.

        The opponent's frozen response is loop-invariant (it depends only on
        initial_planets/fleets/turn/player, never on `source`), so it is hoisted
        above the `for source in owned:` loop. Setup: 2 source planets, 2 candidate
        targets => 4 (source, target) combinations; the opponent plan_moves must
        fire exactly ONCE total — not once per source (2) and not once per
        combination (4). This is the redundant-recompute fix from issue #49.
        """
        import src.strategy as strategy_module
        from src.strategy import plan_expansion
        from src.config import PARAMS

        # Two owned planets (sources)
        src1 = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        src2 = make_planet(id=1, owner=0, x=68.0, y=52.0, ships=60, production=4)
        # Two neutral targets (candidates)
        tgt1 = make_planet(id=2, owner=-1, x=72.0, y=50.0, ships=1, production=2)
        tgt2 = make_planet(id=3, owner=-1, x=72.0, y=52.0, ships=1, production=2)
        all_planets = [src1, src2, tgt1, tgt2]
        own_classes = {0: "FORTRESS", 1: "FORTRESS"}

        params_blend = {
            **PARAMS,
            "lookahead_blend": 1.0,
            "lookahead_turns": 1,
            "min_garrison": 10,
        }

        opponent_call_count = [0]
        original_plan_moves = strategy_module.plan_moves

        def counting_plan_moves(planets, fleets, player, angular_velocity, **kwargs):
            # Count calls where player is the opponent (player != 0)
            if player != 0:
                opponent_call_count[0] += 1
            return original_plan_moves(
                planets, fleets, player, angular_velocity, **kwargs
            )

        strategy_module.plan_moves = counting_plan_moves
        try:
            plan_expansion(
                [src1, src2],
                [tgt1, tgt2],
                [],
                own_classes,
                angular_velocity=0.03,
                agg=1.0,
                params=params_blend,
                comet_ids=frozenset(),
                initial_planets=all_planets,
                fleets=[],
                player=0,
                turn=0,
            )
        finally:
            strategy_module.plan_moves = original_plan_moves

        # With lookahead_turns=1, n_extra=0 so no extra plan_moves calls happen.
        # The opponent precomputation is hoisted above the source loop, so it fires
        # exactly ONCE per plan_expansion call — not 2 (per source) and not 4 (per pair).
        assert opponent_call_count[0] == 1, (
            f"Expected opponent plan_moves to be called once per plan_expansion call (1), "
            f"got {opponent_call_count[0]}"
        )

    def test_plan_expansion_blend_reduces_opponent_ships(self):
        """Criterion 8: blend=1.0 with enemy planet triggers opponent_fn, confirming
        the lookahead path was taken and the opponent model was active.

        When plan_expansion runs with blend>0 and an enemy planet in targets, it
        constructs opponent_fn by calling plan_moves for the opponent. We verify:
        1. A move is generated (the lookahead path was taken, not an early exit).
        2. plan_moves is called for the opponent player internally (opponent_fn active).
        3. Applying that opponent move in step_state reduces opponent ship count,
           confirming the opponent model produces meaningful output.
        """
        import src.strategy as strategy_module
        from src.strategy import plan_expansion
        from src.config import PARAMS
        from src.lookahead import build_state, step_state

        # our_planet: FORTRESS (ships=120 >= 21, production=4 >= 2)
        # enemy_planet: FORTRESS (ships=30 >= 21, production=4 >= 4); with probe=60,
        #   expected_defenders=30+4=34, ratio=60/34≈1.76 > weak_ratio → SOFT_ENEMY, not skipped.
        # neutral_for_opp: low production=1 so the opponent (FORTRESS) can expand
        #   there; ensures opponent_fn is non-empty.
        our_planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=120, production=4)
        enemy_planet = make_planet(
            id=1, owner=1, x=72.0, y=50.0, ships=30, production=4
        )
        neutral_for_opp = make_planet(
            id=2, owner=-1, x=74.0, y=50.0, ships=1, production=1
        )
        all_planets = [our_planet, enemy_planet, neutral_for_opp]
        own_classes = {0: "FORTRESS"}

        params_blend = {
            **PARAMS,
            "lookahead_blend": 1.0,
            "lookahead_turns": 1,
            "min_garrison": 10,
        }

        opponent_calls = []
        original_plan_moves = strategy_module.plan_moves

        def capturing_plan_moves(planets, fleets, player, angular_velocity, **kwargs):
            result = original_plan_moves(
                planets, fleets, player, angular_velocity, **kwargs
            )
            if player != 0:
                opponent_calls.append(result)
            return result

        strategy_module.plan_moves = capturing_plan_moves
        try:
            moves = plan_expansion(
                [our_planet],
                [neutral_for_opp],
                [enemy_planet],
                own_classes,
                angular_velocity=0.03,
                agg=1.0,
                params=params_blend,
                comet_ids=frozenset(),
                initial_planets=all_planets,
                fleets=[],
                player=0,
                turn=0,
            )
        finally:
            strategy_module.plan_moves = original_plan_moves

        # A move must have been generated (lookahead path taken, not early-exit)
        assert len(moves) >= 1, "plan_expansion should return at least one move"

        # opponent_fn was active: plan_moves was called for the opponent at least once
        assert len(opponent_calls) >= 1, (
            "plan_moves should have been called for the opponent player when blend>0"
        )

        # Confirm the opponent model produces state changes: apply opponent moves
        # from the first captured call to step_state and check ship reduction.
        opp_moves_list = opponent_calls[0]
        assert opp_moves_list, (
            "Opponent should have moves to launch given 30 ships well above min_garrison=10"
        )
        state = build_state(all_planets, [], turn=0)
        initial_ships = next(p.ships for p in state.planets if p.owner == 1)
        # Apply opponent move (opponent sends ships => their planet loses ships)
        opp_move = opp_moves_list[0]
        next_state = step_state(
            state,
            opp_move,
            player=1,
            angular_velocity=0.03,
        )
        final_ships = next(p.ships for p in next_state.planets if p.owner == 1)
        # After production (+4) and launching ships, the result should differ
        # from just production alone (initial_ships + production). If a fleet was sent,
        # fewer ships remain.
        assert final_ships < initial_ships + enemy_planet.production, (
            "Opponent launching ships should reduce their planet's ship count "
            "below production-only growth"
        )


# ---------------------------------------------------------------------------
# Class: TestScoreCandidateLookaheadHoist
# ---------------------------------------------------------------------------


class TestScoreCandidateLookaheadHoist:
    """score_candidate_lookahead builds greedy_params once, not per roll-forward turn."""

    def test_greedy_params_built_once_per_call(self):
        """greedy_params = {**params, "lookahead_blend": 0.0} is loop-invariant and
        must be constructed ONCE per score_candidate_lookahead call, not once per
        iteration of the `for _ in range(n_extra)` roll-forward loop (issue #55).

        A `{**params}` spread of a non-dict Mapping calls params.keys() exactly once;
        params.get()/params[k] do not. With lookahead_turns=3 (n_extra=2) the loop
        runs twice, so the un-hoisted code spreads params twice. After hoisting it is
        spread once. We assert keys() fires exactly once.
        """
        from collections import abc

        from src.config import PARAMS
        from src.lookahead import score_candidate_lookahead

        class CountingParams(abc.Mapping):
            def __init__(self, data):
                self._data = dict(data)
                self.spread_count = 0

            def keys(self):
                self.spread_count += 1
                return self._data.keys()

            def __getitem__(self, key):
                return self._data[key]

            def __iter__(self):
                return iter(self._data)

            def __len__(self):
                return len(self._data)

        params = CountingParams({**PARAMS, "lookahead_turns": 3})

        def fake_plan_moves(planets, fleets, player, angular_velocity, **kwargs):
            return []

        planet = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        score_candidate_lookahead(
            [planet],
            [],
            0,
            None,
            0,
            0.03,
            opponent_fn=lambda s: [],
            params=params,
            plan_moves_fn=fake_plan_moves,
        )

        assert params.spread_count == 1, (
            "greedy_params must be built once per call (hoisted above the "
            f"roll-forward loop), but params was spread {params.spread_count} times"
        )


# ---------------------------------------------------------------------------
# Class: TestScoreCandidateLookaheadDirect
# ---------------------------------------------------------------------------


class TestScoreCandidateLookaheadDirect:
    """Direct unit tests for score_candidate_lookahead's return value."""

    # Shared stub: plan_moves_fn that always returns no moves.
    @staticmethod
    def _noop_plan_moves(planets, fleets, player, angular_velocity, **kwargs):
        return []

    def _simple_planet(self):
        """One owned planet: owner=0, ships=10, production=2."""
        return make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5.0, ships=10, production=2)

    def test_returns_exact_score_at_lookahead_turns_1(self):
        """With lookahead_turns=1 and no moves, the score equals score_state after
        one step of production (ships 10→12): (2-0) + 0.01*(12-0) = 2.12."""
        from src.lookahead import score_candidate_lookahead

        planet = self._simple_planet()
        result = score_candidate_lookahead(
            initial_planets=[planet],
            fleets=[],
            turn=0,
            candidate_move=None,
            player=0,
            angular_velocity=0.0,
            opponent_fn=lambda s: [],
            params={"lookahead_turns": 1, "lookahead_ship_weight": 0.01},
            plan_moves_fn=self._noop_plan_moves,
        )
        assert result == pytest.approx(2.12)

    def test_lookahead_turns_3_differs_from_turns_1_when_production_compounds(self):
        """Increasing lookahead_turns from 1 to 3 advances the roll-forward loop
        twice more, adding 2 production ticks: ships grow 12→14→16, so the score
        changes from 2.12 to 2.16."""
        from src.lookahead import score_candidate_lookahead

        planet = self._simple_planet()

        def make_score(turns):
            return score_candidate_lookahead(
                initial_planets=[planet],
                fleets=[],
                turn=0,
                candidate_move=None,
                player=0,
                angular_velocity=0.0,
                opponent_fn=lambda s: [],
                params={"lookahead_turns": turns, "lookahead_ship_weight": 0.01},
                plan_moves_fn=self._noop_plan_moves,
            )

        score1 = make_score(1)
        score3 = make_score(3)
        assert score1 != score3, (
            f"score at turns=1 ({score1}) should differ from turns=3 ({score3})"
        )
        assert score3 == pytest.approx(2.16), f"expected 2.16 at turns=3, got {score3}"

    def test_lookahead_ship_weight_affects_score(self):
        """params['lookahead_ship_weight'] is passed to score_state; varying it
        changes the returned score.  At turns=1, ships=12: weight 0.01→score 2.12,
        weight 0.1→score 3.2."""
        from src.lookahead import score_candidate_lookahead

        planet = self._simple_planet()

        def make_score(weight):
            return score_candidate_lookahead(
                initial_planets=[planet],
                fleets=[],
                turn=0,
                candidate_move=None,
                player=0,
                angular_velocity=0.0,
                opponent_fn=lambda s: [],
                params={"lookahead_turns": 1, "lookahead_ship_weight": weight},
                plan_moves_fn=self._noop_plan_moves,
            )

        assert make_score(0.01) == pytest.approx(2.12)
        assert make_score(0.1) == pytest.approx(3.2)
        assert make_score(0.01) != make_score(0.1)


# ---------------------------------------------------------------------------
# Class: TestStepStateMulti
# ---------------------------------------------------------------------------


class TestStepStateMulti:
    def _two_planet_state(self):
        """Two owned planets for player 0, no fleets."""
        p0 = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=20, production=0)
        p1 = make_planet(id=1, owner=0, x=30.0, y=50.0, radius=1.0, ships=15, production=0)
        return build_state([p0, p1], [], turn=1)

    def test_multi_move_ship_accounting_two_sources(self):
        """Ships are deducted from each source independently."""
        state = self._two_planet_state()
        moves = [
            [0, 0.0, 8],   # send 8 from planet 0
            [1, math.pi, 5],  # send 5 from planet 1
        ]
        next_s = step_state_multi(state, moves=moves, player=0, angular_velocity=0.0)
        p0 = next(p for p in next_s.planets if p.id == 0)
        p1 = next(p for p in next_s.planets if p.id == 1)
        assert p0.ships == 12, f"expected 20-8=12, got {p0.ships}"
        assert p1.ships == 10, f"expected 15-5=10, got {p1.ships}"

    def test_fleet_count_equals_number_of_valid_moves(self):
        """Exactly one fleet per valid move; insufficient-ship move is skipped silently."""
        state = self._two_planet_state()
        moves = [
            [0, 0.0, 8],   # valid: planet 0 has 20 ships
            [1, math.pi, 99],  # invalid: planet 1 only has 15 ships
        ]
        next_s = step_state_multi(state, moves=moves, player=0, angular_velocity=0.0)
        own_fleets = [f for f in next_s.fleets if f.owner == 0]
        assert len(own_fleets) == 1
        # Planet 1 ships must be untouched (no deduction for the skipped move)
        p1 = next(p for p in next_s.planets if p.id == 1)
        assert p1.ships == 15

    def test_empty_moves_list_no_own_launches(self):
        """Empty moves list: production and combat run, but no own fleet is spawned."""
        p0 = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=10, production=3)
        state = build_state([p0], [], turn=1)
        next_s = step_state_multi(state, moves=[], player=0, angular_velocity=0.0)
        # Production should have run
        owned = next(p for p in next_s.planets if p.id == 0)
        assert owned.ships == 13
        # No own fleet launched
        assert len(next_s.fleets) == 0

    def test_opponent_fn_called_once(self):
        """opponent_fn is invoked exactly once, identical to step_state behaviour."""
        state = self._two_planet_state()
        call_count = [0]

        def counting_fn(s):
            call_count[0] += 1
            return []

        step_state_multi(
            state, moves=[], player=0, angular_velocity=0.0, opponent_fn=counting_fn
        )
        assert call_count[0] == 1

    def test_agrees_with_step_state_for_single_move(self):
        """step_state and step_state_multi must produce identical results for an
        equivalent single move, under the new launch-before-production-and-rotation
        ordering — step_state_multi's docstring promises the non-launch steps are
        byte-for-byte equivalent to step_state.
        """
        planet_single = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=2
        )
        planet_multi = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=2
        )
        move = [0, 0.4, 10]

        state_single = build_state([planet_single], [], turn=0)
        next_single = step_state(
            state_single, move=move, player=0, angular_velocity=0.05
        )

        state_multi = build_state([planet_multi], [], turn=0)
        next_multi = step_state_multi(
            state_multi, moves=[move], player=0, angular_velocity=0.05
        )

        p_single = next_single.planets[0]
        p_multi = next_multi.planets[0]
        assert p_single.ships == p_multi.ships
        assert p_single.owner == p_multi.owner

        assert len(next_single.fleets) == len(next_multi.fleets) == 1
        f_single = next_single.fleets[0]
        f_multi = next_multi.fleets[0]
        assert f_single.x == pytest.approx(f_multi.x)
        assert f_single.y == pytest.approx(f_multi.y)

    def test_agrees_with_step_state_across_all_shared_phases(self):
        """Characterization test pinning step_state_multi([move]) == step_state(move)
        across every phase step_state_multi's docstring claims is byte-for-byte
        shared: production, orbital rotation, an own launch, an opponent_fn
        launch, and a fleet landing that triggers _resolve_combat. The two
        functions are independently maintained copies — this guards against
        silent drift between them.
        """
        from src.math_utils import fleet_speed

        def build_planets():
            # Player's own producing, launching, orbiting planet (av=0.03 moves it).
            p0 = make_planet(
                id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=3
            )
            # Opponent's producing, orbiting planet — source for opponent_fn's launch.
            p1 = make_planet(
                id=1, owner=1, x=30.0, y=50.0, radius=1.0, ships=25, production=2
            )
            # Static neutral target: the inbound fleet below lands here this turn.
            p2 = make_planet(
                id=2, owner=-1, x=90.0, y=50.0, radius=5.0, ships=3, production=0
            )
            return [p0, p1, p2]

        def build_fleets():
            speed = fleet_speed(10)
            fleet_x = 90.0 - speed + 0.1  # lands inside p2's radius this turn
            return [make_fleet(id=0, owner=1, x=fleet_x, y=50.0, angle=0.0, ships=10)]

        def opponent_fn(s):
            return [[1, math.pi, 5]]

        move = [0, 0.4, 10]

        state_single = build_state(build_planets(), build_fleets(), turn=0)
        next_single = step_state(
            state_single,
            move=move,
            player=0,
            angular_velocity=0.03,
            opponent_fn=opponent_fn,
        )

        state_multi = build_state(build_planets(), build_fleets(), turn=0)
        next_multi = step_state_multi(
            state_multi,
            moves=[move],
            player=0,
            angular_velocity=0.03,
            opponent_fn=opponent_fn,
        )

        single_planets = {p.id: (p.owner, p.ships) for p in next_single.planets}
        multi_planets = {p.id: (p.owner, p.ships) for p in next_multi.planets}
        assert single_planets == multi_planets

        # Sanity check the scenario actually exercises combat/capture, not just
        # a no-op landing.
        assert single_planets[2] == (1, 6)

        single_fleets = sorted((f.owner, f.ships) for f in next_single.fleets)
        multi_fleets = sorted((f.owner, f.ships) for f in next_multi.fleets)
        assert single_fleets == multi_fleets

    @pytest.mark.parametrize("move", [[0, 0.4, 10], None])
    def test_step_state_delegates_to_step_state_multi(self, move):
        """step_state(state, move, ...) must produce a state identical to
        step_state_multi(deepcopy(state), [move] or [], ...) — step_state is a
        thin wrapper that converts the optional move into a one-or-zero-element
        list and delegates. Covers both a real move and move=None.
        """
        planet = make_planet(
            id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=30, production=2
        )
        state_direct = build_state([planet], [], turn=0)
        state_for_multi = copy.deepcopy(state_direct)

        next_direct = step_state(
            state_direct, move=move, player=0, angular_velocity=0.05
        )
        moves = [move] if move is not None else []
        next_multi = step_state_multi(
            state_for_multi, moves=moves, player=0, angular_velocity=0.05
        )

        direct_planets = {p.id: (p.owner, p.ships) for p in next_direct.planets}
        multi_planets = {p.id: (p.owner, p.ships) for p in next_multi.planets}
        assert direct_planets == multi_planets

        direct_fleets = sorted(
            (f.owner, f.ships, round(f.x, 9), round(f.y, 9))
            for f in next_direct.fleets
        )
        multi_fleets = sorted(
            (f.owner, f.ships, round(f.x, 9), round(f.y, 9))
            for f in next_multi.fleets
        )
        assert direct_fleets == multi_fleets


# ---------------------------------------------------------------------------
# Class: TestScoreCandidateLookaheadFullMoveList
# ---------------------------------------------------------------------------


class TestScoreCandidateLookaheadFullMoveList:
    """score_candidate_lookahead roll-forward applies the full own-move list each turn."""

    def test_roll_forward_applies_full_move_list_via_step_state_multi(self, monkeypatch):
        """The roll-forward loop must pass the entire our_greedy list to step_state_multi,
        not just our_greedy[0]. With plan_moves_fn returning 2 own moves and
        lookahead_turns=2 (n_extra=1), step_state_multi must be called once with a
        list of length 2."""
        import src.lookahead as mod
        from src.lookahead import score_candidate_lookahead

        captured_move_lists = []
        real_ssm = mod.step_state_multi

        def recording_ssm(state, moves, player, angular_velocity, opponent_fn=None):
            captured_move_lists.append(list(moves))
            return real_ssm(state, moves, player, angular_velocity, opponent_fn)

        monkeypatch.setattr(mod, "step_state_multi", recording_ssm)

        p0 = make_planet(id=0, owner=0, x=70.0, y=50.0, radius=1.0, ships=50, production=0)
        p1 = make_planet(id=1, owner=0, x=30.0, y=50.0, radius=1.0, ships=50, production=0)

        def two_move_plan(planets, fleets, player, angular_velocity, **kwargs):
            if player == 0:
                return [[0, 0.0, 10], [1, math.pi, 10]]
            return []

        score_candidate_lookahead(
            initial_planets=[p0, p1],
            fleets=[],
            turn=0,
            candidate_move=None,
            player=0,
            angular_velocity=0.0,
            opponent_fn=lambda s: [],
            params={"lookahead_turns": 2, "lookahead_ship_weight": 0.01},
            plan_moves_fn=two_move_plan,
        )

        assert len(captured_move_lists) >= 1, (
            "step_state_multi must be called during the roll-forward loop; "
            "got 0 calls (the loop may still be using step_state with our_greedy[0])"
        )
        # step_state (used for the T+1 candidate move) now delegates to
        # step_state_multi too, so the roll-forward loop's call is the LAST
        # recorded one, not necessarily the first.
        assert len(captured_move_lists[-1]) == 2, (
            f"step_state_multi must receive the full move list (2 moves), "
            f"got {len(captured_move_lists[-1])}"
        )


# --- distance helper delegation ---


def test_step_state_combat_arrival_uses_math_utils_distance(monkeypatch):
    """step_state must use math_utils.distance for the fleet-to-planet arrival check."""
    import src.lookahead as mod

    assert hasattr(mod, "distance"), (
        "lookahead.py must import 'distance' from .math_utils"
    )

    calls = []
    real_distance = mod.distance
    monkeypatch.setattr(
        mod, "distance", lambda *a: (calls.append(a), real_distance(*a))[1]
    )

    planet = make_planet(id=0, owner=1, x=70.0, y=50.0, radius=5.0, ships=5)
    fleet = make_fleet(id=0, owner=0, x=70.0, y=50.0, ships=10)
    state = build_state([planet], [fleet], turn=0)
    step_state(state, move=None, player=0, angular_velocity=0.03)

    assert calls, "distance() was not called — step_state still uses inline math.sqrt"
