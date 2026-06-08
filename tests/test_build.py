"""Smoke test for build.py — the glue that bundles src/ into submission.py.

build.py strips relative imports and re-injects a single hard-coded
KAGGLE_IMPORTS_BLOCK. If a src module references a kaggle symbol missing from
that block, the Kaggle bundle silently breaks at submission time. These tests
run the real build in an isolated copy and assert the artifact is sound.
"""

import ast
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
BUILD_SCRIPT = REPO_ROOT / "build.py"


@pytest.fixture(scope="module")
def built_submission(tmp_path_factory):
    """Run build.py against an isolated copy; return the generated submission text.

    Copies src/ and build.py into a temp dir and runs the build there so the
    generated submission.py lands in the temp dir (auto-cleaned) rather than
    polluting the repo root. Module-scoped so the build runs once for all the
    read-only assertions below.
    """
    tmp_path = tmp_path_factory.mktemp("build")
    shutil.copytree(SRC_DIR, tmp_path / "src")
    shutil.copy(BUILD_SCRIPT, tmp_path / "build.py")
    result = subprocess.run(
        [sys.executable, "build.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"
    submission = tmp_path / "submission.py"
    assert submission.exists(), "build.py did not write submission.py"
    return submission.read_text()


def _isolated_repo(tmp_path):
    """Copy src/ and build.py into tmp_path so the build is sandboxed."""
    shutil.copytree(SRC_DIR, tmp_path / "src")
    shutil.copy(BUILD_SCRIPT, tmp_path / "build.py")


def test_import_has_no_side_effects(tmp_path):
    """Importing build must not write submission.py or print to stdout."""
    _isolated_repo(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", "import build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", f"import produced stdout: {result.stdout!r}"
    assert not (tmp_path / "submission.py").exists(), "import wrote submission.py"


def test_build_function_returns_written_path(tmp_path):
    """build() writes submission.py and returns its path."""
    _isolated_repo(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", "import build; print(build.build())"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "submission.py").exists(), "build() did not write submission.py"
    assert result.stdout.strip().endswith("submission.py"), result.stdout


def test_submission_parses(built_submission):
    """The bundled submission must be syntactically valid Python."""
    ast.parse(built_submission)
    compile(built_submission, "submission.py", "exec")


def test_submission_defines_agent(built_submission):
    """Kaggle calls agent(obs, config); the bundle must define it."""
    assert "def agent(" in built_submission


def test_no_relative_imports_survive(built_submission):
    """Relative imports (from .module) are invalid in the flat bundle."""
    leftover = re.search(r"^\s*from \.", built_submission, re.MULTILINE)
    assert leftover is None, f"leftover relative import: {leftover.group(0)!r}"


def test_no_duplicate_stdlib_imports(built_submission):
    """Each stdlib import must appear exactly once in the bundle."""
    stdlib_lines = [
        line
        for line in built_submission.splitlines()
        if re.match(r"^import \w|^from \w", line)
        and not line.startswith("from kaggle_environments")
    ]
    counts = {}
    for line in stdlib_lines:
        counts[line] = counts.get(line, 0) + 1
    duplicates = {line: n for line, n in counts.items() if n > 1}
    assert not duplicates, f"duplicate stdlib imports in bundle: {duplicates}"


def test_no_mid_file_stdlib_imports(built_submission):
    """All stdlib imports must be in the top block, not scattered mid-file."""
    lines = built_submission.splitlines()
    first_section = next(
        (i for i, line in enumerate(lines) if line.startswith("# ---")),
        None,
    )
    assert first_section is not None, "no '# ---' section header found in bundle"
    body = "\n".join(lines[first_section:])
    mid_import = re.search(r"^(import \w|from \w)", body, re.MULTILINE)
    assert mid_import is None, f"import found mid-file: {mid_import.group(0)!r}"


def _kaggle_symbols_imported(source: str):
    """Collect every name imported from kaggle_environments in the given source.

    Walks the AST for `from kaggle_environments... import ...` statements and
    returns the bound names — i.e. what the code actually *imports*, not merely
    what it references. A whole-text search can't make that distinction: every
    kaggle symbol is also used throughout the bundled body, so a dropped import
    line still matches as a bare word. Parsing the import statements is the only
    way to catch a symbol silently missing from the bundle's import block.
    """
    names = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("kaggle_environments")
        ):
            names.update(alias.name for alias in node.names)
    return names


def _kaggle_symbols_in_src():
    """Collect every name imported from kaggle_environments across src/*.py."""
    names = set()
    for path in sorted(SRC_DIR.glob("*.py")):
        names |= _kaggle_symbols_imported(path.read_text())
    return names


def test_src_files_covers_all_src_modules():
    """Every src/*.py (except __init__.py) must appear in build.SRC_FILES.

    Guards against adding a module to src/ and forgetting to list it in the
    bundle, which causes a silent NameError at Kaggle runtime while local
    imports continue working fine.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("build", BUILD_SCRIPT)
    build_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_mod)

    src_modules = {p.name for p in SRC_DIR.glob("*.py") if p.name != "__init__.py"}
    bundled = {Path(p).name for p in build_mod.SRC_FILES}

    missing = sorted(src_modules - bundled)
    assert not missing, (
        f"src/ module(s) missing from build.SRC_FILES: {missing} — "
        f"add them to SRC_FILES in build.py"
    )


def test_kaggle_symbols_present_in_bundle(built_submission):
    """Every kaggle symbol imported in src/ must survive into the bundle's import
    block — catches the silent-drop fragility when a new symbol is added to a
    src module but not to build.py's hard-coded KAGGLE_IMPORTS_BLOCK."""
    needed = _kaggle_symbols_in_src()
    assert needed, "expected at least one kaggle_environments symbol in src/"
    have = _kaggle_symbols_imported(built_submission)
    missing = sorted(needed - have)
    assert not missing, f"kaggle symbols dropped from bundle import block: {missing}"


def _build_and_import_submission(tmp_path):
    """Build submission.py in tmp_path and return it as an imported module object."""
    _isolated_repo(tmp_path)
    result = subprocess.run(
        [sys.executable, "build.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"
    submission_path = tmp_path / "submission.py"
    assert submission_path.exists()
    spec = importlib.util.spec_from_file_location(
        "_submission_under_test", submission_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_docstring_not_stale():
    """build.py module docstring must not name a stale subset of bundled modules.

    If the docstring enumerates any .py filenames, every module in SRC_FILES
    must be named — not just the three that existed before config, lookahead,
    comets, and endgame were added.
    """
    spec = importlib.util.spec_from_file_location("build", BUILD_SCRIPT)
    build_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_mod)

    docstring = build_mod.__doc__ or ""
    bundled_names = {Path(p).name for p in build_mod.SRC_FILES}

    # If the docstring mentions any bundled module by name, all must be present.
    named = {name for name in bundled_names if name in docstring}
    if named:
        missing = sorted(bundled_names - named)
        assert not missing, (
            f"build.py docstring names some modules ({sorted(named)}) "
            f"but omits: {missing}"
        )


def test_submission_agent_matches_src_agent(tmp_path):
    """submission.agent(obs) returns the same moves as src.agent.agent(obs) for a
    fixed turn-0 observation.

    Catches behavioral divergence that syntax checks alone cannot detect — e.g. if
    build.py's regexes ever eat a non-import line, the bundle could plan different
    moves than src/agent.py.  Module-level state is reset on both sides before each
    call so the comparison is order-independent.
    """
    import src.agent as src_agent_mod

    sub = _build_and_import_submission(tmp_path)

    obs = {
        "planets": [
            (0, 0, 70.0, 50.0, 5, 20, 3),
            (1, 1, 30.0, 50.0, 5, 15, 2),
        ],
        "fleets": [],
        "player": 0,
        "angular_velocity": 0.03,
        "step": 0,
        "comet_planet_ids": None,
    }

    # Reset module-level tracking state so the comparison is order-independent
    src_agent_mod._initial_planets = None
    src_agent_mod._prev_comet_positions = {}
    sub._initial_planets = None
    sub._prev_comet_positions = {}

    assert src_agent_mod.agent(obs) == sub.agent(obs)
