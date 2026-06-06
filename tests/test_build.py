"""Smoke test for build.py — the glue that bundles src/ into submission.py.

build.py strips relative imports and re-injects a single hard-coded
KAGGLE_IMPORTS_BLOCK. If a src module references a kaggle symbol missing from
that block, the Kaggle bundle silently breaks at submission time. These tests
run the real build in an isolated copy and assert the artifact is sound.
"""

import ast
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
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
            "kaggle_environments"
        ):
            names.update(alias.name for alias in node.names)
    return names


def _kaggle_symbols_in_src():
    """Collect every name imported from kaggle_environments across src/*.py."""
    names = set()
    for path in sorted(SRC_DIR.glob("*.py")):
        names |= _kaggle_symbols_imported(path.read_text())
    return names


def test_kaggle_symbols_present_in_bundle(built_submission):
    """Every kaggle symbol imported in src/ must survive into the bundle's import
    block — catches the silent-drop fragility when a new symbol is added to a
    src module but not to build.py's hard-coded KAGGLE_IMPORTS_BLOCK."""
    needed = _kaggle_symbols_in_src()
    assert needed, "expected at least one kaggle_environments symbol in src/"
    have = _kaggle_symbols_imported(built_submission)
    missing = sorted(needed - have)
    assert not missing, f"kaggle symbols dropped from bundle import block: {missing}"
