"""Guards on trials.champion.CHAMPION_PARAMS against drift from src.config.

trials/run_trials.py:write_champion auto-generates trials/champion.py, and the
tuning workflow (see CLAUDE.md) hand-copies those values into src/config.py
PARAMS. A champion promoted under since-tightened PARAM_SPACE bounds, or
carrying a key later renamed/removed from PARAMS, would ship silently —
nothing else validates the champion artifact itself against the current
PARAMS/PARAM_SPACE definitions.
"""

from src.config import PARAMS, PARAM_SPACE
from trials.champion import CHAMPION_PARAMS

_RETUNE_HINT = (
    "Re-tune: rm trials/study.db, then uv run python trials/run_trials.py, "
    "copy the winning params into src/config.py PARAMS, then python build.py."
)


def test_no_stale_keys():
    stale = set(CHAMPION_PARAMS) - set(PARAMS)
    assert not stale, f"CHAMPION_PARAMS has keys no longer in PARAMS: {sorted(stale)}. {_RETUNE_HINT}"


def test_champion_params_within_param_space_bounds():
    # Only PARAM_SPACE keys have tunable bounds — keys in PARAMS but not
    # PARAM_SPACE (e.g. "game_length") are fixed constants, not Optuna-tunable
    # (mirrors the FIXED_KEYS set in docs/wiki/generate_config.py), so they
    # have no bounds to check here.
    out_of_bounds = [
        key
        for key, (low, high, _) in PARAM_SPACE.items()
        if key in CHAMPION_PARAMS and not (low <= CHAMPION_PARAMS[key] <= high)
    ]
    assert not out_of_bounds, (
        f"CHAMPION_PARAMS values outside PARAM_SPACE bounds: {out_of_bounds}. {_RETUNE_HINT}"
    )


def test_champion_params_type_matches_param_space():
    # Same FIXED_KEYS exclusion as above — game_length has no declared
    # PARAM_SPACE type to check against.
    type_mismatches = [
        key
        for key, (_, _, typ) in PARAM_SPACE.items()
        if key in CHAMPION_PARAMS and not isinstance(CHAMPION_PARAMS[key], typ)
    ]
    assert not type_mismatches, (
        "CHAMPION_PARAMS values with wrong type for declared PARAM_SPACE type: "
        f"{type_mismatches}. {_RETUNE_HINT}"
    )
