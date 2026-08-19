"""Drift guard for docs/wiki/generate_config.py vs the committed config.md.

Issue #164: no test covered generate_config.py, which is exactly how IMPACT/
GROUPS drifted out of sync with src/config.py undetected (a live param went
missing, stale entries lingered). These tests pin validate_keys(), the
PARAMS/GROUPS/IMPACT key-set invariants, and the generated table content
against the committed doc so a `src/config.py` change without a regenerated
`docs/wiki/src/config.md` fails CI.
"""

import importlib.util
from pathlib import Path

import pytest

from src.config import PARAMS

REPO_ROOT = Path(__file__).parent.parent
GENERATE_CONFIG_SCRIPT = REPO_ROOT / "docs" / "wiki" / "generate_config.py"
CONFIG_MD = REPO_ROOT / "docs" / "wiki" / "src" / "config.md"


def _load_generate_config():
    spec = importlib.util.spec_from_file_location(
        "_generate_config_under_test", GENERATE_CONFIG_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _committed_generated_section() -> str:
    text = CONFIG_MD.read_text(encoding="utf-8")
    start_marker = "<!-- AUTO-GENERATED-START -->"
    end_marker = "<!-- AUTO-GENERATED-END -->"
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    assert start_idx != -1 and end_idx != -1, (
        f"AUTO-GENERATED-START/END markers missing from {CONFIG_MD}"
    )
    return text[start_idx + len(start_marker) : end_idx].strip("\n")


def test_validate_keys_does_not_raise():
    """validate_keys() must pass — catches a missing/stale key the moment
    src/config.py changes without generate_config.py being updated to match."""
    mod = _load_generate_config()
    mod.validate_keys()  # raises ValueError on any drift


def test_validate_keys_raises_when_param_missing_from_groups():
    """A PARAMS key with no GROUPS entry must make validate_keys() raise —
    catches the case where build_table would silently omit it from the doc."""
    mod = _load_generate_config()
    target_key = sorted(set(PARAMS.keys()) - mod.FIXED_KEYS)[0]
    for _, keys in mod.GROUPS:
        if target_key in keys:
            keys.remove(target_key)
            break
    with pytest.raises(ValueError, match="missing from GROUPS"):
        mod.validate_keys()


def test_every_params_key_covered_by_exactly_one_group_and_has_impact():
    """Every non-fixed PARAMS key must appear in exactly one GROUPS entry and
    have an IMPACT description; no GROUPS/IMPACT key may be absent from PARAMS."""
    mod = _load_generate_config()

    params_keys = set(PARAMS.keys()) - mod.FIXED_KEYS

    group_membership = {}
    for group_name, keys in mod.GROUPS:
        for key in keys:
            group_membership.setdefault(key, []).append(group_name)

    for key in params_keys:
        memberships = group_membership.get(key, [])
        assert len(memberships) == 1, (
            f"PARAMS key {key!r} must appear in exactly one GROUPS entry, "
            f"found in {memberships}"
        )
        assert key in mod.IMPACT, f"PARAMS key {key!r} is missing an IMPACT description"

    groups_keys = set(group_membership.keys())
    stale_groups = groups_keys - set(PARAMS.keys())
    assert not stale_groups, f"GROUPS key(s) absent from PARAMS (stale): {sorted(stale_groups)}"

    stale_impact = set(mod.IMPACT.keys()) - set(PARAMS.keys())
    assert not stale_impact, f"IMPACT key(s) absent from PARAMS (stale): {sorted(stale_impact)}"


def test_impact_game_length_derived_from_params(monkeypatch):
    """IMPACT['game_length'] must be built from PARAMS['game_length'], not a
    hardcoded literal — changing PARAMS must change the generated text."""
    import src.config as config_module

    monkeypatch.setitem(config_module.PARAMS, "game_length", 999)
    mod = _load_generate_config()
    assert "999" in mod.IMPACT["game_length"]
    assert "500" not in mod.IMPACT["game_length"]


def test_generated_section_matches_committed_doc():
    """build_generated_section() output must equal the committed AUTO-GENERATED
    block in config.md — an un-regenerated doc fails CI."""
    mod = _load_generate_config()
    generated = mod.build_generated_section().strip("\n")
    committed = _committed_generated_section()
    assert generated == committed, (
        "docs/wiki/src/config.md is out of sync with generate_config.py output. "
        "Run `uv run python docs/wiki/generate_config.py` and commit the result."
    )
