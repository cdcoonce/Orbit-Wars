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

    def test_broken_pool_is_reset_so_next_call_gets_a_fresh_pool(self, caplog):
        """After a broken pool is caught, _pool is cleared so _get_pool() rebuilds it."""
        import trials.game_runner as game_runner

        broken_pool = MagicMock()
        broken_pool.submit.side_effect = BrokenProcessPool("worker process died")

        fresh_future = MagicMock()
        fresh_future.result.return_value = "challenger"
        fresh_pool = MagicMock()
        fresh_pool.submit.return_value = fresh_future

        game_runner._pool = broken_pool
        try:
            with patch(
                "trials.game_runner.concurrent.futures.ProcessPoolExecutor",
                return_value=fresh_pool,
            ), caplog.at_level(logging.ERROR, logger="trials.game_runner"):
                first_result = game_runner.run_game(PARAMS, PARAMS)
                assert first_result == "draw"
                assert game_runner._pool is None

                second_result = game_runner.run_game(PARAMS, PARAMS)
                assert second_result == "challenger"
                assert game_runner._pool is fresh_pool
        finally:
            game_runner._pool = None
