"""CLAUDE.md must declare the tuned-constant update convention (issue #96).

PR #72 surfaced repeated doc drift: old values survived in `.claude/docs/`,
decimal forms were missed when only the percent form was grepped, and
docs cited hard-coded numbers that silently rotted when constants changed.

These tests pin the convention rule itself (CLAUDE.md structure) and enforce
N_GAMES consistency in the wiki, mirroring what test_docs_promotion_threshold.py
does for PROMOTION_THRESHOLD.
"""

import re
from pathlib import Path

from trials.run_trials import N_GAMES

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
TUNING_PIPELINE = REPO_ROOT / "docs" / "wiki" / "Tuning-Pipeline.md"


class TestConventionRuleInClaudeMd:
    """CLAUDE.md must contain the full-repo-grep convention rule."""

    def test_convention_instructs_grep(self):
        """The rule must explicitly say to grep the repo on constant changes."""
        assert "grep" in CLAUDE_MD.read_text()

    def test_convention_covers_percent_and_decimal_forms(self):
        """The rule must name both the percent and decimal representations."""
        text = CLAUDE_MD.read_text()
        has_percent = "percent" in text.lower() or re.search(r"\d+%", text)
        has_decimal = "decimal" in text.lower()
        assert has_percent, "CLAUDE.md does not mention the percent form"
        assert has_decimal, "CLAUDE.md does not mention the decimal form"

    def test_convention_covers_claude_docs_tree(self):
        """The rule must explicitly name .claude/docs/ as a tree to update."""
        assert ".claude/docs" in CLAUDE_MD.read_text()

    def test_convention_instructs_cite_by_name(self):
        """The rule must say to cite constants by name instead of hardcoding."""
        text = CLAUDE_MD.read_text()
        assert "by name" in text.lower(), "expected 'by name' instruction in CLAUDE.md"

    def test_convention_exempts_archive_and_superpowers(self):
        """The rule must exempt archive/ and superpowers/ dated snapshots."""
        text = CLAUDE_MD.read_text()
        assert "archive" in text, "CLAUDE.md does not name the archive/ exemption"
        assert "superpowers" in text, (
            "CLAUDE.md does not name the superpowers/ exemption"
        )

    def test_convention_names_promotion_threshold_as_example(self):
        """PROMOTION_THRESHOLD must appear as a named drift-prone example."""
        assert "PROMOTION_THRESHOLD" in CLAUDE_MD.read_text()

    def test_convention_names_n_games_as_example(self):
        """N_GAMES must appear as a named drift-prone example."""
        assert "N_GAMES" in CLAUDE_MD.read_text()


class TestNGamesWikiConsistency:
    """Tuning-Pipeline.md must stay consistent with the N_GAMES code constant."""

    def test_constants_table_n_games_matches_code(self):
        """The Constants table value for N_GAMES must equal the code constant."""
        text = TUNING_PIPELINE.read_text()
        expected = str(N_GAMES)
        for line in text.splitlines():
            if "N_GAMES" in line and "|" in line:
                assert expected in line, (
                    f"stale N_GAMES in Constants table: {line!r} (want {expected})"
                )

    def test_alternation_description_matches_n_games(self):
        """The 'Over N games' prose must cite the current N_GAMES value."""
        text = TUNING_PIPELINE.read_text()
        half = N_GAMES // 2
        for line in text.splitlines():
            if "games as P0" in line:
                assert str(N_GAMES) in line, (
                    f"stale total game count in alternation description: {line!r}"
                )
                assert str(half) in line, (
                    f"stale per-side game count in alternation description: {line!r}"
                )
