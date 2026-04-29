"""Optuna self-play trial runner.

Run from the project root:
    uv run python trials/run_trials.py
"""
import logging
import math
import os
import sys
import threading
from pathlib import Path

# Add project root to sys.path so src/ and trials/ are importable as packages
# when this script is run directly (python -m sets this up automatically;
# direct script execution does not).
sys.path.insert(0, str(Path(__file__).parent.parent))

import optuna

from src.config import PARAM_SPACE, PARAMS
from trials.champion import CHAMPION_PARAMS
from trials.game_runner import run_games

N_GAMES = 40
N_WORKERS = 4
N_TRIALS = 200
PROMOTION_THRESHOLD = 0.65

STUDY_DB = Path(__file__).parent / "study.db"
CHAMPION_FILE = Path(__file__).parent / "champion.py"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Mutable in-process champion state; updated on every promotion.
# Protected by _lock so parallel workers always read the latest champion.
_lock = threading.Lock()
_current_champion: dict = dict(CHAMPION_PARAMS)
_best_win_rate: float = 0.0


def write_champion(params: dict) -> None:
    """Atomically write params to champion.py via temp-file + os.replace.

    Must be called while holding _lock to avoid concurrent temp-file collision.
    """
    for k, v in params.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"Non-finite value for param {k!r}: {v}")

    lines = ["CHAMPION_PARAMS = {\n"]
    for k, v in params.items():
        lines.append(f"    {k!r}: {v!r},\n")
    lines.append("}\n")

    # Per-thread temp name prevents concurrent write collisions.
    temp = str(CHAMPION_FILE) + f".{threading.get_ident()}.tmp"
    with open(temp, "w") as fh:
        fh.writelines(lines)
    os.replace(temp, CHAMPION_FILE)


def _make_callback():
    def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        global _best_win_rate
        win_rate = trial.value
        if win_rate is None:
            return
        with _lock:
            if win_rate > _best_win_rate:
                _best_win_rate = win_rate
            local_best = _best_win_rate
        promoted = " [PROMOTED]" if win_rate >= PROMOTION_THRESHOLD else ""
        try:
            logger.info(
                "Trial %d: win_rate=%.2f | best=%.2f%s",
                trial.number, win_rate, local_best, promoted,
            )
        except (ValueError, OSError):
            pass  # stderr closed during process teardown

    return callback


def objective(trial: optuna.Trial) -> float:
    # Build challenger from full PARAMS defaults so no key is ever missing.
    challenger_params = dict(PARAMS)
    for key, (low, high, typ) in PARAM_SPACE.items():
        if typ is int:
            challenger_params[key] = trial.suggest_int(key, low, high)
        else:
            challenger_params[key] = trial.suggest_float(key, low, high)

    with _lock:
        current_champ = dict(_current_champion)

    win_rate, _ = run_games(challenger_params, current_champ, n_games=N_GAMES)

    if win_rate >= PROMOTION_THRESHOLD:
        with _lock:
            write_champion(challenger_params)
            _current_champion.clear()
            _current_champion.update(challenger_params)

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
