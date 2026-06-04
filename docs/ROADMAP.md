# Roadmap — Orbit Wars (Kaggle bot)

> Read **verbatim** by `afk-driver --expand` and injected into the feature-
> proposing agent's prompt alongside the live code. Write at the altitude of
> **intent** — name directions and gaps; let the expander (and the code it reads)
> propose specifics. Each proposal inherits the **Track** it advances; that label
> is how a human triages it (see Direction).

## Vision

Win the Kaggle **Orbit Wars** competition: an agent that captures the most ships
by turn 500 across planets orbiting a central sun. Climb ELO from the current
~637 baseline before the **2026-06-16 deadline**, via a **parameterized,
well-tested, fast-to-tune** bot — where strategy lives in tunable params, the
test suite guards correctness, and Optuna self-play does the searching.

## What's shipped (baseline — do not re-propose)

- **Parameterized strategy** (`src/config.py`: `PARAMS` active defaults +
  `PARAM_SPACE` Optuna bounds) consumed by `src/strategy.py` (`plan_moves`,
  own/neutral/enemy classifiers, send-fraction lookups).
- **1–2 turn lookahead simulator** (`src/lookahead.py`: `step_state`,
  `score_state`) blended into move scoring.
- **Comet handling** (`src/comets.py`), **endgame mode** (`src/endgame.py`),
  early-game garrison ramp, distance-power ramp.
- **Tuning workflow**: `trials/run_trials.py` (Optuna self-play) promotes
  challengers to `trials/champion.py` at a win-rate threshold; `trials/
benchmark.py` sanity-checks champion vs. original defaults.
- **Submission bundling**: `build.py` flattens `src/` into a single
  `submission.py` for Kaggle.
- **Recent fixes**: value-tier system removed; benchmark repaired (the opponent
  was crashing every turn on missing params → silent all-draws); div-by-zero
  guard in `predict_planet_position`; a `build.py` submission smoke test.

## Direction

Two tracks. **Every proposal must state which track it is on** — that is how a
human decides whether the test gate is sufficient or a benchmark is required.

### Track A — Robustness, quality & tuning infrastructure

_The test suite can verify these. Autonomous-safe: promote on a green gate._

- _Where we are:_ a few real bugs have surfaced (a silent benchmark crash, a
  divide-by-zero, a stale-defaults drift). `strategy.py` is 466 lines doing a lot.
  Optuna runs are slow (~30–60 min) and depend on a `study.db` that goes stale.
- _Where we're going:_ a bot that is hard to break and fast to iterate —
  defensive guards on edge cases, invariant tests that catch config/param drift
  (in the spirit of the consistency test that just caught a stale champion),
  sounder and faster tuning/benchmark machinery (reproducibility, parallelism,
  clearer study lifecycle), focused decomposition of the largest modules, and a
  submission path that can't silently break.
- _The principle:_ every correctness property the bot relies on should be pinned
  by a test, and every tuning run should be reproducible and trustworthy.

### Track B — Strategy & play

_The gate confirms "doesn't break"; it CANNOT confirm an ELO gain — that needs a
self-play / Optuna run the human evaluates. A Track-B proposal MUST state how to
benchmark its claimed gain._

- _Where we are:_ target valuation is production-based (the value-tier heuristic
  was just removed); lookahead is 1–2 turns with no explicit opponent model;
  endgame and comet logic are simple.
- _Where we're going:_ sharper decisions — better target valuation and threat
  assessment, deeper or more selective lookahead, a real opponent model,
  refined endgame/comet play, and **new tunable dimensions** that widen the
  Optuna search space where the current params plateau.
- _The principle:_ express new behavior as **tunable params** (so Optuna can
  search it) rather than hard-coded constants, and never claim an improvement
  without a self-play benchmark to back it.

## Principles every proposal must respect

- **afk-sized + independently testable.** A child must leave the suite green on
  its own; keep consistency-coupled changes in one slice.
- **Express strategy as params.** New behavioral knobs go in `PARAMS` +
  `PARAM_SPACE` so Optuna can tune them — not as magic numbers.
- **Never break submission bundling.** Changes must survive `build.py` →
  `submission.py` (no new heavy deps, no imports Kaggle can't resolve).
- **Don't touch tuned `champion.py` values blindly.** Champion params are the
  output of a tuning run; only change them via a benchmark, never by hand-guess.
- **Tests are the gate.** Track A is promote-on-green; Track B is promote-then-
  benchmark.

## Non-goals (out of scope — do not propose)

- No architecture rewrite or framework swap of the strategy/lookahead engine.
- No heavy third-party dependencies (the Kaggle bundle must stay self-contained).
- No changing `champion.py` tuned values without a self-play benchmark.
- No UI, dashboard, or telemetry — this is a headless competition agent.
- No work on the afk tooling itself here — propose bot improvements only.
