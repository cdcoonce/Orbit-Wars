## Overview

`src/config.py` contains three top-level objects: `PARAMS`, `PARAM_SPACE`, and `SKIP_COMBOS`. Together they define all tunable behavior in the bot and the bounds within which Optuna searches for better values.

Cross-links: [Strategy](strategy.md) | [Lookahead](lookahead.md) | [Home](../Home.md)

---

## PARAMS

`PARAMS` is a flat `dict[str, int | float]` with 32 keys. It is the **active runtime configuration** — every strategy function accepts a `params` argument defaulting to `PARAMS`. To run with alternate parameters (e.g., during Optuna trials), pass a modified copy; the source file is never mutated at runtime.

After a tuning run promotes a champion, copy the winning values into `PARAMS` manually, then rebuild (`python build.py`) and submit.

---

## PARAM_SPACE

`PARAM_SPACE` is a `dict[str, tuple[low, high, type]]` defining the Optuna search space. Each entry maps a param name to `(low, high, int | float)`. `run_trials.py` reads this to construct `trial.suggest_int` / `trial.suggest_float` calls.

One key intentionally absent from `PARAM_SPACE`: `game_length` — it is a fixed constant (500) that reflects the Kaggle competition rule, not a tunable hyperparameter.

After any significant change to the simulator or scoring logic, **delete `trials/study.db`** before rerunning trials. Stale Bayesian priors from a previous objective function will mislead Optuna.

---

## SKIP_COMBOS

`SKIP_COMBOS` is a `set` of `(source_class, target_class)` string tuples. `plan_expansion` filters out any move whose source and target classes appear in this set. These are hard-coded policy decisions — there is no Optuna tuning for which combos to skip. See [Strategy](strategy.md) for the full rationale table.

---

## generate_config.py

`docs/wiki/generate_config.py` is a maintenance script that reads `PARAMS` and `PARAM_SPACE` from `src/config.py` and regenerates the parameter reference table below. Run it after any change to `PARAMS` or `PARAM_SPACE`:

```bash
uv run python docs/wiki/generate_config.py
```

The script validates that the key sets of `PARAMS` and `PARAM_SPACE` match (excluding `game_length`, which is intentionally absent from `PARAM_SPACE`). A `ValueError` is raised if any key diverges. On success it prints `config.md updated` and replaces the section between the `AUTO-GENERATED-START` and `AUTO-GENERATED-END` markers in this file.

---

## Parameter Reference

<!-- AUTO-GENERATED: run docs/wiki/generate_config.py to update -->
<!-- AUTO-GENERATED-START -->
### Planet Classification

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `fortress_min_ships` | `23` | 20 – 60 (int) | Raise → fewer FORTRESS planets, more ships available for attack |
| `fortress_min_production` | `2` | 2 – 5 (int) | Raise → fewer FORTRESS planets |
| `factory_min_production` | `4` | 2 – 5 (int) | Raise → fewer FACTORY planets, more OUTPOST |

### Value Tiers

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `high_value_production` | `5` | 3 – 6 (int) | Raise → fewer HIGH tier planets |
| `medium_value_production` | `4` | 1 – 4 (int) | Raise → fewer MEDIUM tier planets |
| `stationary_value_bonus` | `4` | 0 – 8 (int) | Raise → more attractive to attack stationary planets |

### Target Classification

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `weak_ratio` | `2.43003` | 1.1 – 2.5 (float) | Raise → fewer EASY_NEUTRAL / SOFT_ENEMY targets (more conservative) |
| `contested_ratio` | `0.892436` | 0.8 – 1.5 (float) | Raise → fewer CONTESTED targets (more conservative) |

### Send Fractions

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `frac_fortress_easy_neutral` | `0.449357` | 0.4 – 0.9 (float) | Raise → send more ships from FORTRESS to EASY_NEUTRAL |
| `frac_fortress_hard_neutral` | `0.50665` | 0.5 – 0.95 (float) | Raise → send more ships from FORTRESS to HARD_NEUTRAL |
| `frac_fortress_soft_enemy` | `0.873833` | 0.4 – 0.9 (float) | Raise → send more ships from FORTRESS to SOFT_ENEMY |
| `frac_fortress_contested_enemy` | `0.52808` | 0.5 – 0.95 (float) | Raise → send more ships from FORTRESS to CONTESTED_ENEMY |
| `frac_fortress_hardened_enemy` | `0.85` | 0.5 – 0.95 (float) | Raise → send more ships from FORTRESS to HARDENED_ENEMY |
| `frac_factory_easy_neutral` | `0.32536` | 0.3 – 0.8 (float) | Raise → send more ships from FACTORY to EASY_NEUTRAL |
| `frac_factory_soft_enemy` | `0.662866` | 0.3 – 0.8 (float) | Raise → send more ships from FACTORY to SOFT_ENEMY |
| `frac_outpost_easy_neutral` | `0.55908` | 0.2 – 0.7 (float) | Raise → send more ships from OUTPOST to EASY_NEUTRAL |
| `frac_outpost_soft_enemy` | `0.674644` | 0.2 – 0.7 (float) | Raise → send more ships from OUTPOST to SOFT_ENEMY |

### Defense

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `threat_radius` | `7.58474` | 3 – 8 (float) | Raise → detect threats from farther away |
| `threat_eta_window` | `22` | 10 – 50 (int) | Raise → react earlier to incoming fleets |
| `defense_reinforce_fraction` | `0.304684` | 0.3 – 0.7 (float) | Raise → send more reinforcements when threatened |
| `eta_buffer` | `9` | 2 – 10 (int) | Raise → more conservative ETA margin for defense |
| `min_garrison` | `24` | 5 – 30 (int) | Raise → keep more ships at home before attacking |

### Aggression

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `aggression_max` | `0.967912` | 0.7 – 1 (float) | Raise → more ships sent earlier in game |
| `aggression_min` | `0.467406` | 0.3 – 0.8 (float) | Raise → more ships sent later in game |
| `game_length` | `500` | fixed | Fixed: 500 — reflects Kaggle competition rule, not tunable |

### Garrison Ramp

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `min_garrison_early` | `3` | 1 – 15 (int) | Raise → more conservative in early game |
| `garrison_ramp_turns` | `27` | 10 – 100 (int) | Raise → take longer to reach full garrison threshold |

### Distance Power

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `distance_power_early` | `4.2343` | 2 – 5 (float) | Raise → penalise distant targets more in early game |
| `distance_power_late` | `1.94595` | 0.5 – 3 (float) | Raise → penalise distant targets more in late game |
| `distance_ramp_turns` | `80` | 10 – 150 (int) | Raise → take longer to ramp from early to late distance exponent |

### Comets

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `comet_value_multiplier` | `1.75354` | 0 – 3 (float) | Raise → treat comets as more attractive targets |

### Endgame

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `endgame_threshold_turn` | `447` | 380 – 490 (int) | Raise → switch to defensive mode later |
| `endgame_lead_margin` | `1.56832` | 1.05 – 2 (float) | Raise → require larger lead before going defensive |

### Lookahead

| Param | Default | Optuna range | Behavioral impact |
|---|---|---|---|
| `lookahead_turns` | `2` | 1 – 5 (int) | Raise → simulate further ahead (slower) |
| `lookahead_blend` | `0.970012` | 0 – 1 (float) | Raise → trust simulator more vs greedy heuristic |
| `lookahead_ship_weight` | `0.0804694` | 0.001 – 0.1 (float) | Raise → value ship counts more vs production in scoring |

<!-- AUTO-GENERATED-END -->
