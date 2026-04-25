# Strategy Testing Harness — Design Spec

**Date:** 2026-04-24
**Status:** Approved

## Summary

A two-tool testing harness for iterating on bot strategy:

1. **Single-game viewer** — detailed per-turn metrics for one game (our bot vs `random`)
2. **Multi-game comparison** — champion/challenger win-rate comparison across N games, with results saved to JSON

The champion baseline is a committed `champion.json` snapshot of `PARAMS`. The comparison module is importable as a library to support future automated parameter search.

---

## Architecture

```
scripts/
  run_game.py          — single-game detail view
  run_comparison.py    — champion vs challenger across N games (also importable)
  champion.json        — committed PARAMS snapshot (the current best strategy)
  results/             — per-run JSON output files (gitignored)
```

The existing root `run_game.py` is superseded by `scripts/run_game.py`.

---

## Single-Game Viewer (`scripts/run_game.py`)

Runs one game of our agent vs `random` using `kaggle_environments`. Collects per-turn:

- Ships owned per player
- Planets owned per player
- Active fleet count

Prints a summary table every 50 turns plus a final result line.

**Example output:**

```
Turn  | P0 planets | P0 ships | P1 planets | P1 ships | Fleets
------|------------|----------|------------|----------|-------
   50 |     8      |   420    |     4      |   180    |   12
  100 |    14      |   890    |     3      |   110    |    8
  150 |    21      |  1840    |     1      |    40    |    3
  500 |    36      |  4210    |     0      |     0    |    0

Result: WIN (4210 vs 0 ships)
```

**Usage:**

```bash
uv run python scripts/run_game.py
```

---

## Multi-Game Comparison (`scripts/run_comparison.py`)

Runs N games twice — challenger (current `strategy.py` PARAMS) and champion (`champion.json`) — both against `random`. Reports win rate and average final ships per player.

**Champion management:**

- `champion.json` is initialized by running `--promote` once before any comparisons
- After a comparison run, if challenger wins, the tool prompts interactively: `Promote challenger to champion? [y/N]`
- `--promote` as a standalone flag (no games run) writes current PARAMS to `champion.json` immediately — used for first-time setup or scripted pipelines
- `champion.json` is committed to git so the baseline is always reproducible

**Results persistence:**

- Each run saves to `scripts/results/YYYY-MM-DD-HH-MM.json`
- `scripts/results/` is gitignored
- JSON format is machine-readable for future automated tuning

**Example output:**

```
Running 50 games: challenger vs random...  [====================] 50/50
Running 50 games: champion vs random...    [====================] 50/50

                 Challenger   Champion
Win rate            74%          61%
Avg final ships    3420         2890
Avg planets held     22           18

Challenger wins. Run with --promote to update champion.json.
```

**Usage:**

```bash
uv run python scripts/run_comparison.py --promote   # first-time setup: save current PARAMS as champion
uv run python scripts/run_comparison.py             # 50 games, prompts to promote if challenger wins
uv run python scripts/run_comparison.py --games 200
```

**Module interface (for future automation):**

```python
from scripts.run_comparison import run_comparison

results = run_comparison(params_challenger, params_champion, games=100)
# returns: {"challenger": {"wins": 74, "avg_ships": 3420}, "champion": {...}}
```

---

## Iteration Workflow

```
0. First time only: uv run python scripts/run_comparison.py --promote
1. Tweak a value in PARAMS (src/strategy.py)
2. uv run python scripts/run_comparison.py --games 100
3. Review results; if challenger wins, type "y" at the prompt
4. Commit champion.json + strategy.py together
```

---

## Planned Next Step: Automated Parameter Search

The module interface on `run_comparison` is designed to support a future `scripts/tune.py` that iterates over a parameter grid automatically:

```python
for value in [0.4, 0.5, 0.6, 0.7, 0.8]:
    results = run_comparison(
        {**PARAMS, "aggression_min": value},
        champion_params,
        games=50,
    )
    # log results, find best value
```

No implementation now — just the door left open.

---

## What Does Not Change

- `src/strategy.py` — PARAMS structure unchanged
- `src/agent.py` — unchanged
- `build.py` / `submission.py` — unchanged
- `tests/` — unchanged
