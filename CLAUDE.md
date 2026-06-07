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

1. Run `uv run python trials/run_trials.py` — promotes challengers to `trials/champion.py` when their win rate meets `PROMOTION_THRESHOLD` in `trials/run_trials.py` (currently ≥65%)
2. Copy winning params into `src/config.py` PARAMS
3. Run `python build.py` then submit

After any significant simulator change: **delete `trials/study.db` first** to clear stale Bayesian priors.

### Tuned-constant update rule

Whenever a tuned constant changes value (e.g. `PROMOTION_THRESHOLD` or `N_GAMES`):

1. **grep the entire repo** for the old value in every representation — both the percent form (e.g. `65%`) and the decimal form (e.g. `0.65`) — and update every live reference, including files under `.claude/docs/`.
2. **Cite constants by name** in new or edited docs (e.g. "see `PROMOTION_THRESHOLD` in `trials/run_trials.py`") instead of hardcoding the number, so docs cannot silently drift when the value changes.
3. **Exemption**: intentionally-dated snapshots in `archive/` or `superpowers/` preserve the historical figure on purpose and need not be updated.

### Pending re-tune: multi-fleet defense aggregation

Inbound fleets are now aggregated per planet before defense scaling, so
`defense_incoming_multiplier` (`src/config.py`) multiplies the _combined_ incoming
ships rather than a single fleet's. The defensive params in `src/config.py` were
tuned against the old per-fleet behavior and **must NOT be promoted until re-tuned**.
To re-tune:

1. `rm trials/study.db` — clear stale Bayesian priors
2. `uv run python trials/run_trials.py` — run fresh Optuna self-play tuning
3. Copy the winning params into `src/config.py` PARAMS
4. `python build.py` then submit
