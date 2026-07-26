"""Convention enforcement: fixed-field records must be tuples/structures, not lists (issue #98).

PR #85's ``detect_threats`` accumulator stored a fixed two-field record (summed
ships, earliest ETA) as a ``list[int]`` mutated via ``agg[0]``/``agg[1]``. The
positional indices made each slot's meaning implicit and easy to swap during
edits. The fix rebuilt the record as an explicit ``(ships, eta)`` 2-tuple with
named unpacking.

CLAUDE.md must document this convention so future fixed-arity records are
modeled as tuples/NamedTuples/dataclasses instead of positionally-indexed
mutable lists.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _text():
    return CLAUDE_MD.read_text()


class TestNamedRecordConventionDocumented:
    """CLAUDE.md must document the fixed-field-record convention."""

    def test_rule_states_tuple_or_named_structure(self):
        """Convention must state a fixed-field record should be a tuple/NamedTuple/dataclass."""
        text = _text().lower()
        assert "namedtuple" in text or "named tuple" in text, (
            "CLAUDE.md must state that a fixed set of named fields should be "
            "modeled as a tuple with named unpacking, or a NamedTuple/dataclass."
        )
        assert "dataclass" in text, (
            "CLAUDE.md must mention dataclass as an acceptable small named structure."
        )

    def test_rule_forbids_positional_mutable_list(self):
        """Convention must call out positionally-indexed mutable lists as the anti-pattern."""
        text = _text().lower()
        assert "positionally-indexed" in text or "positional" in text, (
            "CLAUDE.md must name the anti-pattern: a mutable list mutated via "
            "positional indices like [0]/[1] for a fixed set of distinct fields."
        )

    def test_rationale_stated(self):
        """Convention must explain why: implicit/edit-fragile positional access vs self-documenting unpacking."""
        text = _text().lower()
        assert "edit-fragile" in text or "easy to swap" in text or "implicit" in text, (
            "CLAUDE.md must give the rationale: positional [0]/[1] access is "
            "implicit and edit-fragile, while named unpacking is self-documenting."
        )

    def test_scope_excludes_homogeneous_collections(self):
        """Convention must clarify it targets fixed-field records, not genuine homogeneous collections."""
        text = _text().lower()
        assert "homogeneous" in text, (
            "CLAUDE.md must clarify the rule targets fixed-field records, not "
            "genuine homogeneous collections where a list is appropriate."
        )

    def test_pr85_detect_threats_cited(self):
        """Convention must reference PR #85's detect_threats accumulator as the motivating example."""
        text = _text().lower()
        assert "detect_threats" in text or "pr #85" in text, (
            "CLAUDE.md must cite PR #85's detect_threats agg[0]/agg[1] accumulator "
            "as the motivating failure for this convention."
        )
