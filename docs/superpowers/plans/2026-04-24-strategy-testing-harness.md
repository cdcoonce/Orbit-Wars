# Strategy Testing Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-tool testing harness: a single-game viewer and a multi-game champion/challenger comparison tool.

**Architecture:** `scripts/run_comparison.py` is the core importable module containing the game runner, champion I/O, and `run_comparison()`. `scripts/run_game.py` is a thin CLI that imports from it and prints a per-turn table. A committed `scripts/champion.json` stores the PARAMS baseline.

**Tech Stack:** Python 3.11, uv, kaggle-environments (already installed), pytest, stdlib only (json, argparse, pathlib, datetime)

---

## File Map

| File                         | Action | Responsibility                                                   |
| ---------------------------- | ------ | ---------------------------------------------------------------- |
| `scripts/__init__.py`        | Create | Makes `scripts` importable as a package                          |
| `scripts/run_comparison.py`  | Create | Core library: game runner, champion I/O, `run_comparison()`, CLI |
| `scripts/run_game.py`        | Create | Single-game CLI: prints per-turn table                           |
| `scripts/champion.json`      | Create | Committed PARAMS snapshot                                        |
| `scripts/results/.gitignore` | Create | Ignores per-run result files                                     |
| `tests/test_scripts.py`      | Create | Tests for champion I/O and run_comparison                        |
| `run_game.py`                | Delete | Superseded by `scripts/run_game.py`                              |

---

## Task 1: Scaffolding

**Files:**

- Create: `scripts/__init__.py`
- Create: `scripts/results/.gitignore`
- Create: `tests/test_scripts.py`

- [ ] **Step 1: Create `scripts/__init__.py`**

```python

```

(empty file — makes the directory a package)

- [ ] **Step 2: Create `scripts/results/.gitignore`**

```
*
!.gitignore
```

- [ ] **Step 3: Create `tests/test_scripts.py`**

```python
import json
import pytest
from pathlib import Path
```

- [ ] **Step 4: Verify import works**

Run:

```bash
uv run python -c "import scripts; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/results/.gitignore tests/test_scripts.py
git commit -m "feat: add scripts package scaffolding"
```

---

## Task 2: Champion I/O

`champion.json` stores `PARAMS` with tuple keys serialised as `"CLASS_A,CLASS_B"` strings (JSON does not support tuple keys).

**Files:**

- Create: `scripts/run_comparison.py`
- Create: `scripts/champion.json`
- Modify: `tests/test_scripts.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_scripts.py`:

```python
import json
import pytest
from pathlib import Path
from src.strategy import PARAMS


def test_params_roundtrip(tmp_path, monkeypatch):
    from scripts import run_comparison
    monkeypatch.setattr(run_comparison, "CHAMPION_PATH", tmp_path / "champion.json")
    run_comparison.save_champion(PARAMS)
    loaded = run_comparison.load_champion()
    assert loaded["fortress_min_ships"] == PARAMS["fortress_min_ships"]
    assert loaded["send_fractions"][("FORTRESS", "EASY_NEUTRAL")] == PARAMS["send_fractions"][("FORTRESS", "EASY_NEUTRAL")]


def test_save_champion_writes_valid_json(tmp_path, monkeypatch):
    from scripts import run_comparison
    monkeypatch.setattr(run_comparison, "CHAMPION_PATH", tmp_path / "champion.json")
    run_comparison.save_champion(PARAMS)
    data = json.loads((tmp_path / "champion.json").read_text())
    assert "send_fractions" in data
    assert "FORTRESS,EASY_NEUTRAL" in data["send_fractions"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_scripts.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Create `scripts/run_comparison.py` with champion I/O**

```python
import json
from pathlib import Path

CHAMPION_PATH = Path(__file__).parent / "champion.json"


def _params_to_json(params: dict) -> dict:
    result = {k: v for k, v in params.items() if k != "send_fractions"}
    result["send_fractions"] = {
        f"{k[0]},{k[1]}": v for k, v in params["send_fractions"].items()
    }
    return result


def _params_from_json(data: dict) -> dict:
    result = {k: v for k, v in data.items() if k != "send_fractions"}
    result["send_fractions"] = {
        tuple(k.split(",")): v for k, v in data["send_fractions"].items()
    }
    return result


def load_champion() -> dict:
    return _params_from_json(json.loads(CHAMPION_PATH.read_text()))


def save_champion(params: dict) -> None:
    CHAMPION_PATH.write_text(json.dumps(_params_to_json(params), indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_scripts.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Create initial `scripts/champion.json`**

```bash
uv run python -c "
from src.strategy import PARAMS
from scripts.run_comparison import save_champion
save_champion(PARAMS)
print('champion.json written')
"
```

Expected: `champion.json written`

- [ ] **Step 6: Commit**

```bash
git add scripts/run_comparison.py scripts/champion.json tests/test_scripts.py
git commit -m "feat: add champion I/O and initial champion.json"
```

---

## Task 3: Game Runner

`run_single_game(params, steps=500)` runs one game of our agent (using `params`) vs `"random"` and returns per-turn stats plus final result.

**Files:**

- Modify: `scripts/run_comparison.py`
- Modify: `tests/test_scripts.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_scripts.py`:

```python
def test_run_single_game_returns_correct_shape():
    from scripts.run_comparison import run_single_game
    from src.strategy import PARAMS
    result = run_single_game(PARAMS, steps=10)
    assert "winner" in result
    assert result["winner"] in (0, 1)
    assert "final_ships" in result
    assert 0 in result["final_ships"]
    assert "turns" in result
    assert len(result["turns"]) > 0
    turn = result["turns"][0]
    assert "turn" in turn
    assert "ships" in turn
    assert "planets" in turn
    assert "fleet_count" in turn
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_scripts.py::test_run_single_game_returns_correct_shape -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `_make_agent` and `run_single_game` to `scripts/run_comparison.py`**

```python
from kaggle_environments import make
import src.strategy as _strat
from src.agent import agent as _agent


def _make_agent(params: dict):
    """Return an agent function that uses the given params instead of the global PARAMS."""
    def _run(obs: dict) -> list:
        saved = dict(_strat.PARAMS)
        _strat.PARAMS.update(params)
        try:
            return _agent(obs)
        finally:
            _strat.PARAMS.clear()
            _strat.PARAMS.update(saved)
    return _run


def run_single_game(params: dict, steps: int = 500) -> dict:
    """Run one game of our agent (with params) vs random. Returns stats dict."""
    env = make("orbit_wars", debug=False, configuration={"episodeSteps": steps})
    env.run([_make_agent(params), "random"])

    turns = []
    for step in env.steps[1:]:
        obs = step[0]["observation"]
        planets = obs.get("planets", [])
        fleets = obs.get("fleets", [])

        ships: dict[int, int] = {}
        planet_counts: dict[int, int] = {}
        for p in planets:
            owner = p[1]
            if owner == -1:
                continue
            ships[owner] = ships.get(owner, 0) + p[5]
            planet_counts[owner] = planet_counts.get(owner, 0) + 1
        for f in fleets:
            owner = f[1]
            ships[owner] = ships.get(owner, 0) + f[6]

        turns.append({
            "turn": obs.get("step", 0),
            "ships": ships,
            "planets": planet_counts,
            "fleet_count": len(fleets),
        })

    final = turns[-1]
    p0 = final["ships"].get(0, 0)
    p1 = final["ships"].get(1, 0)
    return {
        "winner": 0 if p0 >= p1 else 1,
        "final_ships": {0: p0, 1: p1},
        "final_planets": {0: final["planets"].get(0, 0), 1: final["planets"].get(1, 0)},
        "turns": turns,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_scripts.py::test_run_single_game_returns_correct_shape -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_comparison.py tests/test_scripts.py
git commit -m "feat: add game runner with per-turn stats collection"
```

---

## Task 4: `run_comparison` Function

`run_comparison(params_challenger, params_champion, games)` runs N games for each strategy vs `"random"` and returns a comparison dict.

**Files:**

- Modify: `scripts/run_comparison.py`
- Modify: `tests/test_scripts.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_scripts.py`:

```python
def test_run_comparison_returns_correct_shape():
    from scripts.run_comparison import run_comparison
    from src.strategy import PARAMS
    results = run_comparison(PARAMS, PARAMS, games=1)
    assert "challenger" in results
    assert "champion" in results
    assert "games" in results
    assert results["games"] == 1
    for key in ("wins", "win_rate", "avg_final_ships", "avg_final_planets"):
        assert key in results["challenger"]
        assert key in results["champion"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_scripts.py::test_run_comparison_returns_correct_shape -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `run_comparison` to `scripts/run_comparison.py`**

```python
def run_comparison(
    params_challenger: dict,
    params_champion: dict,
    games: int = 50,
) -> dict:
    """Run N games for each strategy vs random. Returns comparison stats dict."""

    def _run_games(params: dict, label: str) -> dict:
        wins = 0
        total_ships = 0
        total_planets = 0
        for i in range(games):
            print(f"\r{label}: {i + 1}/{games}", end="", flush=True)
            result = run_single_game(params)
            if result["winner"] == 0:
                wins += 1
            total_ships += result["final_ships"][0]
            total_planets += result["final_planets"][0]
        print()
        return {
            "wins": wins,
            "win_rate": wins / games,
            "avg_final_ships": total_ships // games,
            "avg_final_planets": total_planets // games,
        }

    return {
        "challenger": _run_games(params_challenger, "Challenger"),
        "champion": _run_games(params_champion, "  Champion"),
        "games": games,
    }
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/test_scripts.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_comparison.py tests/test_scripts.py
git commit -m "feat: add run_comparison function"
```

---

## Task 5: Single-Game CLI (`scripts/run_game.py`)

Prints a per-turn table every 50 turns and a final result line.

**Files:**

- Create: `scripts/run_game.py`
- Delete: `run_game.py`

- [ ] **Step 1: Create `scripts/run_game.py`**

```python
from src.strategy import PARAMS
from scripts.run_comparison import run_single_game


def main() -> None:
    result = run_single_game(PARAMS)
    turns = result["turns"]

    header = f"{'Turn':>5} | {'P0 planets':>10} | {'P0 ships':>8} | {'P1 planets':>10} | {'P1 ships':>8} | {'Fleets':>6}"
    print(header)
    print("-" * len(header))

    checkpoints = set(range(50, 501, 50))
    for t in turns:
        if t["turn"] in checkpoints:
            print(
                f"{t['turn']:>5} | "
                f"{t['planets'].get(0, 0):>10} | "
                f"{t['ships'].get(0, 0):>8} | "
                f"{t['planets'].get(1, 0):>10} | "
                f"{t['ships'].get(1, 0):>8} | "
                f"{t['fleet_count']:>6}"
            )

    p0 = result["final_ships"][0]
    p1 = result["final_ships"][1]
    outcome = "WIN" if result["winner"] == 0 else "LOSS"
    print(f"\nResult: {outcome} ({p0} vs {p1} ships)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it manually and verify output**

```bash
uv run python scripts/run_game.py
```

Expected: table printed every 50 turns, final `Result: WIN` or `Result: LOSS` line, no errors.

- [ ] **Step 3: Delete the old root `run_game.py`**

```bash
git rm run_game.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/run_game.py
git commit -m "feat: add single-game CLI viewer, remove old run_game.py"
```

---

## Task 6: Comparison CLI (`scripts/run_comparison.py` entry point)

Adds `argparse` CLI with `--games` and `--promote`, interactive promote prompt, and results JSON saving.

**Files:**

- Modify: `scripts/run_comparison.py`

- [ ] **Step 1: Add CLI entry point to `scripts/run_comparison.py`**

Append to the bottom of `scripts/run_comparison.py`:

```python
if __name__ == "__main__":
    import argparse
    import sys
    from datetime import datetime
    from src.strategy import PARAMS

    parser = argparse.ArgumentParser(description="Champion vs challenger comparison")
    parser.add_argument("--games", type=int, default=50, help="Games per strategy (default 50)")
    parser.add_argument("--promote", action="store_true", help="Save current PARAMS as champion and exit")
    args = parser.parse_args()

    if args.promote:
        save_champion(PARAMS)
        print(f"Champion saved to {CHAMPION_PATH}")
        sys.exit(0)

    if not CHAMPION_PATH.exists():
        print(f"No champion found at {CHAMPION_PATH}. Run with --promote first.")
        sys.exit(1)

    champion_params = load_champion()
    results = run_comparison(PARAMS, champion_params, games=args.games)

    c = results["challenger"]
    ch = results["champion"]
    print(f"\n{'':20} {'Challenger':>12} {'Champion':>12}")
    print(f"{'Win rate':20} {c['win_rate']:>11.0%} {ch['win_rate']:>11.0%}")
    print(f"{'Avg final ships':20} {c['avg_final_ships']:>12} {ch['avg_final_ships']:>12}")
    print(f"{'Avg planets held':20} {c['avg_final_planets']:>12} {ch['avg_final_planets']:>12}")

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    results_file = results_dir / f"{timestamp}.json"
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {results_file}")

    if c["win_rate"] > ch["win_rate"]:
        print(f"\nChallenger wins ({c['win_rate']:.0%} vs {ch['win_rate']:.0%}).")
        answer = input("Promote challenger to champion? [y/N]: ").strip().lower()
        if answer == "y":
            save_champion(PARAMS)
            print("Champion updated.")
    else:
        print(f"\nChampion holds ({ch['win_rate']:.0%} vs {c['win_rate']:.0%}).")
```

- [ ] **Step 2: Test `--promote` flag**

```bash
uv run python scripts/run_comparison.py --promote
```

Expected: `Champion saved to scripts/champion.json`

- [ ] **Step 3: Run a short comparison to verify end-to-end**

```bash
uv run python scripts/run_comparison.py --games 2
```

Expected: progress lines, results table, results saved message, no errors.

- [ ] **Step 4: Run full test suite to confirm nothing broken**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_comparison.py
git commit -m "feat: add comparison CLI with promote prompt and results saving"
```

---

## Self-Review

**Spec coverage:**

- ✅ Single-game viewer with per-turn table (Task 5)
- ✅ Multi-game comparison (Task 4 + 6)
- ✅ Champion I/O with JSON serialization of tuple keys (Task 2)
- ✅ `--promote` as standalone flag for first-time setup (Task 6)
- ✅ Interactive promote prompt after winning comparison (Task 6)
- ✅ Results saved to `scripts/results/YYYY-MM-DD-HH-MM.json` (Task 6)
- ✅ `run_comparison` importable as module (Task 4)
- ✅ Old `run_game.py` removed (Task 5)

**No placeholders:** All steps contain complete code.

**Type consistency:** `run_single_game`, `run_comparison`, `load_champion`, `save_champion` signatures used consistently across tasks 2–6.
