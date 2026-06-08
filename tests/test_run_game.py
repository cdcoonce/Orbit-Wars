"""Tests for run_game.py winner-summary logic.

run_game.py is a dev script, so the game code is guarded by
``if __name__ == "__main__":``. Importing the module is safe and gives
access to the pure ``format_game_result`` helper.
"""
from run_game import format_game_result


class TestFormatGameResult:
    def test_player0_wins(self):
        assert format_game_result(7, 3) == "Result: our agent WINS (reward 7 vs 3)"

    def test_player1_wins(self):
        assert format_game_result(3, 7) == "Result: starter WINS (reward 3 vs 7)"

    def test_draw(self):
        assert format_game_result(5, 5) == "Result: DRAW (reward 5 vs 5)"

    def test_zero_rewards_draw(self):
        assert format_game_result(0, 0) == "Result: DRAW (reward 0 vs 0)"

    def test_winner_uses_reward_comparison_not_truthiness(self):
        """reward=0 for our agent with reward=0 for starter is a draw, not starter wins."""
        result = format_game_result(0, 0)
        assert "DRAW" in result
        assert "our agent" not in result or "WINS" not in result
