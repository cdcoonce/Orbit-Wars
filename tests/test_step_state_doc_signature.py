"""step_state dropped its initial_planets parameter (the opponent function is
pre-frozen by the caller instead), but docs/wiki/src/lookahead.md still
documented it. Pins the wiki doc's step_state section to the real signature
in src/lookahead.py, per issue #354."""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
WIKI_DOC = REPO_ROOT / "docs" / "wiki" / "src" / "lookahead.md"


def _step_state_section(text):
    start = text.index("### `step_state(")
    end = text.index("### `score_state(")
    return text[start:end]


class TestStepStateSignatureDoc:
    def test_wiki_does_not_reference_initial_planets(self):
        section = _step_state_section(WIKI_DOC.read_text())
        assert "initial_planets" not in section

    def test_wiki_heading_matches_real_signature(self):
        text = WIKI_DOC.read_text()
        assert (
            "### `step_state(state, move, player, angular_velocity, opponent_fn=None) -> GameState`"
            in text
        )

    def test_wiki_code_block_matches_real_signature(self):
        text = WIKI_DOC.read_text()
        assert (
            "def step_state(\n"
            "    state: GameState,\n"
            "    move,\n"
            "    player: int,\n"
            "    angular_velocity: float,\n"
            "    opponent_fn=None,\n"
            ") -> GameState:"
        ) in text
