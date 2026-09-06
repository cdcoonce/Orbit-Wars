"""Latency guard against the engine's per-turn ``actTimeout`` (issue #227).

The competition config sets ``actTimeout: 1`` second per turn
(``kaggle_environments/envs/orbit_wars/orbit_wars.json``), but nothing else in
this repo measures how long ``src.agent.plan_turn`` actually takes under the
shipped ``src/config.py`` ``PARAMS``. Local ``env.run`` (see ``run_game.py``,
``trials/game_runner.py``) does not enforce ``actTimeout``, so a turn slow
enough to be forfeited on Kaggle would pass silently here, and Optuna tuning
would have no signal against ever-more-expensive lookahead settings.

This test drives the engine turn-by-turn itself (rather than via ``env.run``)
so it can time only our agent's ``plan_turn`` call, excluding the opponent's
move and the engine's own interpreter step. Both sides use ``plan_turn`` with
the shipped ``PARAMS`` (self-play, matching the evaluation convention in
``trials/game_runner.py``) so the board reaches the contested, many-target
mid-game state the lookahead path is actually expensive against, rather than
staying sparse against a passive opponent.
"""
import random
import time

import pytest
from kaggle_environments import make

from src.agent import plan_turn
from src.config import PARAMS

# 100 self-play turns reliably reaches a populated mid-game board (12+ owned
# planets out of ~28-32 total) without running a full 500-step episode.
N_TURNS = 100

# actTimeout is read from the live engine configuration by name (see
# CLAUDE.md's cite-by-name rule) rather than hardcoded, so this guard tracks
# the shipped competition config if it ever changes.
#
# CI machines run slower than a dev laptop, so the budget is a conservative
# fraction of actTimeout rather than the full second.
SAFETY_FRACTION = 0.5

# Measured locally on 2026-09-06, seed=1, N_TURNS=100, shipped PARAMS
# (lookahead_turns=5, lookahead_blend=0.903, self-play vs. itself):
#   mean ~= 0.0009s, p90 ~= 0.0017s, max ~= 0.0029s
# Comfortably inside SAFETY_FRACTION * actTimeout == 0.5s (~170x headroom) --
# in practice most expansion candidates are filtered out (SKIP_COMBOS,
# can_capture, classification) well before reaching lookahead scoring, so the
# nested-plan_moves worst case described in issue #227 is not realized here.


@pytest.mark.slow
def test_plan_turn_latency_stays_under_act_timeout_budget():
    random.seed(1)
    env = make("orbit_wars", debug=False)
    act_timeout = env.configuration.actTimeout
    budget = SAFETY_FRACTION * act_timeout

    env.reset(2)
    initial_planets0 = None
    prev_comet_positions0: dict[int, tuple[float, float]] = {}
    initial_planets1 = None
    prev_comet_positions1: dict[int, tuple[float, float]] = {}
    turn_times = []

    for _ in range(N_TURNS):
        if env.done:
            break
        obs0 = env.state[0].observation
        obs1 = env.state[1].observation

        start = time.perf_counter()
        moves0, initial_planets0, prev_comet_positions0 = plan_turn(
            obs0, initial_planets0, prev_comet_positions0, params=PARAMS,
        )
        turn_times.append(time.perf_counter() - start)

        moves1, initial_planets1, prev_comet_positions1 = plan_turn(
            obs1, initial_planets1, prev_comet_positions1, params=PARAMS,
        )
        env.step([moves0, moves1])

    assert turn_times, "no turns were played"
    turn_times.sort()
    mean_time = sum(turn_times) / len(turn_times)
    p90_time = turn_times[int(0.9 * (len(turn_times) - 1))]
    max_time = turn_times[-1]

    assert max_time < budget, (
        f"worst plan_turn call took {max_time:.3f}s, exceeding the "
        f"{SAFETY_FRACTION} * actTimeout({act_timeout}) = {budget:.3f}s budget "
        f"(mean={mean_time:.3f}s, p90={p90_time:.3f}s over {len(turn_times)} turns)"
    )
