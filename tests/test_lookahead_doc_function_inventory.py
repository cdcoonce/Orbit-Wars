"""lookahead.md's overview said the module exports "three functions" and
listed only build_state/step_state/score_state, but src/lookahead.py also
publicly exports step_state_multi and score_candidate_lookahead — the latter
being the actual multi-turn rollout entry point plan_expansion calls. Pins
the wiki doc's function inventory to the real module exports, per issue
#372."""
from pathlib import Path

import src.lookahead as lookahead_module

REPO_ROOT = Path(__file__).parent.parent
WIKI_DOC = REPO_ROOT / "docs" / "wiki" / "src" / "lookahead.md"

PUBLIC_FUNCTIONS = [
    "build_state",
    "step_state",
    "step_state_multi",
    "score_state",
    "score_candidate_lookahead",
]


class TestFunctionInventory:
    def test_all_public_functions_exist_in_module(self):
        for name in PUBLIC_FUNCTIONS:
            assert callable(getattr(lookahead_module, name, None))

    def test_overview_does_not_undercount_functions(self):
        text = WIKI_DOC.read_text()
        assert "three functions" not in text

    def test_overview_names_every_public_function(self):
        text = WIKI_DOC.read_text()
        overview = text[: text.index("Cross-links:")]
        for name in PUBLIC_FUNCTIONS:
            assert f"`{name}`" in overview

    def test_step_state_multi_has_own_section(self):
        text = WIKI_DOC.read_text()
        assert "### `step_state_multi(" in text

    def test_score_candidate_lookahead_has_own_section(self):
        text = WIKI_DOC.read_text()
        assert "### `score_candidate_lookahead(" in text
