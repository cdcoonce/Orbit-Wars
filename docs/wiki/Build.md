## What it does

`build.py` concatenates `src/` modules into a single `submission.py` for Kaggle submission. Kaggle requires one self-contained Python file; all relative imports (`from .module import ...`) are stripped so the inlined modules reference each other by name in the flat global namespace. `kaggle_environments` imports are deduplicated into a single canonical block at the top of the file. See [Home](Home.md) for the broader workflow and [Tuning-Pipeline](Tuning-Pipeline.md) for how `submission.py` fits into the release cycle.

## Module bundling order

`build.py` concatenates modules in this exact sequence (from `SRC_FILES`):

| Position | File                | Why here                                                         |
| -------- | ------------------- | ---------------------------------------------------------------- |
| 1        | `src/math_utils.py` | Pure math helpers; no internal deps                              |
| 2        | `src/config.py`     | `PARAMS`, `PARAM_SPACE`, `SKIP_COMBOS`; imported by most modules |
| 3        | `src/lookahead.py`  | Imports from `config`; needed by `strategy`                      |
| 4        | `src/comets.py`     | Comet-ID helper; needed by `strategy`                            |
| 5        | `src/endgame.py`    | Endgame classifier; needed by `strategy`                         |
| 6        | `src/strategy.py`   | Core decision logic; imports all of the above                    |
| 7        | `src/agent.py`      | Entry point `agent()`; imports `strategy`                        |

Order is load-bearing: if module A imports from module B, B must appear earlier in the bundle. Violating this produces a `NameError` at Kaggle runtime that won't appear locally (where the real package imports work).

Before the module chunks, `build.py` emits a single canonical `kaggle_environments` import block:

```python
from kaggle_environments.envs.orbit_wars.orbit_wars import (
    CENTER,
    ROTATION_RADIUS_LIMIT,
    SUN_RADIUS,
    Fleet,
    Planet,
)
```

## Import stripping logic

`build.py` applies two regex substitutions to each source file before inlining:

**Relative imports** — matches both single-line and multi-line parenthesised forms:

```python
RELATIVE_IMPORT_RE = re.compile(
    r"from \.[^\s]+\s+import\s*\([^)]*\)\s*\n|"
    r"^\s*from \.[^\s]+ import [^\n]+\n?",
    re.MULTILINE | re.DOTALL,
)
```

Any line of the form `from .module import ...` (or multi-line with parentheses) is replaced with an empty string. This covers `from .config import PARAMS`, `from .lookahead import step_state`, etc.

**kaggle_environments imports** — stripped from individual modules to avoid duplicates, then replaced by the single canonical block at the top of the bundle. The regex handles both single-line and multi-line parenthesised forms:

```python
KAGGLE_IMPORT_RE = re.compile(
    r"from kaggle_environments[^\n]*import\s*\([^)]*\)\s*\n|"
    r"from kaggle_environments[^\n]*import[^\n]*\n",
    re.DOTALL,
)
```

If `grep "from kaggle_environments" submission.py` returns any output, a deduplication failure leaked through — compare the leaking line's whitespace against both alternatives above.

After stripping, each module's content is appended with a comment banner (`# --- src/foo.py ---`) for orientation when reading `submission.py`.

## How to run

```bash
python build.py          # produces submission.py
```

Note: `build.py` has no project-specific dependencies (only `re` and `pathlib`), so plain `python build.py` works from any environment with Python 3. `uv run python build.py` also works — it simply activates the venv first, which is harmless. The Kaggle submission environment doesn't use `uv` at all, so the script avoids the `uv run` prefix to keep the workflow clearly separate from Kaggle's runtime.

`build.py` runs a quick self-check after writing: it asserts `"def agent(" in content`, so a missing `agent.py` or a botched strip will fail loudly rather than silently uploading a broken file.

## How to verify the output

```bash
head -50 submission.py          # check imports are clean and canonical block is present
grep "from \." submission.py    # should return nothing — all relative imports stripped
wc -l submission.py             # sanity check — should be several hundred lines
```

If `grep "from \."` returns any output, a relative import leaked through. Check the `RELATIVE_IMPORT_RE` pattern against the leaking line's exact whitespace and parenthesisation.

## How to debug submission.py

If `submission.py` behaves differently from the dev version:

1. **Module order** — confirm all modules are present in the right sequence. `grep "^# ---" submission.py` lists the inlined files in order.
2. **Leaked relative imports** — `grep "from \." submission.py`; any output is a bug.
3. **Stale PARAMS** — if you edited `src/config.py` after the last build, the old values are in `submission.py`. Always rebuild before submitting. `grep "lookahead_turns" submission.py` to spot-check a key constant.
4. **Missing new module** — if you added a `src/` file and forgot to add it to `SRC_FILES` in `build.py`, the symbol it defines will be undefined at runtime → `NameError`. See gotcha below.

## Submit command

```bash
kaggle competitions submit -c orbit-wars -f submission.py -m "description"
```

## Gotcha

**Adding a new `src/` module:** you must add it to `SRC_FILES` in `build.py` at the correct position — before any module that imports from it. Forgetting to add it produces a `NameError` at Kaggle runtime that won't appear locally (local runs use the real package import system). The symptom is a crash on the first turn with a name that exists only in the missing module.
