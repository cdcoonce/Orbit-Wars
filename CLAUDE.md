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

## Doc-Invariant Test Conventions

Tests that assert "no doc references the old value X" must follow three rules (see issue #97 for the PR #72 failure modes that motivated this):

1. **Match all value representations.** Check every encoding of the guarded value
   — percent form (e.g. `65%`), decimal form (e.g. `0.65`), and any other
   representation in use. Scanning for a single literal allows other forms to slip
   through undetected (in PR #72 the percent-form guard missed the decimal form
   `0.55` in living docs).

2. **Scan the full repo.** The test must walk the entire repository. Any excluded
   directory (e.g. dated `archive/` or `superpowers/` snapshots that are historical
   records, not living docs) must be listed in an exclusion set with a comment
   explaining why the exclusion is valid. Silent omission of a directory is not
   acceptable even when that directory holds the stale value.

3. **Document CI limitations explicitly.** When a doc tree cannot be governed from
   CI — for example, the Claude Code harness auto-denies edits to `.claude/`, so
   `.claude/docs/project.md` cannot be policed by a pytest assertion — add a comment
   in the test explaining the limitation and what manual action is required. Do not
   silently exclude ungovernable trees; document the gap so maintainers know to fix
   those files by hand.
