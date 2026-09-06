"""Gotchas.md's SKIP_COMBOS description must match src.config.SKIP_COMBOS.

Issue #218: the doc listed 7 pairs, including a stale ``FORTRESS→HARDENED_ENEMY``
entry that was never actually in the code's ``SKIP_COMBOS`` set (that combo has a
live ``frac_fortress_hardened_enemy`` param and is exercised by `plan_expansion`).
This test pins the doc's bullet to the code so the two cannot drift apart again.
"""
from pathlib import Path

from src.config import SKIP_COMBOS

REPO_ROOT = Path(__file__).parent.parent
GOTCHAS_MD = REPO_ROOT / "docs" / "wiki" / "Gotchas.md"


def _skip_combos_line():
    for line in GOTCHAS_MD.read_text().splitlines():
        if "SKIP_COMBOS" in line:
            return line
    raise AssertionError("Gotchas.md has no SKIP_COMBOS line")


class TestSkipCombosDocMatchesCode:
    def test_every_combo_pair_listed_in_doc(self):
        line = _skip_combos_line()
        missing = [
            f"{src}→{tgt}" for src, tgt in SKIP_COMBOS if f"{src}→{tgt}" not in line
        ]
        assert not missing, f"Gotchas.md SKIP_COMBOS bullet is missing: {missing}"

    def test_doc_count_matches_code(self):
        line = _skip_combos_line()
        assert f"{len(SKIP_COMBOS)} " in line, (
            f"Gotchas.md SKIP_COMBOS bullet must state the count {len(SKIP_COMBOS)}"
        )

    def test_fortress_hardened_enemy_not_listed_as_blocked(self):
        """FORTRESS→HARDENED_ENEMY is not in SKIP_COMBOS — it must not appear
        in the doc's blocked-pairs bullet."""
        assert ("FORTRESS", "HARDENED_ENEMY") not in SKIP_COMBOS
        line = _skip_combos_line()
        assert "FORTRESS→HARDENED_ENEMY" not in line
