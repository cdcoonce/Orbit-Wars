"""Optuna self-play trial runner.

Run from the project root:
    uv run python trials/run_trials.py
"""
import logging
import math
import os
from pathlib import Path

import optuna

from src.config import PARAM_SPACE, PARAMS
from trials.champion import CHAMPION_PARAMS
from trials.game_runner import run_games

N_GAMES = 10
N_WORKERS = 4
N_TRIALS = 200
PROMOTION_THRESHOLD = 0.55

STUDY_DB = Path(__file__).parent / "study.db"
CHAMPION_FILE = Path(__file__).parent / "champion.py"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_best_win_rate = 0.0


def write_champion(params: dict) -> None:
    """Atomically write params to champion.py via temp-file + os.replace."""
    for k, v in params.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"Non-finite value for param {k!r}: {v}")

    lines = ["CHAMPION_PARAMS = {\n"]
    for k, v in params.items():
        lines.append(f"    {k!r}: {v!r},\n")
    lines.append("}\n")

    temp = str(CHAMPION_FILE) + ".tmp"
    with open(temp, "w") as fh:
        fh.writelines(lines)
    os.replace(temp, CHAMPION_FILE)


def _make_callback():
    def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        global _best_win_rate
        win_rate = trial.value
        if win_rate is None:
            return
        if win_rate > _best_win_rate:
            _best_win_rate = win_rate
        promoted = " [PROMOTED]" if win_rate >= PROMOTION_THRESHOLD else ""
        logger.info(
            "Trial %d: win_rate=%.2f | best=%.2f%s",
            trial.number, win_rate, _best_win_rate, promoted,
        )

    return callback


def objective(trial: optuna.Trial) -> float:
    challenger_params: dict = {}
    for key, (low, high, typ) in PARAM_SPACE.items():
        if typ is int:
            challenger_params[key] = trial.suggest_int(key, low, high)
        else:
            challenger_params[key] = trial.suggest_float(key, low, high)
    challenger_params["game_length"] = CHAMPION_PARAMS.get("game_length", PARAMS["game_length"])

    win_rate, _ = run_games(challenger_params, CHAMPION_PARAMS, n_games=N_GAMES)

    if win_rate >= PROMOTION_THRESHOLD:
        write_champion(challenger_params)

    return win_rate


if __name__ == "__main__":
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        study_name="orbit_wars",
        storage=f"sqlite:///{STUDY_DB}",
        direction="maximize",
        load_if_exists=True,
    )

    study.optimize(
        objective,
        n_trials=N_TRIALS,
        n_jobs=N_WORKERS,
        callbacks=[_make_callback()],
    )

    best = study.best_trial
    print(f"Best trial: {best.number}, win_rate={best.value:.2f}")
    print(f"Best params: {best.params}")
