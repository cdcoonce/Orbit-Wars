"""docs/wiki/tests/overview.md's Test Files table must list every tests/test_*.py file.

Issue #220: the table documented only 8 of 20 test files, so a reader could not
tell what coverage already existed before adding new tests. This walks tests/
and pins every filename into the doc so new test files can't silently go
undocumented again.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TESTS_DIR = REPO_ROOT / "tests"
OVERVIEW = REPO_ROOT / "docs" / "wiki" / "tests" / "overview.md"


def _test_file_names():
    return sorted(p.name for p in TESTS_DIR.glob("test_*.py"))


def _documented_test_files():
    """Filenames appearing as the first column of a Test Files table row.

    Only rows whose first cell is `` `tests/<name>` `` count — a filename
    mentioned in prose, a note, or a link elsewhere in the doc does not.
    """
    documented = set()
    in_table = False
    for line in OVERVIEW.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_table = stripped == "## Test Files"
            continue
        if not in_table or not stripped.startswith("|"):
            continue
        first_cell = stripped.split("|")[1].strip()
        if first_cell.startswith("`tests/") and first_cell.endswith("`"):
            documented.add(first_cell.strip("`").split("/", 1)[1])
    return documented


class TestTestFilesTableComplete:
    def test_every_test_file_is_documented(self):
        documented = _documented_test_files()
        missing = [name for name in _test_file_names() if name not in documented]
        assert not missing, (
            f"docs/wiki/tests/overview.md's Test Files table is missing rows "
            f"for: {missing}. Add a row naming the module covered and its key "
            "invariant groups."
        )

    def test_test_strategy_row_does_not_claim_value_tier_coverage(self):
        """value_tier was removed from src/strategy.py and tests/test_strategy.py
        has no test for it — the row must not claim that coverage (issue #314)."""
        for line in OVERVIEW.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("| `tests/test_strategy.py`"):
                assert "value tier" not in stripped.lower(), (
                    "tests/test_strategy.py row still claims value-tier coverage, "
                    "but value_tier was removed from src/strategy.py and no test "
                    "for it exists."
                )
                return
        raise AssertionError("tests/test_strategy.py row not found in overview.md")
