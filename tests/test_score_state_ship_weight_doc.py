"""score_state's signature default (0.01) is never used in real play — the
operative weight is `lookahead_ship_weight` in `src/config.py` PARAMS
(~0.0724). These tests pin the docstring and wiki doc to say so, per issue
#181, instead of presenting 0.01 as "the" default."""
from pathlib import Path

from src.lookahead import score_state

REPO_ROOT = Path(__file__).parent.parent
WIKI_DOC = REPO_ROOT / "docs" / "wiki" / "src" / "lookahead.md"


class TestScoreStateDocstring:
    def test_docstring_names_lookahead_ship_weight(self):
        doc = score_state.__doc__ or ""
        assert "lookahead_ship_weight" in doc

    def test_docstring_explains_0_01_is_a_fallback(self):
        doc = score_state.__doc__ or ""
        assert "0.01" in doc


class TestWikiDocReconciled:
    def test_wiki_does_not_present_0_01_as_the_default(self):
        text = WIKI_DOC.read_text()
        assert "ship_weight` (`lookahead_ship_weight` in PARAMS, default 0.01)" not in text

    def test_wiki_cites_lookahead_ship_weight_as_operative(self):
        text = WIKI_DOC.read_text()
        assert "lookahead_ship_weight" in text
