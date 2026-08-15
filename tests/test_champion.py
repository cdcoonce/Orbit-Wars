"""Tests for trials/champion.py CHAMPION_PARAMS integrity."""

from conftest import assert_covers_params


class TestChampionParams:
    def test_contains_every_params_key(self):
        """CHAMPION_PARAMS must hold every key strategy.py indexes with params[...].

        plan_moves/plan_expansion read params via bracket indexing (not .get),
        so a missing key raises KeyError every turn and game_runner silently
        scores all games as draws.  See also TestOriginalDefaults in test_benchmark.py.

        If this fails, the champion predates a new tunable.  Re-tune before use:
          rm trials/study.db
          uv run python trials/run_trials.py
          copy winners into src/config.py PARAMS
          python build.py && kaggle submit
        """
        from trials.champion import CHAMPION_PARAMS

        assert_covers_params(CHAMPION_PARAMS, "CHAMPION_PARAMS")
