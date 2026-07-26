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

## Simulator Correctness

### Boundary-split guard rule

When a single `<=` (or `>=`) guard on a boundary value is decomposed into multiple
`if`/`elif` branches (e.g. `> 0`, `== 0`, `else`), follow these two rules:

1. **Equality branches must test the exact boundary (`== 0`), never a loose `elif`.**
   A loose `elif winner == planet.owner` silently fires when `surviving < 0` — the
   incumbent may be the largest _single_ stack yet still lose to the _combined_
   attackers. The strictly-negative case must either fall through to the `else`
   branch or be handled explicitly. Using `elif surviving == 0 and winner == planet.owner`
   (exact boundary) prevents the silent capture.

   _Motivating failure:_ PR #72 combat-resolution in `step_state` — an
   `elif winner == planet.owner` branch fired on `surviving < 0` (10 vs 6+6 = −2),
   incorrectly retaining the planet for the incumbent. Fix: guard on
   `surviving == 0` exactly.

2. **Every such split must ship a regression test covering the strictly-negative
   (or strictly-greater) case**, not just the boundary value itself. A test that
   only exercises `surviving == 0` cannot catch a guard that also fires for
   `surviving < 0`.

   _Example:_ `test_incumbent_largest_stack_but_loses_to_combined_attackers` in
   `tests/test_lookahead.py` — owner=0 holds 10 ships, owners 1 and 2 each send 6
   (combined 12 > 10, `surviving = −2`) — the planet must go neutral.

## Python Conventions

### Named-field records, not positionally-indexed lists

A value holding a **fixed set of distinct named fields** must be represented as a
tuple (rebuilt via named unpacking) or a small named structure (`NamedTuple` /
`dataclass`) — never a mutable `list` mutated via positional indices like
`agg[0]`/`agg[1]`.

- **Anti-pattern**: `agg = [0, math.inf]; agg[0] += ships; agg[1] = min(agg[1], eta)`.
  The positional `[0]`/`[1]` access is implicit — a reader can't tell what slot 0
  means without tracing every write site — and it is edit-fragile: inserting or
  reordering a field silently swaps the meaning of every existing index.
- **Fix**: model the record as an explicit tuple with named unpacking, e.g.
  `prev_ships, prev_eta = inbound_by_planet[planet.id]` then rebuild
  `inbound_by_planet[planet.id] = (prev_ships + ships, min(prev_eta, eta))`. Named
  unpacking is self-documenting: the field names are visible at every read and
  write site.

  _Motivating failure:_ PR #85's `detect_threats` accumulator stored a fixed
  two-field record (summed ships, earliest ETA) as `agg: list[int]` mutated via
  `agg[0]`/`agg[1]`. The fix replaced it with an explicit `(ships, eta)` 2-tuple.

- **Scope**: this rule targets fixed-arity records of _distinct_ fields (a
  ships-count paired with an ETA, a min/max pair, etc.), not genuine homogeneous
  collections — a `list[Fleet]` or `list[int]` of same-meaning elements is still
  the right type and is unaffected by this rule.

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
4. **When editing a doc section that enumerates constants from a single source file, re-verify ALL enumerated constants against that file in the same edit** — not just the one you came to change. Acceptance-criteria bullet lists and inline plan-doc numbers are in scope, not just headline prose values (both drifted in PR #72 even after the prose was fixed). For example, fixing `PROMOTION_THRESHOLD` in a section that also lists `N_GAMES` from `trials/run_trials.py` requires re-checking `N_GAMES` in the same edit; leaving adjacent constants unverified contradicts the cite-by-name rule above.

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
