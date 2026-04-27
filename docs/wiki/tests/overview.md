## Overview

Test suite for Orbit Wars. Run the fast suite (no Optuna dependency) with:

```bash
uv run pytest tests/ --ignore=tests/test_trial_runner.py
```

Full suite (requires `optuna` installed):

```bash
uv run pytest tests/ -v
```

Cross-links: [Home](../Home.md) | [Strategy](../src/strategy.md) | [Lookahead](../src/lookahead.md) | [Math Utils](../src/math_utils.md) | [Comets](../src/comets.md) | [Endgame](../src/endgame.md) | [Config](../src/config.md)

---

## Test Files

| Test file                          | Module covered                      | Key invariant groups                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_strategy.py`           | `src/strategy.py`                   | Stationarity / value tier, capture mechanics (`can_capture` strict-`>` rule), intercept correction pass, own/neutral/enemy classifiers, threat detection and response, `plan_expansion` filters (SKIP_COMBOS, garrison, sun-crossing), garrison ramp direction                                                                            |
| `tests/test_lookahead.py`          | `src/lookahead.py`                  | State construction (`TestBuildState` — field copy fidelity), turn simulation (`TestStepState` — production, rotation, combat resolution, foothold cost), scoring (`TestScoreState` — production differential + ship weight), lookahead blend integration (`TestPlanExpansionBlend` — opponent_fn call count, normalized score selection)  |
| `tests/test_math_utils.py`         | `src/math_utils.py`                 | Distance (zero, 3-4-5 triangle), fleet speed curve (1-ship floor, monotone increase, 1000-ship ceiling at 6.0), orbital rotation (stationary unchanged, zero-turns identity, full-revolution round-trip), angle calculation (right/down/left quadrants)                                                                                   |
| `tests/test_comets.py`             | `src/comets.py`                     | Comet ID extraction (absent key, `None` value, single ID, empty list), effective production scaling (zero multiplier, double multiplier, non-comet unaffected, empty comet set)                                                                                                                                                           |
| `tests/test_comets_integration.py` | `src/strategy.py` × `src/comets.py` | Comet value reflected in `plan_expansion` scoring — comet planets are scored with `effective_production` and compete against permanent planets correctly                                                                                                                                                                                  |
| `tests/test_endgame.py`            | `src/endgame.py`                    | `total_ships` (planet-only, fleet-only, combined, ignores other player and neutral), `should_play_defensive` trigger conditions (winning + past threshold, losing, before threshold, zero-enemy guard, boundary equality), `plan_moves` integration (expansion suppressed when defensive, expansion continues when losing past threshold) |
| `tests/test_config.py`             | `src/config.py`                     | `PARAM_SPACE` coverage — every key in `PARAMS` except `game_length` has a corresponding entry in `PARAM_SPACE` with a tunable range                                                                                                                                                                                                       |
| `tests/test_trial_runner.py`       | `trials/`                           | Optuna objective smoke test — requires `optuna`; skip with `--ignore=tests/test_trial_runner.py` in the fast suite                                                                                                                                                                                                                        |

---

## Notes

- `make_planet` / `make_fleet` helpers appear in most test files with consistent default arguments; they wrap the Kaggle `Planet` / `Fleet` namedtuple constructors.
- `test_config.py` uses set equality: `assert set(PARAM_SPACE.keys()) == set(PARAMS.keys()) - {"game_length"}`. `game_length` is intentionally excluded from tuning (it's a fixed game property, not a strategic parameter).
- `test_trial_runner.py` is the only file with an external dependency (Optuna). All other tests run in the base environment with only `kaggle_environments` installed.
