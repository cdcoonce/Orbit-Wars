"""Characterization test pinning the real engine's comet-motion contract.

Regular planets rotate orbitally around the sun each turn (orbit_wars.py:572-590),
guarded by `if planet[0] in comet_pid_set: continue`. Comets instead advance along
a pre-computed path (orbit_wars.py:592-610) that `generate_comet_paths`
(orbit_wars.py:215-265) re-samples at constant `comet_speed` arc-length intervals
— so a comet's per-turn displacement is a roughly constant-length step along a
locally near-straight segment, not an orbital rotation. src/agent.py estimates a
comet's velocity as its one-turn position delta and
src/strategy._intercept_comet_linear extrapolates linearly; both already assume
this model. This test pins the engine contract they rely on against the real
kaggle_environments engine so the lookahead fix (issue #77) can be validated
against ground truth.
"""
import math
from typing import NamedTuple

import pytest
from kaggle_environments import make
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet

from src.comets import get_comet_ids

MAX_TURNS_PER_GAME = 150
MAX_GAMES = 5
MIN_CONSECUTIVE_SIGHTINGS = 3  # need >= 2 deltas to compare for collinearity
# Step length may exceed comet_speed slightly: generate_comet_paths re-samples a
# 5000-point dense curve, so the first sample past each arc-length target
# overshoots by at most one dense spacing (< 4% of comet_speed for the widest
# admissible orbit). Chord-vs-arc shortening is far smaller still.
STEP_LENGTH_REL_TOLERANCE = 0.1


class CometMotion(NamedTuple):
    """One tracked comet's motion, paired with the engine's configured speed."""

    comet_speed: float
    deltas: list[tuple[float, float]]


def _track_longest_comet_run(max_turns=MAX_TURNS_PER_GAME):
    """Step a fresh no-op game forward, returning the engine's configured
    `cometSpeed` and the longest run of consecutive per-turn (x, y) positions
    seen for a single comet id."""
    env = make("orbit_wars", debug=False)
    trainer = env.train([None, "starter"])
    trainer.reset()

    runs: dict[int, list[tuple[float, float]]] = {}
    best_run: list[tuple[float, float]] = []
    for _ in range(max_turns):
        obs, _reward, done, _info = trainer.step([])
        comet_ids = get_comet_ids(obs)
        seen_this_turn = set()
        for raw in obs.get("planets", []):
            planet = Planet(*raw)
            if planet.id in comet_ids:
                seen_this_turn.add(planet.id)
                runs.setdefault(planet.id, []).append((planet.x, planet.y))
        for planet_id in list(runs):
            if planet_id not in seen_this_turn:
                if len(runs[planet_id]) > len(best_run):
                    best_run = runs[planet_id]
                del runs[planet_id]
        if done:
            break
    for positions in runs.values():
        if len(positions) > len(best_run):
            best_run = positions
    return env.configuration.cometSpeed, best_run


def _find_comet_run():
    """Try several fresh games until one yields enough consecutive comet sightings."""
    for _ in range(MAX_GAMES):
        comet_speed, run = _track_longest_comet_run()
        if len(run) >= MIN_CONSECUTIVE_SIGHTINGS:
            return comet_speed, run
    pytest.fail(
        f"No comet was tracked for >= {MIN_CONSECUTIVE_SIGHTINGS} consecutive turns "
        f"across {MAX_GAMES} games of {MAX_TURNS_PER_GAME} turns each; cannot pin "
        "comet-motion semantics."
    )


@pytest.fixture(scope="module")
def comet_motion():
    """Engine `cometSpeed` plus consecutive per-turn (dx, dy) displacement
    vectors for one tracked comet."""
    comet_speed, run = _find_comet_run()
    deltas = [
        (run[i + 1][0] - run[i][0], run[i + 1][1] - run[i][1])
        for i in range(len(run) - 1)
    ]
    return CometMotion(comet_speed, deltas)


def test_comet_step_length_matches_configured_comet_speed(comet_motion):
    """Comet per-turn step length is ~the engine's configured comet_speed.

    See generate_comet_paths (orbit_wars.py:215-265): the precomputed path is
    resampled at constant comet_speed arc-length intervals, and the per-turn
    advance (orbit_wars.py:592-610) walks that path one sample at a time.
    """
    assert comet_motion.comet_speed > 0.0
    for dx, dy in comet_motion.deltas:
        assert math.hypot(dx, dy) == pytest.approx(
            comet_motion.comet_speed, rel=STEP_LENGTH_REL_TOLERANCE
        )


def test_comet_motion_is_locally_linear_not_orbital(comet_motion):
    """Successive comet displacement vectors are near-collinear over a short
    window — i.e. locally linear, distinguishable from an orbital rotation.

    Regular planets rotate around the sun each turn (orbit_wars.py:572-590);
    comets are explicitly excluded from that rotation (guarded by
    `if planet[0] in comet_pid_set: continue`) and instead walk the
    near-straight precomputed path from generate_comet_paths.
    """
    deltas = comet_motion.deltas
    for (dx1, dy1), (dx2, dy2) in zip(deltas, deltas[1:]):
        cos_angle = (dx1 * dx2 + dy1 * dy2) / (
            math.hypot(dx1, dy1) * math.hypot(dx2, dy2)
        )
        assert cos_angle > 0.95
