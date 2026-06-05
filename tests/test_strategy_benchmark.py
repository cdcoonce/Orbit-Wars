"""Deterministic self-play regression gate for strategy changes.

The fast unit suite verifies decision logic in isolation, but no unit test can
tell whether a change to `plan_moves` (or `PARAMS`) makes the bot *play* better
or worse. This benchmark closes that gap: it pits the CURRENT strategy against a
frozen snapshot of the last accepted strategy (`trials.baseline.BASELINE_PARAMS`)
over a fixed-seed batch of paired self-play games, and fails if play regresses.

Why it is trustworthy as a gate:
  - **Deterministic.** A fixed seed makes the result identical on every run, so an
    unrelated change (PARAMS/plan_moves untouched) yields the same score every
    time and never flaps. Only a change that actually moves play moves the score.
  - **Draw-aware.** Score = (wins + 0.5*draws)/games — the standard chess scoring.
    Baseline-vs-itself scores exactly 0.50 regardless of the draw rate; a real
    regression shows up as wins < losses and pulls the score down.
  - **Map-luck cancelled.** `run_games(seed=...)` plays paired games on each map
    with the challenger's side swapped, so starting-position luck cancels.

This test is marked `benchmark` and is EXCLUDED from the default `pytest` run
(see pyproject `addopts`). Run it explicitly with `pytest -m benchmark`. The afk
executor's gate runs it via the repo's `.afk/config.toml` test_command, so a
strategy slice that regresses play is caught before it can reach a PR.

When you intentionally accept a strategy improvement, update
`trials/baseline.py` to the new `PARAMS` in the same commit that ships it.
"""

import pytest

from src.config import PARAMS
from trials.baseline import BASELINE_PARAMS
from trials.game_runner import run_games

# Fixed for reproducibility: 100 paired games over 50 distinct seeded maps.
BENCHMARK_GAMES = 100
BENCHMARK_SEED = 42
# Baseline-vs-itself scores exactly 0.50; floor allows a small noise band but
# catches any genuine regression (wins < losses).
REGRESSION_FLOOR = 0.45


@pytest.mark.benchmark
def test_current_strategy_does_not_regress_vs_baseline():
    """Current strategy must not play worse than the frozen baseline snapshot."""
    _win_rate, results = run_games(
        dict(PARAMS), dict(BASELINE_PARAMS),
        n_games=BENCHMARK_GAMES, seed=BENCHMARK_SEED,
    )
    wins = results.count("challenger")
    losses = results.count("champion")
    draws = results.count("draw")
    score = (wins + 0.5 * draws) / len(results)

    assert score >= REGRESSION_FLOOR, (
        f"strategy regressed vs baseline: score={score:.3f} "
        f"(W={wins} L={losses} D={draws}); floor={REGRESSION_FLOOR}. "
        f"If this change is an intentional improvement, update trials/baseline.py "
        f"to the new PARAMS in this commit."
    )
