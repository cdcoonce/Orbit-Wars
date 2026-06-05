"""Tests for the comet-velocity tracking state in agent.py.

The agent keeps module-level state (``_prev_comet_positions``) so it can estimate
a comet's velocity from the one-turn delta between sightings. When the module
persists across multiple games in one process, that state must be reset at the
start of each game (turn 0), otherwise a comet id reused in a new game is matched
against a stale position from the previous game.
"""
import pytest
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet

import src.agent as agent_mod
from src.agent import agent


def make_planet(id=0, owner=0, x=70.0, y=50.0, radius=5, ships=20, production=3):
    return Planet(id, owner, x, y, radius, ships, production)


def make_obs(planets, comet_planet_ids=None, step=0):
    return {
        "planets": [tuple(p) for p in planets],
        "fleets": [],
        "player": 0,
        "angular_velocity": 0.03,
        "step": step,
        "comet_planet_ids": comet_planet_ids,
    }


@pytest.fixture(autouse=True)
def reset_agent_state():
    """Reset module-level tracking state before each test for isolation."""
    agent_mod._initial_planets = None
    agent_mod._prev_comet_positions = {}
    yield


@pytest.fixture
def captured_velocities(monkeypatch):
    """Capture the comet_velocities kwarg passed to plan_moves on each call."""
    calls = []

    def fake_plan_moves(*args, **kwargs):
        calls.append(kwargs.get("comet_velocities"))
        return []

    monkeypatch.setattr(agent_mod, "plan_moves", fake_plan_moves)
    return calls


def test_velocity_computed_from_one_turn_delta(captured_velocities):
    """A comet seen two turns running yields a velocity equal to its position delta."""
    comet = make_planet(id=1, owner=-1, x=70.0, y=50.0, ships=0)
    agent(make_obs([comet], comet_planet_ids=[1], step=0))

    comet_moved = make_planet(id=1, owner=-1, x=72.0, y=51.0, ships=0)
    agent(make_obs([comet_moved], comet_planet_ids=[1], step=1))

    assert captured_velocities[1] == {1: (2.0, 1.0)}


def test_first_sighting_comet_has_no_velocity(captured_velocities):
    """On a comet's first sighting there is no prior position, so no velocity."""
    comet = make_planet(id=1, owner=-1, x=70.0, y=50.0, ships=0)
    agent(make_obs([comet], comet_planet_ids=[1], step=0))

    assert captured_velocities[0] == {}


def test_turn_zero_clears_stale_positions_from_previous_game(captured_velocities):
    """A comet position from a previous episode must not leak into a fresh game.

    Game 1 records comet id 1 at (72, 51). Game 2 begins at turn 0 with the same
    comet id at a far-away position. If turn-0 state were not cleared, the agent
    would compute a garbage velocity from the cross-game delta; instead the comet
    must be treated as a first sighting (no velocity).
    """
    # --- Game 1: comet seen twice, ending at (72, 51) ---
    agent(make_obs([make_planet(id=1, owner=-1, x=70.0, y=50.0, ships=0)],
                   comet_planet_ids=[1], step=0))
    agent(make_obs([make_planet(id=1, owner=-1, x=72.0, y=51.0, ships=0)],
                   comet_planet_ids=[1], step=1))

    # --- Game 2: turn 0, same comet id at a far-away spot ---
    agent(make_obs([make_planet(id=1, owner=-1, x=10.0, y=10.0, ships=0)],
                   comet_planet_ids=[1], step=0))

    # First sighting of the new game: no velocity, not a cross-game garbage delta.
    assert captured_velocities[-1] == {}
