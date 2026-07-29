"""Tests for trials/game_runner.py and trials/run_trials.py."""
import concurrent.futures
import logging
import math
import os
from unittest.mock import MagicMock, patch

import optuna
import pytest

from src.config import PARAMS


# ---------------------------------------------------------------------------
# make_agent
# ---------------------------------------------------------------------------

class TestMakeAgent:
    def test_returns_callable(self):
        from trials.game_runner import make_agent
        agent = make_agent(PARAMS)
        assert callable(agent)

    def test_callable_accepts_obs(self):
        from trials.game_runner import make_agent
        agent = make_agent(PARAMS)
        obs = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 0}
        result = agent(obs)
        assert isinstance(result, list)

    def test_per_closure_initial_planets_resets_on_turn_zero(self):
        """Each make_agent() closure tracks its own initial_planets independently."""
        from trials.game_runner import make_agent
        captured = []

        def mock_plan_moves(planets, fleets, player, angular_velocity, turn,
                            params=None, comet_ids=None, initial_planets=None,
                            comet_velocities=None):
            captured.append(initial_planets)
            return []

        obs0 = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 0}
        obs1 = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 1}

        # make_agent delegates to src.agent.plan_turn, which calls plan_moves
        # via the src.agent namespace, so that is the patch target.
        with patch("src.agent.plan_moves", mock_plan_moves):
            agent = make_agent(PARAMS)
            agent(obs0)  # turn 0 — sets initial_planets
            agent(obs1)  # turn 1 — reuses cached initial_planets

        # Both calls should reference the same initial_planets list (turn-0 value)
        assert captured[0] is captured[1]

    def test_two_closures_independent(self):
        """Two agents from separate make_agent() calls don't share initial_planets."""
        from trials.game_runner import make_agent
        initial_planets_seen = []

        def mock_plan_moves(planets, fleets, player, angular_velocity, turn,
                            params=None, comet_ids=None, initial_planets=None,
                            comet_velocities=None):
            initial_planets_seen.append(initial_planets)
            return []

        obs0 = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 0}

        agent_a = make_agent(PARAMS)
        agent_b = make_agent(PARAMS)

        # See note above: the shared wrapper calls plan_moves via src.agent.
        with patch("src.agent.plan_moves", mock_plan_moves):
            agent_a(obs0)
            agent_b(obs0)

        # Each closure must have its own initial_planets list, not the same object.
        assert len(initial_planets_seen) == 2
        assert initial_planets_seen[0] is not initial_planets_seen[1]


# ---------------------------------------------------------------------------
# run_games — player alternation
# ---------------------------------------------------------------------------

class TestRunGames:
    def test_alternates_challenger_player(self):
        """challenger_player for game i must be i % 2."""
        from trials.game_runner import run_games
        call_log = []

        def mock_run_game(challenger_params, champion_params, challenger_player=0,
                          timeout=60):
            call_log.append(challenger_player)
            return "draw"

        with patch("trials.game_runner.run_game", mock_run_game):
            run_games(PARAMS, PARAMS, n_games=6)

        assert call_log == [0, 1, 0, 1, 0, 1]

    def test_win_rate_counts_challenger_wins_only(self):
        """Win rate = challenger wins / total games; draws and champion wins excluded."""
        from trials.game_runner import run_games

        outcomes = ["challenger", "champion", "draw", "challenger"]

        def mock_run_game(cp, chp, challenger_player=0, timeout=60):
            return outcomes.pop(0)

        with patch("trials.game_runner.run_game", mock_run_game):
            win_rate, results = run_games(PARAMS, PARAMS, n_games=4)

        assert win_rate == pytest.approx(0.5)  # 2 wins out of 4
        assert results == ["challenger", "champion", "draw", "challenger"]


# ---------------------------------------------------------------------------
# run_game — timeout
# ---------------------------------------------------------------------------

class TestRunGameTimeout:
    def test_timeout_returns_draw(self):
        """A game exceeding the timeout must return 'draw' without raising.

        The game runs in a shared worker pool (see game_runner._get_pool); a
        slow game surfaces as a TimeoutError from ``future.result(timeout=...)``.
        We mock that boundary so no real game is played.
        """
        from trials.game_runner import run_game

        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()

        mock_pool = MagicMock()
        mock_pool.submit.return_value = mock_future

        with patch("trials.game_runner._get_pool", return_value=mock_pool):
            result = run_game(PARAMS, PARAMS)

        assert result == "draw"


# ---------------------------------------------------------------------------
# run_game — self-healing pool after BrokenProcessPool
# ---------------------------------------------------------------------------

class TestRunGameBrokenPoolSelfHeals:
    def test_poisoned_pool_is_replaced_and_next_call_gets_real_result(self, caplog):
        """A poisoned (broken) pool must be discarded so the next run_game call is
        served by a *different* executor object that can actually play a game."""
        import trials.game_runner as game_runner

        poisoned_pool = MagicMock()
        poisoned_pool.submit.side_effect = concurrent.futures.process.BrokenProcessPool(
            "worker process died",
        )

        fresh_future = MagicMock()
        fresh_future.result.return_value = "champion"
        fresh_pool = MagicMock()
        fresh_pool.submit.return_value = fresh_future

        game_runner._pool = poisoned_pool
        game_runner._consecutive_pool_rebuilds = 0
        game_runner._pool_rebuilds_exhausted = False
        try:
            with patch(
                "trials.game_runner.concurrent.futures.ProcessPoolExecutor",
                return_value=fresh_pool,
            ), caplog.at_level(logging.WARNING, logger="trials.game_runner"):
                first_result = game_runner.run_game(PARAMS, PARAMS)
                assert first_result == "draw"
                assert game_runner._pool is not poisoned_pool

                second_result = game_runner.run_game(PARAMS, PARAMS)
                assert second_result == "champion"
                assert game_runner._pool is fresh_pool
        finally:
            game_runner._pool = None
            game_runner._consecutive_pool_rebuilds = 0
            game_runner._pool_rebuilds_exhausted = False

        # The rebuild is announced on its own log path, not the generic
        # "Worker raised an unexpected exception" fallback.
        assert "rebuild" in caplog.text.lower()
        assert "unexpected exception" not in caplog.text.lower()

    def test_repeated_unrecoverable_breaks_stop_rebuilding(self):
        """A deterministically-fatal worker must not cause the pool to be rebuilt
        forever — rebuild attempts are capped."""
        import trials.game_runner as game_runner

        always_broken_pool = MagicMock()
        always_broken_pool.submit.side_effect = concurrent.futures.process.BrokenProcessPool(
            "dead",
        )

        construct_calls = []

        def fake_ctor(*args, **kwargs):
            construct_calls.append((args, kwargs))
            return always_broken_pool

        game_runner._pool = always_broken_pool
        game_runner._consecutive_pool_rebuilds = 0
        game_runner._pool_rebuilds_exhausted = False
        try:
            with patch(
                "trials.game_runner.concurrent.futures.ProcessPoolExecutor",
                side_effect=fake_ctor,
            ):
                for _ in range(game_runner.MAX_CONSECUTIVE_POOL_REBUILDS + 5):
                    result = game_runner.run_game(PARAMS, PARAMS)
                    assert result == "draw"
                # The dead executor is never left installed, even once rebuilds stop.
                assert game_runner._pool is not always_broken_pool
        finally:
            game_runner._pool = None
            game_runner._consecutive_pool_rebuilds = 0
            game_runner._pool_rebuilds_exhausted = False

        assert len(construct_calls) <= game_runner.MAX_CONSECUTIVE_POOL_REBUILDS

    def test_concurrent_reports_of_one_broken_pool_count_as_one_rebuild(self):
        """Optuna's threads all see BrokenProcessPool from the *same* dead executor.

        Those duplicate reports must not each consume rebuild budget (which would
        strand the dead pool in place) nor discard the replacement pool.
        """
        import trials.game_runner as game_runner

        broken_pool = MagicMock()
        replacement_pool = MagicMock()

        game_runner._pool = broken_pool
        game_runner._consecutive_pool_rebuilds = 0
        game_runner._pool_rebuilds_exhausted = False
        try:
            game_runner._discard_broken_pool(broken_pool)
            assert game_runner._pool is None
            assert game_runner._consecutive_pool_rebuilds == 1

            # A sibling thread reports the same dead executor after another
            # thread has already installed a replacement.
            game_runner._pool = replacement_pool
            for _ in range(game_runner.MAX_CONSECUTIVE_POOL_REBUILDS + 5):
                game_runner._discard_broken_pool(broken_pool)

            assert game_runner._pool is replacement_pool
            assert game_runner._consecutive_pool_rebuilds == 1
            assert game_runner._pool_rebuilds_exhausted is False
        finally:
            game_runner._pool = None
            game_runner._consecutive_pool_rebuilds = 0
            game_runner._pool_rebuilds_exhausted = False


# ---------------------------------------------------------------------------
# write_champion — atomic write
# ---------------------------------------------------------------------------

class TestWriteChampion:
    def test_atomic_write_creates_file(self, tmp_path):
        from trials.run_trials import write_champion

        champion_file = tmp_path / "champion.py"
        with patch("trials.run_trials.CHAMPION_FILE", champion_file):
            write_champion(PARAMS)

        assert champion_file.exists()

    def test_no_temp_file_remains(self, tmp_path):
        from trials.run_trials import write_champion

        champion_file = tmp_path / "champion.py"
        with patch("trials.run_trials.CHAMPION_FILE", champion_file):
            write_champion(PARAMS)

        assert not any(tmp_path.glob("*.tmp"))

    def test_content_contains_champion_params(self, tmp_path):
        from trials.run_trials import write_champion

        champion_file = tmp_path / "champion.py"
        with patch("trials.run_trials.CHAMPION_FILE", champion_file):
            write_champion(PARAMS)

        content = champion_file.read_text()
        assert "CHAMPION_PARAMS" in content
        assert "'fortress_min_ships'" in content

    def test_rejects_non_finite_values(self, tmp_path):
        from trials.run_trials import write_champion

        bad_params = {**PARAMS, "weak_ratio": math.inf}
        champion_file = tmp_path / "champion.py"
        with patch("trials.run_trials.CHAMPION_FILE", champion_file):
            with pytest.raises(ValueError, match="Non-finite"):
                write_champion(bad_params)

    def test_uses_os_replace(self, tmp_path):
        """Promotion must use os.replace (atomic rename), not a plain write."""
        from trials.run_trials import write_champion

        champion_file = tmp_path / "champion.py"
        replace_calls = []
        real_replace = os.replace

        def mock_replace(src, dst):
            replace_calls.append((src, dst))
            real_replace(src, dst)

        with patch("trials.run_trials.CHAMPION_FILE", champion_file):
            with patch("trials.run_trials.os.replace", mock_replace):
                write_champion(PARAMS)

        assert len(replace_calls) == 1
        src, dst = replace_calls[0]
        assert src.endswith(".tmp")
        assert not src.endswith(".tmp.tmp")


# ---------------------------------------------------------------------------
# champion.py — initial state
# ---------------------------------------------------------------------------

class TestChampionModule:
    def test_champion_params_has_all_keys(self):
        from trials.champion import CHAMPION_PARAMS
        assert set(CHAMPION_PARAMS.keys()) == set(PARAMS.keys())

    def test_champion_params_has_game_length(self):
        from trials.champion import CHAMPION_PARAMS
        assert "game_length" in CHAMPION_PARAMS


# ---------------------------------------------------------------------------
# Stale-study.db guard — PARAM_SPACE fingerprint
# ---------------------------------------------------------------------------

class TestParamSpaceFingerprint:
    def test_fingerprint_is_stable_across_calls(self):
        """A process-stable digest (hashlib, not builtin hash()) must not vary."""
        from trials.run_trials import param_space_fingerprint
        assert param_space_fingerprint() == param_space_fingerprint()

    def test_fingerprint_changes_when_param_space_changes(self):
        """Altering any bound must change the fingerprint."""
        from trials import run_trials
        before = run_trials.param_space_fingerprint()
        mutated = {**run_trials.PARAM_SPACE, "fortress_min_ships": (1, 999, int)}
        with patch.object(run_trials, "PARAM_SPACE", mutated):
            after = run_trials.param_space_fingerprint()
        assert before != after


class TestLoadGuardedStudy:
    def test_fresh_run_records_current_fingerprint(self, tmp_path):
        """A brand-new study must record the current PARAM_SPACE fingerprint."""
        from trials.run_trials import (
            FINGERPRINT_ATTR,
            load_guarded_study,
            param_space_fingerprint,
        )
        db = tmp_path / "study.db"
        study = load_guarded_study(db)
        assert study.user_attrs[FINGERPRINT_ATTR] == param_space_fingerprint()

    def test_matching_fingerprint_resumes(self, tmp_path):
        """A study with a matching fingerprint resumes — trials preserved, nothing archived."""
        from trials.run_trials import load_guarded_study
        db = tmp_path / "study.db"
        first = load_guarded_study(db)
        first.add_trial(optuna.trial.create_trial(value=0.5))

        second = load_guarded_study(db)

        assert len(second.trials) == 1          # resumed, not reset
        assert not list(tmp_path.glob("*.stale*"))  # nothing archived

    def test_mismatch_archives_and_starts_fresh(self, tmp_path):
        """A study fingerprinted to a different PARAM_SPACE is archived, not resumed."""
        from trials import run_trials
        db = tmp_path / "study.db"
        storage = f"sqlite:///{db}"

        seed = optuna.create_study(
            study_name=run_trials.STUDY_NAME, storage=storage, direction="maximize",
        )
        seed.set_user_attr(run_trials.FINGERPRINT_ATTR, "stale-fingerprint")
        seed.add_trial(optuna.trial.create_trial(value=0.9))
        del seed

        study = run_trials.load_guarded_study(db)

        assert list(tmp_path.glob("study.db.stale*"))  # stale db archived aside
        assert len(study.trials) == 0                  # fresh — old trials not inherited
        assert study.user_attrs[run_trials.FINGERPRINT_ATTR] == (
            run_trials.param_space_fingerprint()
        )

    def test_reset_archives_even_on_match(self, tmp_path):
        """--reset forces a fresh study even when the fingerprint matches."""
        from trials.run_trials import load_guarded_study
        db = tmp_path / "study.db"
        first = load_guarded_study(db)
        first.add_trial(optuna.trial.create_trial(value=0.5))

        study = load_guarded_study(db, reset=True)

        assert list(tmp_path.glob("study.db.stale*"))
        assert len(study.trials) == 0


# ---------------------------------------------------------------------------
# objective — stale-snapshot promotion guard
# ---------------------------------------------------------------------------

class TestObjectiveStaleChampionGuard:
    def test_stale_snapshot_does_not_overwrite_newer_champion(self):
        """Stale-snapshot race: promotion skipped when _current_champion changed mid-trial.

        Race reproduced: worker A snapshots v1, then worker B promotes v2 during
        run_games; worker A must NOT overwrite v2 even though its win_rate was
        measured against the now-stale v1.
        """
        from trials import run_trials

        v1 = {**PARAMS, "fortress_min_ships": 10}
        v2 = {**PARAMS, "fortress_min_ships": 20}

        original = dict(run_trials._current_champion)
        with run_trials._lock:
            run_trials._current_champion.clear()
            run_trials._current_champion.update(v1)

        try:
            def mock_run_games(challenger_params, champ_params, n_games, seed):
                # Simulate concurrent worker B promoting v2 while A is playing.
                with run_trials._lock:
                    run_trials._current_champion.clear()
                    run_trials._current_champion.update(v2)
                return (run_trials.PROMOTION_THRESHOLD, [])

            mock_trial = MagicMock()
            mock_trial.number = 99
            mock_trial.suggest_int.side_effect = (
                lambda k, lo, hi: int(PARAMS.get(k, lo))
            )
            mock_trial.suggest_float.side_effect = (
                lambda k, lo, hi: float(PARAMS.get(k, lo))
            )

            with patch("trials.run_trials.run_games", mock_run_games):
                with patch("trials.run_trials.write_champion") as mock_write:
                    run_trials.objective(mock_trial)

            # Stale challenger must not overwrite the stronger champion v2.
            mock_write.assert_not_called()
            assert run_trials._current_champion == v2
        finally:
            with run_trials._lock:
                run_trials._current_champion.clear()
                run_trials._current_champion.update(original)
