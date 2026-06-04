from src.config import PARAMS, PARAM_SPACE, SKIP_COMBOS

# Class matrix mirrors the string literals returned by classify_own /
# classify_neutral / classify_enemy in src/strategy.py. plan_expansion looks up
# params[f"frac_{src}_{tgt}"] for every non-skipped combo, so each must exist.
SRC_CLASSES = ("FORTRESS", "FACTORY", "OUTPOST")
TGT_CLASSES = ("EASY_NEUTRAL", "HARD_NEUTRAL", "SOFT_ENEMY", "CONTESTED_ENEMY", "HARDENED_ENEMY")


def _expected_frac_keys():
    return {
        f"frac_{src.lower()}_{tgt.lower()}"
        for src in SRC_CLASSES
        for tgt in TGT_CLASSES
        if (src, tgt) not in SKIP_COMBOS
    }


def test_param_space_covers_all_tunable_params():
    assert set(PARAM_SPACE.keys()) == set(PARAMS.keys()) - {"game_length"}


def test_every_non_skipped_combo_has_frac_param():
    actual = {k for k in PARAMS if k.startswith("frac_")}
    missing = _expected_frac_keys() - actual
    assert not missing, f"non-skipped combos with no frac param: {sorted(missing)}"


def test_no_frac_param_for_skipped_or_unknown_combos():
    actual = {k for k in PARAMS if k.startswith("frac_")}
    orphans = actual - _expected_frac_keys()
    assert not orphans, f"frac params for skipped/unknown combos: {sorted(orphans)}"
