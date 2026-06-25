"""Optuna self-play trial runner.

Run from the project root:
    uv run python trials/run_trials.py
"""
import hashlib
import logging
import math
import os
import shutil
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

STUDY_NAME = "orbit_wars"
# user_attr key under which each study records the PARAM_SPACE fingerprint it
# was created against, so a later run can refuse to resume a stale study.
FINGERPRINT_ATTR = "param_space_fingerprint"

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

    # Derive a per-trial base seed from trial.number so every trial is
    # reproducible and its paired games share generated maps. Scale by N_GAMES
    # so distinct trials never reuse another trial's map seeds.
    win_rate, _ = run_games(
        challenger_params, current_champ, n_games=N_GAMES,
        seed=trial.number * N_GAMES,
    )

    if win_rate >= PROMOTION_THRESHOLD:
        with _lock:
            # Guard against the stale-snapshot race: worker B may have promoted a
            # stronger champion (v2) while this trial was playing its games against
            # the old champion (v1). Re-check that the live champion is still the
            # one we benchmarked against before committing. If it has changed, skip
            # this promotion — the win_rate is stale and cannot justify overwriting
            # a champion the challenger never faced.
            # Trade-off: some valid promotions are dropped under heavy concurrency,
            # but the champion can never regress to a weaker, unvalidated challenger.
            if _current_champion != current_champ:
                return win_rate
            write_champion(challenger_params)
            _current_champion.clear()
            _current_champion.update(challenger_params)

    return win_rate


def param_space_fingerprint() -> str:
    """Return a stable SHA-256 digest of the current PARAM_SPACE bounds.

    Keyed to the sorted ``(name, (low, high, type))`` items, so any change to a
    bound, a key, or a parameter type yields a different fingerprint. Uses
    hashlib rather than the builtin ``hash()`` because ``hash()`` is salted per
    process (PYTHONHASHSEED) and would not be comparable across runs.
    """
    payload = repr(sorted(PARAM_SPACE.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stored_fingerprint(storage_url: str) -> str | None:
    """Read the fingerprint recorded on an existing study, or None if absent."""
    try:
        study = optuna.load_study(study_name=STUDY_NAME, storage=storage_url)
    except KeyError:
        return None  # storage exists but holds no study of this name
    return study.user_attrs.get(FINGERPRINT_ATTR)


def _archive_stale_db(db_path: Path) -> Path:
    """Move a stale study DB aside (never overwriting) and return the archive path."""
    archive = db_path.with_name(db_path.name + ".stale")
    n = 1
    while archive.exists():
        archive = db_path.with_name(f"{db_path.name}.stale.{n}")
        n += 1
    shutil.move(str(db_path), str(archive))
    return archive


def load_guarded_study(db_path: Path, *, reset: bool = False) -> "optuna.Study":
    """Create or resume the study, refusing to resume across a PARAM_SPACE change.

    Optuna's sampler builds Bayesian priors keyed to the PARAM_SPACE it sampled.
    Resuming a study whose priors target a different space silently corrupts the
    run (the documented "delete study.db first" foot-gun). We fingerprint
    PARAM_SPACE and, on a mismatch (or when ``reset`` is set), archive the stale
    DB and start fresh rather than resume. A matching fingerprint resumes exactly
    as before. A pre-existing study with no recorded fingerprint is backfilled
    with the current one rather than archived.
    """
    storage_url = f"sqlite:///{db_path}"
    current_fp = param_space_fingerprint()

    if db_path.exists():
        if reset:
            archive = _archive_stale_db(db_path)
            logger.info("Reset requested — archived %s to %s.", db_path.name, archive.name)
        else:
            existing_fp = _stored_fingerprint(storage_url)
            if existing_fp is not None and existing_fp != current_fp:
                archive = _archive_stale_db(db_path)
                logger.info(
                    "PARAM_SPACE fingerprint mismatch (study=%s…, current=%s…) — "
                    "archived stale %s to %s and starting fresh.",
                    existing_fp[:12], current_fp[:12], db_path.name, archive.name,
                )

    study = optuna.create_study(
        study_name=STUDY_NAME,
        storage=storage_url,
        direction="maximize",
        load_if_exists=True,
    )
    if study.user_attrs.get(FINGERPRINT_ATTR) is None:
        study.set_user_attr(FINGERPRINT_ATTR, current_fp)
    return study


if __name__ == "__main__":
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = load_guarded_study(STUDY_DB, reset="--reset" in sys.argv[1:])

    study.optimize(
        objective,
        n_trials=N_TRIALS,
        n_jobs=N_WORKERS,
        callbacks=[_make_callback()],
    )

    best = study.best_trial
    print(f"Best trial: {best.number}, win_rate={best.value:.2f}")
    print(f"Best params: {best.params}")
