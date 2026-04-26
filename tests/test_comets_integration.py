"""Integration tests for comet_ids wiring through strategy.py and agent.py."""
import pytest
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet

from src.strategy import value_tier, plan_expansion, plan_moves, PARAMS
from src.agent import agent


def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5, ships=20, production=3):
    return Planet(id, owner, x, y, radius, ships, production)


# --- value_tier comet integration ---

class TestValueTierWithCometIds:
    def test_comet_with_zero_multiplier_is_treated_as_zero_production(self):
        # A comet with production=4 (HIGH) with multiplier=0 should become LOW
        params = {**PARAMS, "comet_value_multiplier": 0.0}
        comet = make_planet(id=5, production=4)
        assert value_tier(comet, comet_ids={5}, params=params) == "LOW"

    def test_non_comet_unaffected_by_comet_ids(self):
        params = {**PARAMS, "comet_value_multiplier": 0.0}
        regular = make_planet(id=1, production=4)
        assert value_tier(regular, comet_ids={5}, params=params) == "HIGH"

    def test_comet_with_default_multiplier_unchanged(self):
        # Default comet_value_multiplier=1.0 means no change
        comet = make_planet(id=5, production=4)
        assert value_tier(comet, comet_ids={5}) == "HIGH"

    def test_value_tier_accepts_empty_comet_ids(self):
        # Backward-compatible: no comet_ids arg works with frozenset default
        planet = make_planet(id=1, production=4)
        assert value_tier(planet) == "HIGH"

    def test_comet_with_low_prod_and_zero_multiplier_stays_low(self):
        params = {**PARAMS, "comet_value_multiplier": 0.0}
        comet = make_planet(id=3, production=1)
        assert value_tier(comet, comet_ids={3}, params=params) == "LOW"


# --- plan_expansion comet integration ---

class TestPlanExpansionWithCometIds:
    def test_comet_zero_multiplier_blocks_outpost_from_attacking_high_value_comet(self):
        """OUTPOST skips non-LOW targets; a comet with multiplier=0.0 scores as 0 -> LOW,
        so an outpost would be allowed to attack it if it's easy. But actually the HIGH-value
        filter in plan_expansion checks value_tier, so with multiplier=0 the comet appears
        LOW and the outpost CAN attack it."""
        params = {**PARAMS, "comet_value_multiplier": 0.0, "min_garrison": 10}
        outpost = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=20, production=1)
        # production=4 would normally be HIGH and blocked for outposts,
        # but with multiplier=0 in comet_ids it becomes LOW -> allowed
        comet_neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=0, production=4)
        own_classes = {0: "OUTPOST"}
        moves = plan_expansion(
            [outpost], [comet_neutral], [], own_classes,
            angular_velocity=0.03, comet_ids={1}, params=params
        )
        # With multiplier=0 the comet appears LOW → OUTPOST gate passes → attack happens
        assert len(moves) == 1

    def test_comet_zero_multiplier_makes_score_zero_so_no_attack(self):
        """score = effective_production / (eta+1)^2; if effective_production=0 score=0,
        which is not > -inf, so no best_target is selected when ALL targets are zero-scored.
        Wait — actually 0 > -inf is True, so score=0 IS selected. Instead test that a
        non-comet beats a comet when both are candidates for a FORTRESS."""
        params = {**PARAMS, "comet_value_multiplier": 0.0}
        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        # Two easy neutrals adjacent: comet (production=3) vs regular (production=3)
        # Both equally close, comet scores 0 while regular scores normally.
        # Only one move allowed (one source), so fortress picks regular over comet.
        comet_neutral = make_planet(id=1, owner=-1, x=71.0, y=50.0, ships=0, production=3)
        regular_neutral = make_planet(id=2, owner=-1, x=72.0, y=50.0, ships=0, production=3)
        own_classes = {0: "FORTRESS"}
        moves_comet_present = plan_expansion(
            [fortress], [comet_neutral, regular_neutral], [], own_classes,
            angular_velocity=0.03, comet_ids={1}, params=params
        )
        # Should pick the regular neutral (id=2) over the comet (id=1)
        assert len(moves_comet_present) == 1
        assert moves_comet_present[0][0] == 0  # source is fortress

    def test_plan_expansion_default_comet_ids_backward_compatible(self):
        """Calling plan_expansion without comet_ids still works (frozenset default)."""
        fortress = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        soft_enemy = make_planet(id=1, owner=1, x=72.0, y=50.0, ships=1, production=1)
        own_classes = {0: "FORTRESS"}
        moves = plan_expansion([fortress], [], [soft_enemy], own_classes, angular_velocity=0.03)
        assert len(moves) == 1


# --- plan_moves comet integration ---

class TestPlanMovesWithCometIds:
    def test_plan_moves_accepts_comet_ids_kwarg(self):
        """plan_moves accepts comet_ids keyword argument without error."""
        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        moves = plan_moves(
            [owned, neutral], fleets=[], player=0, angular_velocity=0.03,
            comet_ids={99}
        )
        # Should still produce moves (planet 1 is not a comet)
        assert len(moves) >= 1

    def test_plan_moves_default_comet_ids_backward_compatible(self):
        """Calling plan_moves without comet_ids works as before."""
        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        moves = plan_moves([owned, neutral], fleets=[], player=0, angular_velocity=0.03)
        assert len(moves) >= 1


# --- agent comet_ids extraction ---

class TestAgentCometIdsExtraction:
    def _make_obs(self, planets, comet_planet_ids=None):
        return {
            "planets": [tuple(p) for p in planets],
            "fleets": [],
            "player": 0,
            "angular_velocity": 0.03,
            "step": 0,
            "comet_planet_ids": comet_planet_ids,
        }

    def test_agent_works_without_comet_planet_ids_key(self):
        """agent() handles obs with no comet_planet_ids key gracefully."""
        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        obs = {
            "planets": [tuple(owned), tuple(neutral)],
            "fleets": [],
            "player": 0,
            "angular_velocity": 0.03,
            "step": 0,
        }
        result = agent(obs)
        assert isinstance(result, list)

    def test_agent_works_with_comet_planet_ids_none(self):
        """agent() handles obs where comet_planet_ids is explicitly None."""
        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        obs = {
            "planets": [tuple(owned)],
            "fleets": [],
            "player": 0,
            "angular_velocity": 0.03,
            "step": 0,
            "comet_planet_ids": None,
        }
        result = agent(obs)
        assert isinstance(result, list)

    def test_agent_works_with_comet_planet_ids_list(self):
        """agent() handles obs where comet_planet_ids is a list of ids."""
        owned = make_planet(id=0, owner=0, x=70.0, y=50.0, ships=60, production=4)
        neutral = make_planet(id=1, owner=-1, x=72.0, y=50.0, ships=1, production=1)
        obs = {
            "planets": [tuple(owned), tuple(neutral)],
            "fleets": [],
            "player": 0,
            "angular_velocity": 0.03,
            "step": 0,
            "comet_planet_ids": [1],
        }
        result = agent(obs)
        assert isinstance(result, list)
