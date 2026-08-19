"""Tests that run_game logs worker exceptions while preserving draw-scoring."""
import concurrent.futures
import logging
from concurrent.futures.process import BrokenProcessPool
from unittest.mock import MagicMock, patch

from src.config import PARAMS


class TestRunGameExceptionLogging:
    def test_injected_exception_is_swallowed_and_logged(self, caplog):
        """An injected non-timeout exception is both swallowed (returns 'draw') and logged."""
        from trials.game_runner import run_game

        mock_future = MagicMock()
        mock_future.result.side_effect = KeyError("missing_param")

        mock_pool = MagicMock()
        mock_pool.submit.return_value = mock_future

        with patch("trials.game_runner._get_pool", return_value=mock_pool), \
             caplog.at_level(logging.ERROR, logger="trials.game_runner"):
            result = run_game(PARAMS, PARAMS)

        assert result == "draw"
        assert len(caplog.records) >= 1
        assert "KeyError" in caplog.text or "missing_param" in caplog.text

    def test_timeout_is_silent_draw(self, caplog):
        """TimeoutError path remains a separate, silent draw — no error logged."""
        from trials.game_runner import run_game

        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()

        mock_pool = MagicMock()
        mock_pool.submit.return_value = mock_future

        with patch("trials.game_runner._get_pool", return_value=mock_pool), \
             caplog.at_level(logging.WARNING, logger="trials.game_runner"):
            result = run_game(PARAMS, PARAMS)

        assert result == "draw"
        assert len(caplog.records) == 0


class TestRunGameBrokenPoolRecovery:
    def test_broken_pool_on_submit_is_swallowed_and_scored_draw(self, caplog):
        """A BrokenProcessPool raised from submit() (not future.result()) is caught."""
        import trials.game_runner as game_runner

        mock_pool = MagicMock()
        mock_pool.submit.side_effect = BrokenProcessPool("worker process died")

        with patch("trials.game_runner._get_pool", return_value=mock_pool), \
             caplog.at_level(logging.ERROR, logger="trials.game_runner"):
            result = game_runner.run_game(PARAMS, PARAMS)

        assert result == "draw"

    # Pool-reset-and-rebuild coverage (including the log-level assertions)
    # lives in test_trial_runner.py::TestRunGameBrokenPoolSelfHeals
    # ::test_poisoned_pool_is_replaced_and_next_call_gets_real_result, which
    # exercises the same scenario plus the rebuild-budget globals.
