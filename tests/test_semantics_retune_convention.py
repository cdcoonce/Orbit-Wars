"""Convention enforcement: semantics changes must flag coupled tuned params for re-tune.

Issue #108: PR #85 changed `detect_threats` to aggregate converging enemy fleets
per planet, which changed what `defense_incoming_multiplier` multiplies (combined
vs single-fleet incoming ships). PR #85 only added a one-off "Pending re-tune" note
rather than a standing rule, so the next semantics change could repeat the mistake
of promoting params tuned against stale behavior. These tests pin a generalized
rule in CLAUDE.md so this doesn't need to be reinvented per-PR.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _text():
    return CLAUDE_MD.read_text()


class TestSemanticsRetuneConventionDocumented:
    """CLAUDE.md must document a generalized semantics-change re-tune rule."""

    def test_rule_not_tied_to_defense_incoming_multiplier_alone(self):
        """The generalized rule section must exist independent of the specific constant."""
        text = _text().lower()
        assert "semantics" in text and "re-tune" in text, (
            "CLAUDE.md is missing a generalized semantics-change re-tune rule. "
            "Add one so the next PR that changes simulator/scoring/threat semantics "
            "doesn't repeat PR #85's one-off note instead of following a standing rule."
        )

    def test_rule_requires_inline_coupling_note(self):
        """Rule must require a coupling note at the constant's definition in src/config.py."""
        text = _text().lower()
        assert "coupling note" in text and "src/config.py" in text, (
            "Rule must require an inline coupling note at the constant's definition "
            "in src/config.py explaining what changed and why."
        )

    def test_rule_requires_study_db_reset(self):
        """Rule must require resetting trials/study.db as part of the re-tune workflow."""
        assert "rm trials/study.db" in _text(), (
            "Rule must document the re-tune workflow including `rm trials/study.db` "
            "to clear stale Bayesian priors."
        )

    def test_rule_requires_no_promotion_flag(self):
        """Rule must require explicitly marking affected params as not-for-promotion."""
        text = _text().lower()
        assert "not-for-promotion" in text or "not be promoted" in text, (
            "Rule must require explicitly flagging affected params as not-for-promotion "
            "until re-tuned."
        )

    def test_rule_cites_pr_85_as_motivating_example(self):
        """Rule must cite PR #85's multi-fleet aggregation as the motivating example."""
        assert "#85" in _text(), (
            "Rule must cite PR #85's multi-fleet aggregation change as the motivating "
            "example for why this convention exists."
        )
