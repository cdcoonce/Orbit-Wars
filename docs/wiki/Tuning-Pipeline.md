## Overview

Optuna samples a challenger parameter dict from `PARAM_SPACE`, runs `N_GAMES` self-play games (challenger vs the current champion, with alternating player assignment to neutralise first-move bias), computes win rate, and — if `win_rate >= PROMOTION_THRESHOLD` — atomically overwrites `trials/champion.py` with the new params and updates the in-process `_current_champion` dict so subsequent trials immediately compete against the promoted challenger. This repeats for `N_TRIALS` trials across `N_WORKERS` parallel workers, persisting Bayesian priors in `study.db` between sessions. See [Home](Home.md) for top-level orientation and [src/config](src/config.md) for param definitions.

## Constants

All live in `trials/run_trials.py`:

| Constant              | Value | Meaning                                  |
| --------------------- | ----- | ---------------------------------------- |
| `N_GAMES`             | 20    | Games per trial (challenger vs champion) |
| `N_WORKERS`           | 4     | Parallel Optuna jobs (`n_jobs`)          |
| `N_TRIALS`            | 200   | Total trials per `study.optimize()` call |
| `PROMOTION_THRESHOLD` | 0.55  | Minimum win rate to promote challenger   |

## `objective(trial)`

Optuna calls `objective` with an `optuna.Trial` handle. The function:

1. Builds `challenger_params` by starting from `PARAMS` defaults (so every key exists even if not in `PARAM_SPACE`), then calls `trial.suggest_int` or `trial.suggest_float` for each key in `PARAM_SPACE` according to the `(low, high, typ)` tuple stored there.
2. Reads `_current_champion` under `_lock` (snapshot; avoids a mid-read promotion from another worker).
3. Calls `run_games(challenger_params, current_champ, n_games=N_GAMES)` → `(win_rate, results)`.
4. If `win_rate >= PROMOTION_THRESHOLD`: acquires `_lock`, calls `write_champion(challenger_params)`, clears and repopulates `_current_champion`.
5. Returns `win_rate` — Optuna maximises this value and updates its Bayesian model.

## Atomic promotion (`write_champion`)

**Why it matters:** `N_WORKERS=4` means four threads can reach a promotion simultaneously. Two threads writing `champion.py` at the same moment would produce a partially-written file.

**How it works:**

```python
# Per-thread temp name prevents concurrent temp-file collision
temp = str(CHAMPION_FILE) + f".{threading.get_ident()}.tmp"
with open(temp, "w") as fh:
    fh.writelines(lines)
os.replace(temp, CHAMPION_FILE)   # atomic on POSIX (rename syscall)
```

- `threading.get_ident()` in the temp filename means two threads writing simultaneously produce two distinct temp files — no interleaving.
- `os.replace()` is a single POSIX `rename(2)` syscall: readers either see the old file or the new file, never a partial write.
- `write_champion` is always called while the caller holds `_lock`, so the entire read-modify-write of `_current_champion` is serialised.
- `write_champion` validates that no **float** param value is non-finite (`math.isfinite`) before writing, guarding against Optuna suggesting `inf`/`nan`. Integer params are not checked (Optuna's `suggest_int` cannot produce non-finite values).

## When to delete `study.db`

**Delete `study.db` after any simulator change** — specifically after touching `step_state` step order, scoring weights, combat resolution, or any logic that changes what a param value means at runtime.

**Why:** `study.db` stores Optuna's Gaussian Process surrogate model, which encodes which regions of `PARAM_SPACE` produced high win rates under the _old_ simulator. After a simulator change those priors are wrong: parameters that were optimal before may now be suboptimal (or vice versa). Running on stale priors slows convergence and can guide Optuna toward false optima. A fresh study starts from scratch with correct observations.

```bash
rm trials/study.db
uv run python trials/run_trials.py
```

If `study.db` does not exist, `load_if_exists=True` causes Optuna to create a fresh study automatically — no manual setup required.

## Game runner (`run_games`)

`trials/game_runner.py::run_games` executes `n_games` serially:

```python
for i in range(n_games):
    result = run_game(challenger_params, champion_params, challenger_player=i % 2)
```

- `challenger_player=i % 2` alternates who plays as player 0 (first-mover). Over 20 games the challenger plays 10 games as P0 and 10 as P1 — any first-move advantage cancels out.
- Each `run_game` spawns a `ThreadPoolExecutor(max_workers=1)` and enforces `timeout=60s`. A timeout or uncaught exception returns `"draw"`, preventing a hanging game from blocking an Optuna worker indefinitely.
- Each agent closure captures its own `initial_planets` state so parallel games don't share mutable caches.
- Win rate = `wins / n_games` (draws count as zero wins for the challenger).

## How to run

```bash
# Full tuning run (~30-60 min)
uv run python trials/run_trials.py

# Quick sanity check: champion vs original hand-tuned defaults (20 games)
uv run python trials/benchmark.py
```

`run_trials.py` prints a one-line summary per trial: `Trial N: win_rate=X.XX | best=Y.YY [PROMOTED]`. The `[PROMOTED]` tag appears whenever a challenger meets the threshold.

## Interpreting benchmark results

`benchmark.py` runs `CHAMPION_PARAMS` (challenger role) against `ORIGINAL_DEFAULTS` for 20 games and prints `W/D/L`:

```text
Champion vs original defaults: 70%  (14W / 0D / 6L)
```

| Win rate    | Interpretation                                                                                  |
| ----------- | ----------------------------------------------------------------------------------------------- |
| > 0.55      | Champion is statistically better than the original defaults — healthy                           |
| 0.45 – 0.55 | Uncertain; too close to call with 20 games                                                      |
| < 0.45      | Regression — the current champion may be worse than original tuning; investigate recent changes |

A regression usually means a simulator change shifted the landscape and the promoted champion was tuned on the old code. Delete `study.db` and re-run.

## After tuning

1. Copy the winning params from `trials/champion.py` (`CHAMPION_PARAMS` dict) into `src/config.py` `PARAMS`.
2. Run `python build.py` to regenerate `submission.py`.
3. Submit: `kaggle competitions submit -c orbit-wars -f submission.py -m "description"`.

## Gotchas

**In-process champion vs on-disk champion:** `_current_champion` is updated in-process on promotion so subsequent trials in the same run immediately compete against the latest promoted params. But `champion.py` on disk is what persists across separate runs. If a run is interrupted mid-trial, restarting picks up `champion.py` from disk — no partial in-process state to recover. Bayesian priors from `study.db` still apply (unless you deleted it).

**`game_length` is not in `PARAM_SPACE`:** it is fixed at 500 in both `PARAMS` and `CHAMPION_PARAMS` and is not sampled. Do not add it to `PARAM_SPACE` — the Kaggle environment controls game length.

**`min_garrison_early` vs `min_garrison`:** these interact. Optuna samples them independently; if `min_garrison_early` ends up higher than `min_garrison`, the ramp logic in `strategy.py` may behave unexpectedly. The current bounds (`1–15` vs `5–30`) make this unlikely but not impossible.
