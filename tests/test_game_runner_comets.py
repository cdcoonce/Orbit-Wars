"""Comet-velocity fidelity test for the self-play trial agent.

The deployed agent (``src/agent.py``) tracks per-comet velocities and passes
``comet_velocities`` into ``plan_moves`` so comets are intercepted via linear
extrapolation. The tuning agent (``trials/game_runner.make_agent``) must exercise
that *same* targeting code — otherwise Optuna optimises comet-related params
against a comet-blind agent that never actually attempts an intercept.

This test pins that fidelity: a comet seen on two consecutive turns must yield a
velocity estimate handed to ``plan_moves`` on the trial-agent path.
"""
import src.agent as agent_mod
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet

from src.config import PARAMS
from trials.game_runner import make_agent


def make_obs(planets, comet_planet_ids=None, step=0):
    return {
        "planets": [tuple(p) for p in planets],
        "fleets": [],
        "player": 0,
        "angular_velocity": 0.03,
        "step": step,
        "comet_planet_ids": comet_planet_ids,
    }


def test_trial_agent_produces_comet_velocities(monkeypatch):
    """make_agent's closure must hand a velocity estimate to plan_moves.

    A comet at (70, 50) on turn 0 and (72, 51) on turn 1 has a one-turn delta of
    (2, 1); the trial agent must compute and pass that as ``comet_velocities`` so
    the comet intercept path is actually attempted during self-play.
    """
    captured = []

    def fake_plan_moves(*args, **kwargs):
        captured.append(kwargs.get("comet_velocities"))
        return []

    monkeypatch.setattr(agent_mod, "plan_moves", fake_plan_moves)

    agent = make_agent(PARAMS)
    agent(make_obs([Planet(1, -1, 70.0, 50.0, 5, 0, 3)],
                   comet_planet_ids=[1], step=0))
    agent(make_obs([Planet(1, -1, 72.0, 51.0, 5, 0, 3)],
                   comet_planet_ids=[1], step=1))

    assert captured[1] == {1: (2.0, 1.0)}
