# Copilot Review Instructions — Orbit Wars

This file restates, in reviewer-facing form, conventions this repo already
enforces for its coding agent. **`CLAUDE.md` at the repo root is the source
of truth** — if anything here conflicts with it, `CLAUDE.md` wins. Do not
copy code-derived values (thresholds, game counts, tuned params) into this
file; cite them by name and point back to `CLAUDE.md` and the source module
instead, so this file cannot drift out of sync the way prose docs previously
did (see the "Cite Code-Derived Values by Name" section of `CLAUDE.md`).

When reviewing a PR against this repo, check for the following recurring
failure classes before approving.

## Boundary-split guard rule

See "Simulator Correctness → Boundary-split guard rule" in `CLAUDE.md`.

When a single `<=`/`>=` boundary guard has been decomposed into separate
`if`/`elif`/`else` branches, flag it unless:

- The equality branch tests the **exact boundary** (e.g. `== 0`), never a
  loose `elif` that could also match the strictly-negative (or
  strictly-greater) case.
- A regression test exercises the **strictly-negative/-greater** case, not
  just the boundary value itself.

A loose `elif winner == planet.owner` that silently also fires when
`surviving < 0` is the motivating bug this rule exists to catch — flag any
`elif` that re-tests a condition already implied by the preceding branch
instead of the exact remaining boundary.

## Named-field records, not positionally-indexed lists

See "Python Conventions → Named-field records, not positionally-indexed
lists" in `CLAUDE.md`.

Flag any fixed-arity record of _distinct_ fields (e.g. a ships-count paired
with an ETA) represented as a `list` mutated via positional indices like
`agg[0]`/`agg[1]`. Request a tuple with named unpacking or a small
`NamedTuple`/`dataclass` instead. This does not apply to genuine homogeneous
collections (e.g. `list[Fleet]`).

## Tuned-constant update rule

See "Tuning Workflow → Tuned-constant update rule" in `CLAUDE.md`.

Whenever a PR changes a tuned constant's value (e.g. a promotion threshold
or game count), confirm the author:

1. Grepped the **entire repo** for the old value in **every representation**
   (percent form and decimal form at minimum) and updated every live
   reference, including anything under `.claude/docs/`.
2. Cited the constant **by name** (its symbol and source file) rather than
   transcribing the number in prose, tables, or acceptance-criteria bullets.
3. Left intentionally-dated snapshots under `archive/` and `superpowers/`
   untouched — those are historical records, not living docs.
4. Re-verified every other constant enumerated in the same doc section they
   edited, not just the one that prompted the change.

## Doc-Invariant Test Conventions

See "Doc-Invariant Test Conventions" in `CLAUDE.md`.

For any new or modified test asserting "no doc references the old value X",
confirm it:

1. Matches all value representations (e.g. percent and decimal forms), not
   just one literal.
2. Scans the full repo, with any excluded directory listed in an explicit,
   commented exclusion set that explains why the exclusion is valid.
3. Documents any CI limitation explicitly (e.g. a harness-blocked directory
   that cannot be policed from a test) rather than silently omitting it.
4. Covers any documented constant value by importing it from its source
   module and asserting the doc matches, rather than hardcoding an expected
   number in the test itself.
5. For any excluded directory, confirms (and records) that the directory was
   actually verified clean of the stale value — not just that the exclusion
   was documented.

## Semantics-change re-tune rule

See "Tuning Workflow → Semantics-change re-tune rule" in `CLAUDE.md`.

If a PR changes simulator/scoring/threat-detection semantics in a way that
alters what a tuned param in `src/config.py` `PARAMS` affects, confirm it:

1. Adds an inline coupling note at the constant's definition explaining what
   changed and why the constant's meaning shifted.
2. Documents the re-tune workflow, including clearing stale Optuna priors
   before re-running tuning.
3. Explicitly flags the affected params as ones that **must not be promoted**
   until re-tuned, even if a challenger clears the promotion gate — a
   challenger built on stale semantics must not be promoted regardless of its
   measured win rate.

If `CLAUDE.md` already has a "Pending re-tune" section for affected params,
confirm the PR doesn't promote those params before that section is resolved.

## Keeping this file in sync

`CLAUDE.md` is authoritative. When a convention above changes or a new one
is added to `CLAUDE.md`, update this file in the same change — see the
pointer in `CLAUDE.md`.
