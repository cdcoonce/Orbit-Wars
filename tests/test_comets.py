"""Tests for src/comets.py — get_comet_ids and effective_production."""
import pytest
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet

from src.comets import effective_production, get_comet_ids


def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5, ships=20, production=3):
    return Planet(id, owner, x, y, radius, ships, production)


# --- get_comet_ids ---

class TestGetCometIds:
    def test_returns_empty_set_when_key_absent(self):
        assert get_comet_ids({}) == set()

    def test_returns_empty_set_when_value_is_none(self):
        assert get_comet_ids({"comet_planet_ids": None}) == set()

    def test_returns_set_of_ids_when_present(self):
        result = get_comet_ids({"comet_planet_ids": [3, 7, 11]})
        assert result == {3, 7, 11}

    def test_returns_set_for_single_id(self):
        assert get_comet_ids({"comet_planet_ids": [5]}) == {5}

    def test_returns_empty_set_for_empty_list(self):
        assert get_comet_ids({"comet_planet_ids": []}) == set()


# --- effective_production ---

class TestEffectiveProduction:
    def test_non_comet_returns_raw_production(self):
        planet = make_planet(id=1, production=4)
        assert effective_production(planet, comet_ids={2, 3}, multiplier=0.0) == 4.0

    def test_comet_with_zero_multiplier_returns_zero(self):
        planet = make_planet(id=5, production=3)
        assert effective_production(planet, comet_ids={5}, multiplier=0.0) == 0.0

    def test_comet_with_double_multiplier_returns_doubled(self):
        planet = make_planet(id=5, production=3)
        assert effective_production(planet, comet_ids={5}, multiplier=2.0) == 6.0

    def test_non_comet_unaffected_by_multiplier(self):
        planet = make_planet(id=1, production=4)
        # multiplier=2.0 but planet is not a comet — raw production returned
        assert effective_production(planet, comet_ids={99}, multiplier=2.0) == 4.0

    def test_comet_with_one_multiplier_returns_raw_production(self):
        planet = make_planet(id=7, production=5)
        assert effective_production(planet, comet_ids={7}, multiplier=1.0) == 5.0

    def test_empty_comet_ids_always_returns_raw_production(self):
        planet = make_planet(id=3, production=2)
        assert effective_production(planet, comet_ids=set(), multiplier=0.0) == 2.0
