"""Copilot review instructions must mirror CLAUDE.md conventions.

Issue #157: automated review footers on PR #85 and PR #72 recurringly
suggested adding Copilot custom instructions so the same repo conventions
that govern the coding agent also govern automated review, pre-empting
violations (the `surviving < 0` boundary-split bug, the 0.55/0.65 and
N_GAMES doc drift, the positionally-indexed `agg` list) instead of only
flagging them post-merge.

These tests pin the reviewer-facing file to restate the conventions rather
than duplicate code-derived values that can drift, per CLAUDE.md's own
"Cite Code-Derived Values by Name" rule.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
COPILOT_INSTRUCTIONS = REPO_ROOT / ".github" / "copilot-instructions.md"


def _copilot_text():
    return COPILOT_INSTRUCTIONS.read_text()


def _claude_text():
    return CLAUDE_MD.read_text()


class TestCopilotInstructionsExist:
    def test_file_exists(self):
        assert COPILOT_INSTRUCTIONS.is_file(), (
            "Expected .github/copilot-instructions.md to exist so automated "
            "review can apply the same conventions as CLAUDE.md."
        )


class TestCopilotInstructionsCiteClaudeMd:
    def test_references_claude_md_as_source_of_truth(self):
        text = _copilot_text()
        assert "CLAUDE.md" in text, (
            "Copilot instructions must point at CLAUDE.md as the source of "
            "truth rather than re-deriving conventions independently."
        )

    def test_does_not_hardcode_promotion_threshold_value(self):
        text = _copilot_text()
        for stale_literal in ("65%", "0.65", "55%", "0.55"):
            assert stale_literal not in text, (
                f"Copilot instructions must not hardcode {stale_literal!r} — "
                "cite PROMOTION_THRESHOLD by name so it cannot drift from "
                "trials/run_trials.py."
            )


class TestCopilotInstructionsCoverConventions:
    def test_covers_boundary_split_guard_rule(self):
        text = _copilot_text().lower()
        assert "boundary" in text and "elif" in text, (
            "Copilot instructions must restate the boundary-split guard rule: "
            "equality branches must test the exact boundary, never a loose elif."
        )

    def test_covers_tuned_constant_update_rule(self):
        text = _copilot_text().lower()
        assert "grep" in text and "cite" in text, (
            "Copilot instructions must restate the tuned-constant update rule: "
            "grep the whole repo in every value representation and cite "
            "constants by name."
        )

    def test_covers_doc_invariant_test_conventions(self):
        text = _copilot_text().lower()
        assert "doc-invariant" in text, (
            "Copilot instructions must restate the Doc-Invariant Test "
            "Conventions."
        )

    def test_covers_re_tune_no_promotion_flag(self):
        text = _copilot_text().lower()
        assert "re-tune" in text and "not be promoted" in text, (
            "Copilot instructions must restate that params whose semantics "
            "changed must not be promoted until re-tuned."
        )


class TestClaudeMdPointsAtCopilotInstructions:
    def test_claude_md_references_copilot_instructions_file(self):
        assert ".github/copilot-instructions.md" in _claude_text(), (
            "CLAUDE.md must note that .github/copilot-instructions.md exists "
            "and must be kept in sync when conventions change."
        )

    def test_claude_md_notes_keep_in_sync(self):
        text = _claude_text().lower()
        assert "keep" in text and "sync" in text, (
            "CLAUDE.md must explicitly say the Copilot instructions file "
            "needs to be kept in sync when conventions change."
        )
