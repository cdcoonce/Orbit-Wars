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

**`submission.py` is generated, and every `src/` change must regenerate it.** It is
the bundle that actually ships to Kaggle, and
`tests/test_build.py::test_committed_submission_matches_fresh_build` compares the
committed copy against a fresh build, so a `src/` change that skips `build.py`
fails the suite. Run `uv run python build.py` and commit the result **in the same
change** — it is a required artifact of that change, never an unrelated file and
never scope creep, even when an issue names only the `src/` file. Never hand-edit
`submission.py` to mimic a build; a hand-written bundle can silently diverge from
`src/`, and the bundle is what ships.

Agents: `uv run python build.py` is the spelling granted in `.afk/config.toml`
`allowed_tools`. Other spellings are refused by the permission harness.

Any issue that touches `src/` should say so in its own scope: name `submission.py`
alongside the `src/` file. Reviewers see only the issue body and the diff, so an
undeclared regenerated bundle reads to them as scope creep (this deadlocked #116
and #120 — the build was required by the suite and rejected by the reviewer).

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

## Cite Code-Derived Values by Name

Living docs — everything outside the dated `archive/` and `superpowers/` snapshots — must
cite a code-derived value by its symbol name and source file (e.g. "see `PROMOTION_THRESHOLD`
in `trials/run_trials.py`") rather than transcribing the number. When a number genuinely must
appear (e.g. a worked example), annotate it with the source symbol so a drift scan can find it.

**Value classes in scope**: `PARAMS` defaults (`src/config.py`), tuning constants
(`trials/run_trials.py`), test counts, and formula constants.

**Every representation is in scope**: prose, bullet lists, tables, and acceptance-criteria
checklists are all equally in scope — not just headline prose. PR #72 fixed its prose but left
an acceptance-criteria bullet hardcoding the stale `PROMOTION_THRESHOLD` win-rate figure
alongside the already-corrected prose above it.

**Exemption**: intentionally-dated snapshots in `archive/` and `superpowers/` preserve
historical figures on purpose, as a record of what was true at the time, and are exempt from
this rule.

## Tuning Workflow

1. Run `uv run python trials/run_trials.py` — promotes challengers to `trials/champion.py` when their win rate meets `PROMOTION_THRESHOLD` in `trials/run_trials.py`
2. Copy winning params into `src/config.py` PARAMS
3. Run `python build.py` then submit

After any significant simulator change: **delete `trials/study.db` first** to clear stale Bayesian priors.

### Tuned-constant update rule

Whenever a tuned constant changes value (e.g. `PROMOTION_THRESHOLD` or `N_GAMES`):

1. **grep the entire repo** for the old value in every representation — both the percent form (e.g. `65%`) and the decimal form (e.g. `0.65`) — and update every live reference, including files under `.claude/docs/`.
2. **Cite constants by name** — see [Cite Code-Derived Values by Name](#cite-code-derived-values-by-name) above; this rule is a specific instance of that broader convention.
3. **Exemption**: intentionally-dated snapshots in `archive/` or `superpowers/` preserve the historical figure on purpose and need not be updated.
4. **When editing a doc section that enumerates constants from a single source file, re-verify ALL enumerated constants against that file in the same edit** — not just the one you came to change. Acceptance-criteria bullet lists and inline plan-doc numbers are in scope, not just headline prose values (both drifted in PR #72 even after the prose was fixed). For example, fixing `PROMOTION_THRESHOLD` in a section that also lists `N_GAMES` from `trials/run_trials.py` requires re-checking `N_GAMES` in the same edit; leaving adjacent constants unverified contradicts the cite-by-name rule above.

### Semantics-change re-tune rule

Any PR that changes simulator/scoring/threat-detection semantics in a way that
alters what a tuned `PARAMS` entry (`src/config.py`) affects MUST take three
actions:

1. **Add an inline coupling note** at the constant's definition in `src/config.py`
   explaining what changed and why the constant's meaning shifted.
2. **Document the re-tune workflow**, including `rm trials/study.db` to clear
   stale Bayesian priors before re-running `uv run python trials/run_trials.py`.
3. **Explicitly flag the affected params as not-for-promotion** until re-tuned —
   a challenger built on stale semantics must not be promoted, even if it clears
   `PROMOTION_THRESHOLD`.

_Motivating example:_ PR #85 changed `detect_threats` to aggregate converging
enemy fleets per planet before defense scaling, which changed
`defense_incoming_multiplier` (`src/config.py`) from multiplying a single
fleet's incoming ships to multiplying the _combined_ incoming ships across all
attackers. See "Pending re-tune: multi-fleet defense aggregation" below for the
concrete instance of this rule currently in effect.

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

### Pending re-tune: lookahead launch-before-rotation ordering

`step_state` and `step_state_multi` (`src/lookahead.py`) now launch fleets
before production and planet rotation, matching the engine's step order
(`orbit_wars.py` interpreter: Fleet Launch precedes Production and Planet
Movement & Sweep). Previously the simulator rotated the source planet first, so
every simulated launch angle was applied from a position the engine would never
use. This changes the trajectories the lookahead scores, which changes what the
`lookahead_turns`, `lookahead_blend`, and `lookahead_ship_weight` params
(`src/config.py`) were tuned against. Those params **must NOT be promoted until
re-tuned**. To re-tune:

1. `rm trials/study.db` — clear stale Bayesian priors
2. `uv run python trials/run_trials.py` — run fresh Optuna self-play tuning
3. Copy the winning params into `src/config.py` PARAMS
4. `python build.py` then submit

### Pending re-tune: lookahead in-transit ship counting

`score_state` (`src/lookahead.py`) now counts in-transit fleet ships toward
`my_ships`/`enemy_ships`, not just planet-held ships, matching
`src/endgame.py`'s `total_ships`. This changes what those totals measure,
which changes what the `lookahead_turns`, `lookahead_blend`, and
`lookahead_ship_weight` params (`src/config.py`) were tuned against. Those
params **must NOT be promoted until re-tuned** via #117. See the `NOTE (#256)`
at their definition in `src/config.py` for the inline coupling note. To
re-tune:

1. `rm trials/study.db` — clear stale Bayesian priors
2. `uv run python trials/run_trials.py` — run fresh Optuna self-play tuning
3. Copy the winning params into `src/config.py` PARAMS
4. `python build.py` then submit

## Doc-Invariant Test Conventions

Tests that assert "no doc references the old value X" must follow five rules (see issue #97 for the PR #72 failure modes that motivated this):

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

4. **Any documented constant value must be name-cited or pinned by an importing test.**
   A doc that quotes the literal value of a constant exported from
   `trials/run_trials.py` or `src/config.py` `PARAMS` — rather than citing the
   constant by name — must be covered by a doc-invariant test that imports the
   constant from its source module and asserts the documented value matches.
   Prefer a single parametrized test that iterates the known source-of-truth
   constants over N hand-written per-constant tests, so a newly-documented
   constant is guarded by default instead of requiring someone to remember to
   author another bespoke test.

   _Motivating failure:_ PR #72 surfaced this same failure mode twice in one PR.
   `docs/wiki/Tuning-Pipeline.md` said `N_GAMES` was `20` while
   `trials/run_trials.py` set it to `40`, even though the wiki's own Constants
   table comment claimed the constants "All live in `trials/run_trials.py`" —
   that comment promised centralization but nothing actually verified the
   documented number against the code. `test_docs_promotion_threshold.py` and
   `test_tuned_constant_convention.py` fixed the `PROMOTION_THRESHOLD` and
   `N_GAMES` drift by hand, one bespoke test per constant; this rule generalizes
   so the next drifted constant doesn't need its own hand-written guard.

5. **Verify and clean excluded directories — documenting them is not enough.**
   When a doc-scan test excludes a directory it cannot police (e.g. `.claude/`,
   `.afk/`), the same change must manually `grep` that directory for the guarded
   value and fix any stale occurrences found, in addition to satisfying rule 3.
   The exclusion comment must record that the directory was **verified clean as
   of `<commit/PR>`** — naming the CI limitation alone, without confirming the
   excluded tree is actually free of the stale value, is not sufficient.

   _Motivating failure:_ PR #72's `test_no_doc_references_old_55_percent`
   excluded `.claude/` from its scan and documented the CI limitation, but
   `.claude/docs/project.md` still carried the stale promotion-threshold figure
   the test is named for — so that test's acceptance criterion was never
   actually enforced for the full repository, and the stale value could persist
   indefinitely because nothing ever grepped the excluded tree to confirm it was
   clean.

## Copilot Review Instructions

`.github/copilot-instructions.md` restates the conventions on this page in
reviewer-facing form (boundary-split guard rule, named-field records,
tuned-constant update rule, doc-invariant test conventions, semantics-change
re-tune rule) so automated review can apply the same rules this file gives
the coding agent, instead of only flagging violations after merge. This file
remains the source of truth — **keep `.github/copilot-instructions.md` in
sync whenever a convention here changes or a new one is added.**
