# Orbit Wars

Kaggle competition bot — captures the most ships by turn 500 across orbiting planets.
Full architecture details: [.claude/docs/project.md](.claude/docs/project.md)

## Runtime

**Always use `uv run`** for Python commands — the project pins Python 3.11 via `.python-version`.

```bash
uv run pytest tests/ --ignore=tests/test_trial_runner.py   # fast test suite (no optuna)
uv run pytest tests/ -v                                     # full suite (requires optuna)
uv run python run_game.py                                   # local game vs starter agent
uv run python trials/run_trials.py                         # Optuna self-play tuning (~30-60 min)
```

## Build & Submit

```bash
python build.py                                                              # → submission.py
kaggle competitions submit -c orbit-wars -f submission.py -m "description"  # submit to Kaggle
```

## Key Files

| File                  | Purpose                                                       |
| --------------------- | ------------------------------------------------------------- |
| `src/strategy.py`     | Core decision logic: `plan_moves`, classifiers, lookahead     |
| `src/lookahead.py`    | 1–2 turn simulator (`step_state`, `score_state`)              |
| `src/config.py`       | `PARAMS` (active defaults) + `PARAM_SPACE` (Optuna bounds)    |
| `trials/champion.py`  | Best known params — promoted automatically by `run_trials.py` |
| `trials/benchmark.py` | Quick champion vs original-defaults sanity check (20 games)   |

## Tuning Workflow

1. Run `uv run python trials/run_trials.py` — promotes challengers to `trials/champion.py` at ≥55% win rate
2. Copy winning params into `src/config.py` PARAMS
3. Run `python build.py` then submit

After any significant simulator change: **delete `trials/study.db` first** to clear stale Bayesian priors.
