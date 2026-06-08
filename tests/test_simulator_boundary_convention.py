"""Convention enforcement: boundary-split guard rule for simulator correctness.

Issue #102 / PR #72 combat-resolution: splitting ``x <= 0`` into branches for
``winner != planet.owner`` (``> 0``), ``winner == planet.owner`` (tie hold), and
a fallback ``else`` silently allowed the ``elif winner == planet.owner`` branch to
fire when ``surviving < 0`` — the incumbent was the largest SINGLE stack but lost
to the COMBINED attackers.  The fix guarded on ``surviving == 0`` exactly.

CLAUDE.md must document this pattern so future branch-splits ship correct guards
and a regression test covering the strictly-negative case.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _text():
    return CLAUDE_MD.read_text()


class TestSimulatorBoundaryConventionDocumented:
    """CLAUDE.md must document the boundary-split guard rule under Simulator correctness."""

    def test_simulator_correctness_section_exists(self):
        """CLAUDE.md must have a 'Simulator correctness' heading or note."""
        text = _text().lower()
        assert "simulator correctness" in text, (
            "CLAUDE.md is missing a 'Simulator correctness' section. "
            "Add one near the lookahead/combat references so maintainers "
            "know the boundary-split rule before editing step_state."
        )

    def test_equality_boundary_guard_rule_stated(self):
        """Convention must state that equality branches use == boundary, not a loose elif."""
        text = _text()
        # We check for the canonical form used in the fix: "== 0"
        assert "== 0" in text, (
            "CLAUDE.md must state that the equality/tie branch must test the exact "
            "boundary (e.g. '== 0'), not a loose elif that silently swallows "
            "the strictly-negative case (PR #72 motivating failure)."
        )

    def test_negative_case_must_be_explicit(self):
        """Convention must state that strictly-negative (or over-boundary) cases need explicit handling."""
        text = _text().lower()
        has_negative = "< 0" in text or "strictly-negative" in text or "strictly negative" in text
        assert has_negative, (
            "CLAUDE.md must state that the strictly-negative (surviving < 0) case "
            "must be handled explicitly, not silently swallowed by a loose elif."
        )

    def test_regression_test_required(self):
        """Convention must require a regression test for the strictly-negative/over-boundary case."""
        text = _text().lower()
        assert "regression test" in text, (
            "CLAUDE.md must require a regression test covering the strictly-negative "
            "(or strictly-greater) case whenever a <=/>= guard is decomposed into branches."
        )

    def test_pr72_combat_resolution_cited(self):
        """Convention must reference PR #72 in the combat/boundary-split context."""
        text = _text()
        # "combat" only appears in the new Simulator correctness section — not in
        # the existing doc-invariant section — so this fails until the rule is added.
        assert "combat" in text.lower(), (
            "CLAUDE.md must reference the PR #72 combat-resolution context as the "
            "motivating failure for the boundary-split rule."
        )
