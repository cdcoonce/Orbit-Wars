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

import pytest

from trials.run_trials import N_GAMES, N_TRIALS, N_WORKERS

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
TUNING_PIPELINE = REPO_ROOT / "docs" / "wiki" / "Tuning-Pipeline.md"

# Vendored/generated/protected trees — never police these for doc drift.
# .claude/: harness auto-denies edits, cannot be kept current from CI.
# .afk/: transient worktree copies of in-flight branches, not canonical docs.
_EXCLUDED_PARTS = {".venv", "node_modules", ".claude", ".afk"}

# Intentionally-dated snapshots that record historical figures on purpose.
# archive/ and superpowers/ preserve original design values (e.g. N_GAMES=10,
# PROMOTION_THRESHOLD=0.55) as historical records — they are exempt from
# match-the-code checks.
_HISTORICAL_PARTS = {"archive", "superpowers"}


def _living_doc_files():
    """Every tracked Markdown doc, skipping vendored/protected trees and dated snapshots."""
    skip = _EXCLUDED_PARTS | _HISTORICAL_PARTS
    return [p for p in REPO_ROOT.rglob("*.md") if skip.isdisjoint(p.parts)]


# Matches N_GAMES followed by an optional closing backtick (Markdown table quoting),
# then = or | (table delimiter), then a bare integer.
# Catches inline assignment form (N_GAMES=40) and wiki table form (| `N_GAMES` | 40 |).
_N_GAMES_VALUE_RE = re.compile(r"N_GAMES`?\s*[=|]\s*(\d+)")


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


class TestNWorkersNTrialsWikiConsistency:
    """Tuning-Pipeline.md must stay consistent with the N_WORKERS/N_TRIALS code
    constants (issue #201).

    N_GAMES and PROMOTION_THRESHOLD already have pinning tests in this table;
    N_WORKERS and N_TRIALS were documented alongside them with no equivalent
    guard, so either could silently drift with no CI signal. Mirrors
    TestNGamesWikiConsistency.test_constants_table_n_games_matches_code, using
    one parametrized test for both constants per the doc-constant-pinning
    convention above.
    """

    @pytest.mark.parametrize(
        ("name", "value"),
        [("N_WORKERS", N_WORKERS), ("N_TRIALS", N_TRIALS)],
    )
    def test_constants_table_matches_code(self, name, value):
        """The Constants table Value cell must equal the code constant exactly."""
        text = TUNING_PIPELINE.read_text()
        expected = str(value)
        found = False
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[0].strip("`") != name:
                continue
            found = True
            assert cells[1] == expected, (
                f"stale {name} in Constants table: {line!r} (want {expected})"
            )
        assert found, f"{name} not found in Constants table of {TUNING_PIPELINE}"


class TestFullConstantVerificationConvention:
    """CLAUDE.md must document the re-verify-all-constants rule (issue #150).

    PR #72 left two adjacent stale values: N_GAMES was still documented as 20
    while PROMOTION_THRESHOLD prose was updated, and an acceptance-criteria bullet
    list still hard-coded PROMOTION_THRESHOLD=0.55 after the headline was fixed.
    The existing tuned-constant rule only triggers on *changing* a value; this new
    rule covers editing a doc section that *enumerates* multiple constants and
    silently leaving the ones you weren't focused on stale.
    """

    def test_convention_requires_reverification_of_all_constants(self):
        """CLAUDE.md must instruct maintainers to re-verify ALL enumerated constants."""
        text = CLAUDE_MD.read_text()
        has_reverify = "re-verify" in text.lower() or "re-check" in text.lower()
        assert has_reverify, (
            "CLAUDE.md must instruct maintainers to re-verify ALL constants enumerated "
            "in a doc section, not just the one being changed — see issue #150."
        )

    def test_convention_names_acceptance_criteria_in_scope(self):
        """The rule must explicitly name acceptance-criteria bullet lists as in-scope."""
        text = CLAUDE_MD.read_text()
        assert "acceptance" in text.lower() and "criteria" in text.lower(), (
            "CLAUDE.md must name acceptance-criteria bullet lists as in-scope for the "
            "full-constant-verification rule — they drifted in PR #72 even after the "
            "headline prose was fixed."
        )

    def test_convention_names_inline_plan_doc_numbers_in_scope(self):
        """The rule must explicitly name inline plan-doc numbers as in-scope."""
        text = CLAUDE_MD.read_text()
        assert "inline" in text.lower(), (
            "CLAUDE.md must name inline plan-doc numbers as in-scope for the "
            "full-constant-verification rule — plan-doc numbers drifted in PR #72."
        )


class TestDocConstantPinningConvention:
    """CLAUDE.md must generalize doc-constant pinning to a convention, not a
    bespoke test per constant (issue #103).

    PR #72 surfaced the same doc-drift failure mode twice in one PR:
    PROMOTION_THRESHOLD (stale 55%/0.55) and N_GAMES (docs/wiki/Tuning-Pipeline.md
    said 20 while trials/run_trials.py set 40, despite the wiki claiming the
    constants "All live in `trials/run_trials.py`"). Each was fixed with a
    separate hand-written pinning test. This rule requires future documented
    constants to be either name-cited or covered by a test by default, favoring
    one parametrized guard over N per-constant tests.
    """

    def test_convention_requires_name_cite_or_pinning_test(self):
        """The rule must require a name-cite or an importing pinning test."""
        text = CLAUDE_MD.read_text()
        assert "name-cited" in text.lower() or "cite" in text.lower(), (
            "CLAUDE.md must require documented constants to be name-cited"
        )
        assert "importing test" in text.lower(), (
            "CLAUDE.md must require an importing test as the alternative to a name-cite"
        )

    def test_convention_cites_n_games_20_vs_40_drift(self):
        """The rule must cite the PR #72 N_GAMES 20-vs-40 drift by number."""
        text = CLAUDE_MD.read_text()
        assert "20" in text and "40" in text, (
            "CLAUDE.md must cite the N_GAMES 20-vs-40 drift from PR #72"
        )

    def test_convention_cites_all_live_in_wiki_comment(self):
        """The rule must quote the wiki's 'All live in trials/run_trials.py' claim."""
        text = CLAUDE_MD.read_text()
        assert "All live in" in text, (
            "CLAUDE.md must cite the wiki's 'All live in trials/run_trials.py' comment"
        )

    def test_convention_prefers_parametrized_over_per_constant(self):
        """The rule must prefer one parametrized guard over per-constant tests."""
        text = CLAUDE_MD.read_text().lower()
        assert "parametrized" in text, (
            "CLAUDE.md must prefer a parametrized test over per-constant tests"
        )
        assert "per-constant" in text or "per constant" in text, (
            "CLAUDE.md must name the per-constant-test alternative it's discouraging"
        )


class TestNGamesLivingDocConsistency:
    """No living doc should cite N_GAMES with a stale value (issue #150).

    Mirrors TestThresholdDecimalMatchesCode from test_docs_promotion_threshold.py
    for the N_GAMES constant. Dated snapshots under archive/ and superpowers/ are
    exempt — they preserve historical figures intentionally.
    """

    def test_n_games_regex_matches_backtick_table_form(self):
        """_N_GAMES_VALUE_RE must match the backtick-quoted Markdown table form.

        The wiki uses ``| `N_GAMES` | 40 |`` (backtick-quoted identifier), so the
        regex must allow an optional closing backtick after the constant name.
        """
        line = "| `N_GAMES`             | 40    | Games per trial (challenger vs champion) |"
        matches = _N_GAMES_VALUE_RE.findall(line)
        assert matches == ["40"], (
            f"regex failed to match backtick table form; got {matches!r}. "
            "The wiki uses `N_GAMES` with backtick-quotes: the pattern needs "
            "to allow an optional backtick after 'N_GAMES'."
        )

    def test_no_living_doc_cites_stale_n_games_value(self):
        """Any living doc that cites N_GAMES with an explicit integer must use the code value."""
        expected = str(N_GAMES)
        bad = []
        for md in _living_doc_files():
            for m in _N_GAMES_VALUE_RE.finditer(md.read_text()):
                val = m.group(1)
                if val != expected:
                    bad.append(
                        f"{md.relative_to(REPO_ROOT)}: N_GAMES={val} (want {expected})"
                    )
        # CI limitation: .claude/docs/project.md cannot be governed here because the
        # harness auto-denies edits to .claude/. If that file carries a stale N_GAMES
        # value, a maintainer with .claude/ write access must fix it by hand.
        assert not bad, f"stale N_GAMES value in living docs: {bad}"
