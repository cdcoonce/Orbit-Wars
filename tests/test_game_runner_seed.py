"""Seed reproducibility tests for trials/game_runner.py (fast suite, no optuna).

The Kaggle engine builds every map from the process-global ``random`` module,
so reproducible self-play hinges on two things: a fixed seed must determine the
map, and concurrent trials (``run_trials.py`` runs Optuna with ``n_jobs=4``, a
thread pool) must not clobber one another's RNG. The tests below pin both.
"""
import random
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from src.config import PARAMS


# ---------------------------------------------------------------------------
# run_games — paired seed routing (variance reduction)
# ---------------------------------------------------------------------------

class TestPairedSeeding:
    def test_paired_games_share_a_map_seed(self):
        """With a fixed base seed, consecutive games form pairs that share one
        map seed while the challenger swaps sides — so map-luck cancels."""
        from trials.game_runner import run_games
        calls = []

        def mock_run_game(cp, chp, challenger_player=0, timeout=60, seed=None):
            calls.append((challenger_player, seed))
            return "draw"

        with patch("trials.game_runner.run_game", mock_run_game):
            run_games(PARAMS, PARAMS, n_games=4, seed=100)

        # challenger alternates sides every game
        assert [c[0] for c in calls] == [0, 1, 0, 1]
        # each pair (0,1) and (2,3) shares its map seed
        assert calls[0][1] == calls[1][1]
        assert calls[2][1] == calls[3][1]
        # different pairs use different maps
        assert calls[0][1] != calls[2][1]


# ---------------------------------------------------------------------------
# The premise: the seed is the lever that controls map generation
# ---------------------------------------------------------------------------

class TestSeedControlsMap:
    def test_seed_determines_generated_map(self):
        """The engine builds its map from the global RNG, so a fixed seed yields
        an identical map and a different seed yields a different one. This proves
        the seed — not engine determinism alone — controls the board."""
        from kaggle_environments.envs.orbit_wars.orbit_wars import generate_planets

        random.seed(1)
        first = generate_planets()
        random.seed(1)
        same = generate_planets()
        random.seed(2)
        other = generate_planets()

        assert first == same          # same seed -> same map
        assert first != other         # different seed -> different map


# ---------------------------------------------------------------------------
# The fix: each game runs in an isolated process, so seeding is thread-safe
# ---------------------------------------------------------------------------

class TestProcessIsolation:
    def test_seeded_game_does_not_perturb_caller_rng(self):
        """A seeded game must consume randomness in a separate process, leaving
        the calling thread's global RNG untouched.

        Threads in one process share a single global ``random`` instance, so if
        ``run_game`` seeded in-thread it would corrupt sibling Optuna workers
        (``n_jobs=4``). Isolating the game in its own process is what makes
        per-trial seeding reproducible under parallelism.
        """
        from trials.game_runner import run_game

        random.seed(12345)
        expected = [random.random() for _ in range(5)]

        random.seed(12345)
        run_game(PARAMS, PARAMS, seed=999)  # heavy RNG use, but isolated
        after = [random.random() for _ in range(5)]

        assert after == expected


# ---------------------------------------------------------------------------
# run_games — reproducibility under concurrency (the production path)
# ---------------------------------------------------------------------------

class TestReproducibility:
    def test_concurrent_same_seed_is_reproducible(self):
        """The same seed played concurrently from several threads — exactly how
        run_trials.py drives games under n_jobs=4 — must yield identical results
        every time. Satisfies "run_games(seed=S) returns identical results across
        invocations" while exercising the threaded path that previously broke it.
        """
        from trials.game_runner import run_games

        def play(_):
            _, results = run_games(PARAMS, PARAMS, n_games=1, seed=7)
            return tuple(results)

        with ThreadPoolExecutor(max_workers=4) as ex:
            outcomes = list(ex.map(play, range(4)))

        assert len(set(outcomes)) == 1
