import math

from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from src.endgame import total_ships, should_play_defensive
from src.strategy import plan_moves, PARAMS


def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5, ships=20, production=2):
    return Planet(id, owner, x, y, radius, ships, production)


def make_fleet(id=0, owner=0, ships=10, x=70.0, y=50.0, angle=0.0, from_planet_id=0):
    return Fleet(id, owner, x, y, angle, from_planet_id, ships)


# --- total_ships ---


class TestTotalShips:
    def test_counts_planet_ships_for_player(self):
        planets = [make_planet(id=0, owner=1, ships=30)]
        fleets = []
        assert total_ships(planets, fleets, player=1) == 30

    def test_counts_fleet_ships_for_player(self):
        planets = []
        fleets = [make_fleet(id=0, owner=1, ships=15)]
        assert total_ships(planets, fleets, player=1) == 15

    def test_sums_planet_and_fleet_ships(self):
        planets = [make_planet(id=0, owner=1, ships=30)]
        fleets = [make_fleet(id=0, owner=1, ships=15)]
        assert total_ships(planets, fleets, player=1) == 45

    def test_ignores_other_player_planets(self):
        planets = [
            make_planet(id=0, owner=1, ships=30),
            make_planet(id=1, owner=2, ships=50),
        ]
        fleets = []
        assert total_ships(planets, fleets, player=1) == 30

    def test_ignores_other_player_fleets(self):
        planets = []
        fleets = [
            make_fleet(id=0, owner=1, ships=15),
            make_fleet(id=1, owner=2, ships=100),
        ]
        assert total_ships(planets, fleets, player=1) == 15

    def test_ignores_neutral_planets(self):
        planets = [
            make_planet(id=0, owner=1, ships=20),
            make_planet(id=1, owner=-1, ships=999),
        ]
        fleets = []
        assert total_ships(planets, fleets, player=1) == 20

    def test_empty_inputs_returns_zero(self):
        assert total_ships([], [], player=1) == 0


# --- should_play_defensive ---


class TestShouldPlayDefensive:
    def test_activates_when_winning_and_past_threshold(self):
        # player 1 has 120 ships, player 2 has 100 ships → ratio 1.2 == lead_margin
        planets = [
            make_planet(id=0, owner=1, ships=120),
            make_planet(id=1, owner=2, ships=100),
        ]
        fleets = []
        result = should_play_defensive(
            planets, fleets, player=1, turn=450, threshold_turn=450, lead_margin=1.2
        )
        assert result is True

    def test_stays_aggressive_when_behind(self):
        # player 1 has 80 ships, player 2 has 100 → ratio 0.8 < lead_margin
        planets = [
            make_planet(id=0, owner=1, ships=80),
            make_planet(id=1, owner=2, ships=100),
        ]
        fleets = []
        result = should_play_defensive(
            planets, fleets, player=1, turn=460, threshold_turn=450, lead_margin=1.2
        )
        assert result is False

    def test_stays_aggressive_before_threshold_turn(self):
        # player 1 has 200 ships vs 50 → clearly winning, but turn < threshold
        planets = [
            make_planet(id=0, owner=1, ships=200),
            make_planet(id=1, owner=2, ships=50),
        ]
        fleets = []
        result = should_play_defensive(
            planets, fleets, player=1, turn=449, threshold_turn=450, lead_margin=1.2
        )
        assert result is False

    def test_zero_enemy_ships_returns_false(self):
        # No enemy ships → ZeroDivisionError guard → returns False
        planets = [make_planet(id=0, owner=1, ships=100)]
        fleets = []
        result = should_play_defensive(
            planets, fleets, player=1, turn=480, threshold_turn=450, lead_margin=1.2
        )
        assert result is False

    def test_exactly_at_threshold_turn_and_exactly_at_lead_margin(self):
        # Boundary: turn == threshold_turn, ratio exactly == lead_margin → activates
        planets = [
            make_planet(id=0, owner=1, ships=120),
            make_planet(id=1, owner=2, ships=100),
        ]
        fleets = []
        result = should_play_defensive(
            planets, fleets, player=1, turn=450, threshold_turn=450, lead_margin=1.2
        )
        assert result is True

    def test_fleet_ships_count_toward_total(self):
        # player 1 has 60 planet ships + 60 fleet ships = 120 total
        # player 2 has 100 ships → ratio 1.2
        planets = [
            make_planet(id=0, owner=1, ships=60),
            make_planet(id=1, owner=2, ships=100),
        ]
        fleets = [make_fleet(id=0, owner=1, ships=60)]
        result = should_play_defensive(
            planets, fleets, player=1, turn=460, threshold_turn=450, lead_margin=1.2
        )
        assert result is True

    def test_enemy_in_transit_fleet_counted_in_denominator(self):
        # Planet-only enemy ships = 50; player 1 planet ships = 120.
        # Ratio ignoring fleet: 120/50 = 2.4 ≥ 1.2 → would wrongly return True.
        # Enemy has 60 ships in transit → combined enemy = 110.
        # Ratio with fleet: 120/110 ≈ 1.09 < 1.2 → must return False.
        planets = [
            make_planet(id=0, owner=1, ships=120),
            make_planet(id=1, owner=2, ships=50),
        ]
        fleets = [make_fleet(id=0, owner=2, ships=60)]
        result = should_play_defensive(
            planets, fleets, player=1, turn=460, threshold_turn=450, lead_margin=1.2
        )
        assert result is False


# --- plan_moves integration with should_play_defensive ---


class TestPlanMovesDefensiveIntegration:
    def test_plan_moves_skips_expansion_when_defensive(self):
        """When winning past threshold turn, plan_moves returns only defense moves (empty
        here since no threats), not expansion moves."""
        # player 1 has 200 ships on a fortress-class planet
        # neutral target has 0 ships (trivially capturable under normal conditions)
        # player 2 has only 10 ships → ratio = 200/10 = 20 >> lead_margin
        my_planet = make_planet(id=0, owner=1, x=70.0, y=50.0, ships=200, production=4)
        neutral_planet = make_planet(
            id=1, owner=-1, x=72.0, y=50.0, ships=0, production=1
        )
        enemy_planet = make_planet(
            id=2, owner=2, x=30.0, y=50.0, ships=10, production=1
        )
        planets = [my_planet, neutral_planet, enemy_planet]
        fleets = []

        # Without defensive mode (turn 0), plan_moves should produce expansion moves
        params_normal = dict(PARAMS)
        params_normal["endgame_threshold_turn"] = 450
        moves_normal = plan_moves(
            planets,
            fleets,
            player=1,
            angular_velocity=0.03,
            turn=0,
            params=params_normal,
        )

        # With defensive mode active (winning + past threshold turn)
        params_defensive = dict(PARAMS)
        params_defensive["endgame_threshold_turn"] = 450
        params_defensive["endgame_lead_margin"] = 1.2
        moves_defensive = plan_moves(
            planets,
            fleets,
            player=1,
            angular_velocity=0.03,
            turn=460,
            params=params_defensive,
        )

        # Normal turn produces expansion moves (toward neutral or enemy)
        assert len(moves_normal) > 0
        # Defensive mode with no threats produces no moves (expansion skipped, no threats)
        assert moves_defensive == []

    def test_plan_moves_defensive_still_reinforces_threats(self):
        """Defensive mode suppresses expansion but must still dispatch reinforcement:
        handle_threats runs before the should_play_defensive early return in
        plan_moves, so a threatened planet still gets reinforced even when
        expansion is skipped."""
        # Fortress-class planet (ships >= fortress_min_ships, production >=
        # fortress_min_production) able to reinforce.
        fortress = make_planet(id=0, owner=1, x=70.0, y=50.0, ships=200, production=4)
        # Owned planet under attack by an inbound enemy fleet.
        threatened = make_planet(id=3, owner=1, x=90.0, y=50.0, ships=20, production=2)
        # Low-ship enemy planet keeps the ship ratio well above lead_margin even
        # with the attacking fleet's ships also counted toward the enemy total.
        enemy_planet = make_planet(
            id=2, owner=2, x=10.0, y=50.0, ships=5, production=1
        )
        # Enemy fleet heading toward `threatened` (arrives at eta=10), giving the
        # fortress at x=70 (arrives at eta=6) time to intercept first.
        enemy_fleet = make_fleet(
            id=0, owner=2, x=116.0, y=50.0, angle=math.pi, ships=10
        )
        planets = [fortress, threatened, enemy_planet]
        fleets = [enemy_fleet]

        params = dict(PARAMS)
        params["endgame_threshold_turn"] = 450
        params["endgame_lead_margin"] = 1.2
        # Small eta_buffer so the fortress's ~6-turn reinforcement clears the
        # ~10-turn threat eta (default eta_buffer=8 would reject it as too slow).
        params["eta_buffer"] = 2

        moves = plan_moves(
            planets,
            fleets,
            player=1,
            angular_velocity=0.0,
            turn=460,
            params=params,
        )

        # Defensive mode must still reinforce -- only expansion is suppressed.
        assert len(moves) > 0
        reinforcement_sources = {m[0] for m in moves}
        assert threatened.id not in reinforcement_sources
        assert fortress.id in reinforcement_sources

    def test_plan_moves_expands_when_losing_past_threshold(self):
        """Even past threshold turn, bot does NOT go defensive when losing."""
        # player 1 has 200 ships; player 2 has 500 → ratio = 0.4 < 1.2
        # neutral has 0 ships → easily capturable
        my_planet = make_planet(id=0, owner=1, x=70.0, y=50.0, ships=200, production=4)
        neutral_planet = make_planet(
            id=1, owner=-1, x=72.0, y=50.0, ships=0, production=1
        )
        enemy_planet = make_planet(
            id=2, owner=2, x=30.0, y=50.0, ships=500, production=1
        )
        planets = [my_planet, neutral_planet, enemy_planet]
        fleets = []

        params = dict(PARAMS)
        params["endgame_threshold_turn"] = 450
        params["endgame_lead_margin"] = 1.2
        moves = plan_moves(
            planets, fleets, player=1, angular_velocity=0.03, turn=480, params=params
        )
        # Should still expand toward neutral (ratio = 200/500 = 0.4 < 1.2 → not defensive)
        assert len(moves) > 0
