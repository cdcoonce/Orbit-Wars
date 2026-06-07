"""Convention enforcement: doc-invariant tests must scan all representations and the full repo.

Issue #97: PR #72 revealed two failure modes — the stale-55% guard only scanned
for the literal "55%" (missing the decimal form 0.55), and it excluded `.claude/`
without documenting why. These tests pin the documented convention so future
doc-invariant tests are written complete from the start.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _text():
    return CLAUDE_MD.read_text()


class TestDocInvariantConventionDocumented:
    """CLAUDE.md must document the three rules for writing doc-invariant tests."""

    def test_convention_section_exists(self):
        """CLAUDE.md must have a doc-invariant test conventions section."""
        assert "doc-invariant" in _text().lower(), (
            "CLAUDE.md is missing a doc-invariant test conventions section. "
            "Add one so maintainers know the rules before writing new doc-invariant tests."
        )

    def test_convention_requires_all_value_representations(self):
        """Convention must state tests must check both percent and decimal representations."""
        text = _text().lower()
        assert "percent" in text and "decimal" in text, (
            "Convention must state that all value representations (percent and decimal) "
            "must be checked — scanning only one literal allows other forms to slip through "
            "(see issue #72)."
        )

    def test_convention_requires_full_repo_scan(self):
        """Convention must state the scan must cover the full repo."""
        text = _text().lower()
        assert "full repo" in text or "full-repo" in text, (
            "Convention must state tests must scan the full repo, not a partial subtree."
        )

    def test_convention_requires_justified_exclusions(self):
        """Convention must state that any directory exclusion must be commented/justified."""
        text = _text().lower()
        assert "exclusion" in text and "comment" in text, (
            "Convention must state that directory exclusions must be explicitly justified "
            "in a comment at the exclusion site."
        )

    def test_convention_requires_ci_limitation_documented(self):
        """Convention must state that CI-ungovernable doc trees must be documented in the test."""
        text = _text().lower()
        # Must reference .claude/ as the canonical example of an ungovernable tree
        has_claude_ref = ".claude/" in _text()
        has_doc_ref = "document" in text or "documented" in text
        assert has_claude_ref and has_doc_ref, (
            "Convention must note that when a doc tree cannot be governed from CI "
            "(e.g. .claude/ is harness-blocked), the limitation must be documented "
            "in the test rather than silently skipped."
        )
