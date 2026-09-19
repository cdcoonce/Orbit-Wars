"""Gotchas.md's garrison-ramp gotcha must cite live PARAMS defaults (issue #219).

The "Garrison ramp direction" gotcha previously hardcoded `min_garrison_early`
(6) and `min_garrison` (28) as prose numbers. Both have since been promoted to
different values (13 and 26) by Optuna tuning, per CLAUDE.md's
`trials/champion.py` promotion flow, and the doc silently drifted. This test
pins the quoted figures to the live `src/config.py` PARAMS values so they
cannot silently rot again.
"""
from pathlib import Path

from src.config import PARAMS

REPO_ROOT = Path(__file__).parent.parent
GOTCHAS = REPO_ROOT / "docs" / "wiki" / "Gotchas.md"

MIN_GARRISON_EARLY = PARAMS["min_garrison_early"]
MIN_GARRISON = PARAMS["min_garrison"]


def test_garrison_ramp_direction_defaults_match_params():
    text = GOTCHAS.read_text()
    assert (
        f"(default {MIN_GARRISON_EARLY}, see `min_garrison_early` in `src/config.py`)"
        in text
    )
    assert (
        f"(default {MIN_GARRISON}, see `min_garrison` in `src/config.py`)" in text
    )
