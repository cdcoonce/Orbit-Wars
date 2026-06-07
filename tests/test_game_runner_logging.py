"""Tests that run_game logs worker exceptions while preserving draw-scoring."""
import concurrent.futures
import logging
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
