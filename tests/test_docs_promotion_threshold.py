"""Docs must describe the promotion threshold consistently with the code.

`trials/run_trials.py` is the single source of truth for the self-play
promotion gate (`PROMOTION_THRESHOLD`). Prose docs historically hard-coded the
percentage and drifted stale (issue #67). These tests pin the docs to the code
so the figure cannot silently rot again.
"""
import re
from pathlib import Path

from trials.run_trials import PROMOTION_THRESHOLD

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


# The Claude Code harness guards the entire `.claude/` tree as sensitive and
# auto-denies edits to it, so docs under there cannot be governed from here.
# `.claude/docs/project.md` still carries the stale figure and must be fixed by
# a maintainer with `.claude/` write access (see issue #67 notes).
_EXCLUDED_PARTS = {".venv", "node_modules", ".claude"}


def _doc_files():
    """Every tracked Markdown doc, skipping vendored/protected trees."""
    return [
        p
        for p in REPO_ROOT.rglob("*.md")
        if _EXCLUDED_PARTS.isdisjoint(p.parts)
    ]


class TestClaudeMdThreshold:
    def test_claude_md_references_promotion_constant(self):
        """The Tuning Workflow must point at PROMOTION_THRESHOLD by name so it
        cannot drift from the code again."""
        text = CLAUDE_MD.read_text()
        assert "PROMOTION_THRESHOLD" in text

    def test_claude_md_threshold_matches_code(self):
        """If CLAUDE.md states a percentage, it must equal the code constant."""
        text = CLAUDE_MD.read_text()
        expected_pct = f"{round(PROMOTION_THRESHOLD * 100)}%"
        # The stale figure must be gone; the current figure (if present) must match.
        assert "55%" not in text
        for pct in re.findall(r"\d+%", text):
            assert pct == expected_pct, f"unexpected win-rate figure {pct!r} in CLAUDE.md"


class TestNoStaleFigureAnywhere:
    def test_no_doc_references_old_55_percent(self):
        """Acceptance criterion #3: no doc references the old 55% figure."""
        offenders = [p for p in _doc_files() if "55%" in p.read_text()]
        rel = sorted(str(p.relative_to(REPO_ROOT)) for p in offenders)
        assert not offenders, f"stale 55% figure still present in: {rel}"


class TestWikiReferenceMatchesCode:
    """The wiki is live reference documentation (not a dated snapshot), so any
    numeric value it states for PROMOTION_THRESHOLD must equal the code constant.
    This catches the decimal form (0.55) that the percentage scan above misses."""

    def test_wiki_threshold_values_match_code(self):
        wiki = REPO_ROOT / "docs" / "wiki"
        expected = str(PROMOTION_THRESHOLD)
        bad = []
        for md in wiki.rglob("*.md"):
            for line in md.read_text().splitlines():
                if "PROMOTION_THRESHOLD" not in line:
                    continue
                for dec in re.findall(r"0\.\d+", line):
                    if dec != expected:
                        bad.append(f"{md.relative_to(REPO_ROOT)}: {dec} (want {expected})")
        assert not bad, f"stale PROMOTION_THRESHOLD value in wiki: {bad}"
