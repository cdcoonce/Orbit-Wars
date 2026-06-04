"""Tests for trials/game_runner.py and trials/run_trials.py."""
import concurrent.futures
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
                            params=None, comet_ids=None, initial_planets=None):
            captured.append(initial_planets)
            return []

        obs0 = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 0}
        obs1 = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 1}

        with patch("trials.game_runner.plan_moves", mock_plan_moves):
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
                            params=None, comet_ids=None, initial_planets=None):
            initial_planets_seen.append(initial_planets)
            return []

        obs0 = {"planets": [], "fleets": [], "player": 0, "angular_velocity": 0.03, "step": 0}

        agent_a = make_agent(PARAMS)
        agent_b = make_agent(PARAMS)

        with patch("trials.game_runner.plan_moves", mock_plan_moves):
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
        """A game exceeding the timeout must return 'draw' without raising."""
        from trials.game_runner import run_game

        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()

        mock_executor = MagicMock()
        mock_executor.__enter__ = MagicMock(return_value=mock_executor)
        mock_executor.__exit__ = MagicMock(return_value=False)
        mock_executor.submit.return_value = mock_future

        with patch("concurrent.futures.ThreadPoolExecutor", return_value=mock_executor):
            result = run_game(PARAMS, PARAMS)

        assert result == "draw"


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
