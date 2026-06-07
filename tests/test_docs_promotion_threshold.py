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


# Dated snapshots (archived plans, design specs) record the ORIGINAL figure
# (0.55) on purpose — they are historical records, not living reference, so they
# are exempt from the match-the-code decimal check below.
_HISTORICAL_PARTS = {"archive", "superpowers"}


def _living_doc_files():
    """Living Markdown docs: skip vendored/protected trees and dated snapshots."""
    skip = _EXCLUDED_PARTS | _HISTORICAL_PARTS
    return [p for p in REPO_ROOT.rglob("*.md") if skip.isdisjoint(p.parts)]


class TestThresholdDecimalMatchesCode:
    """Any living doc that states a decimal PROMOTION_THRESHOLD must equal the
    code constant — catches the decimal form (0.55) the percentage scan misses,
    repo-wide across living docs (not just docs/wiki). Lines that merely mention
    PROMOTION_THRESHOLD without a decimal (e.g. "≥ 65%", or by name) are ignored,
    as are unrelated decimals on other lines (param values, win-rate buckets)."""

    def test_living_docs_threshold_decimal_matches_code(self):
        expected = str(PROMOTION_THRESHOLD)
        bad = []
        for md in _living_doc_files():
            for line in md.read_text().splitlines():
                if "PROMOTION_THRESHOLD" not in line:
                    continue
                for dec in re.findall(r"0\.\d+", line):
                    if dec != expected:
                        bad.append(f"{md.relative_to(REPO_ROOT)}: {dec} (want {expected})")
        assert not bad, f"stale PROMOTION_THRESHOLD decimal in living docs: {bad}"
