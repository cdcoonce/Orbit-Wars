"""docs/wiki/Home.md's Module Inventory table must not carry raw line counts.

Issue #319: the table hardcoded a `Lines` column that drifted stale for nearly
every row (e.g. `src/agent.py` documented as 13 lines while the file had grown
to 63) because raw line counts rot on every unrelated edit and carry no
functional meaning. The fix drops the column entirely rather than chasing the
number with a tolerance-based drift test. The `PARAMS` cell must also cite the
dict by name (per CLAUDE.md's cite-by-name convention) instead of transcribing
a stale key count.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HOME = REPO_ROOT / "docs" / "wiki" / "Home.md"


def _module_inventory_lines():
    lines = HOME.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## Module Inventory")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("## "))
    return lines[start:end]


class TestModuleInventoryHasNoLinesColumn:
    def test_no_lines_column_header(self):
        header = next(line for line in _module_inventory_lines() if line.strip().startswith("| File"))
        assert "Lines" not in header, (
            "Module Inventory table must not have a Lines column — raw line "
            "counts drift on every unrelated edit and carry no functional "
            "meaning (issue #319)."
        )

    def test_params_cell_cites_by_name_not_transcribed_count(self):
        table_text = "\n".join(_module_inventory_lines())
        assert "-key" not in table_text, (
            "Module Inventory table must not transcribe a PARAMS key count — "
            "cite `PARAMS` (src/config.py) by name instead, per CLAUDE.md's "
            "cite-by-name convention (issue #319)."
        )
        params_row = next(
            line for line in _module_inventory_lines() if line.strip().startswith("| `src/config.py`")
        )
        assert "`PARAMS`" in params_row, (
            "src/config.py row must cite `PARAMS` by name."
        )
