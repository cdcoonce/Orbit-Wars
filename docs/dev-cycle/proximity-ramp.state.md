---
schema_version: 1
feature: proximity-ramp
status: in_progress
current_phase: implement
created: 2026-04-27
updated: 2026-04-27
branch:
---

## Artifacts

| Phase       | Status    | Artifact                                                           |
| ----------- | --------- | ------------------------------------------------------------------ |
| brainstorm  | completed | [Orbit-Wars #20](https://github.com/cdcoonce/Orbit-Wars/issues/20) |
| plan        | completed | docs/plans/proximity-ramp.md                                       |
| ceo_review  | completed | docs/plans/proximity-ramp.md (revised)                             |
| issues      | completed | #21 #22                                                            |
| implement   | pending   | —                                                                  |
| code_review | pending   | —                                                                  |
| pr          | pending   | —                                                                  |

## Issues

| Plan Slice                             | GitHub Issue                                            | Status |
| -------------------------------------- | ------------------------------------------------------- | ------ |
| Phase 1: Ramp helper + formula + tests | [#21](https://github.com/cdcoonce/Orbit-Wars/issues/21) | open   |
| Phase 2: Optuna retune                 | [#22](https://github.com/cdcoonce/Orbit-Wars/issues/22) | open   |

## Log

- 2026-04-27: Phase 1 (brainstorm) complete. Spec at
  `docs/superpowers/specs/2026-04-27-proximity-ramp-design.md`.
  PRD issue: [Orbit-Wars #20](https://github.com/cdcoonce/Orbit-Wars/issues/20).
- 2026-04-27: Advancing to Phase 2 (plan).
- 2026-04-27: Phase 2 (plan) complete. Plan at `docs/plans/proximity-ramp.md`.
  2 phases: ramp helper + formula + tests → Optuna retune.
  Advancing to Phase 3 (ceo_review).
- 2026-04-27: Phase 3 (ceo_review) complete. HOLD SCOPE mode. Key additions:
  dist_power hoisted before source loop (not per-candidate), score-ordering test
  uses direct math assertion (no plan_expansion scaffolding), future note to
  extract generic \_linear_ramp helper if a third ramp is added.
  Advancing to Phase 4 (issues).
- 2026-04-27: Phase 4 (issues) complete. 2 GitHub issues created (#21-#22).
  #21 must land first; #22 depends on #21.
  Advancing to Phase 5 (implement).
