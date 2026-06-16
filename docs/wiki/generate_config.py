"""Generate the parameter reference table in docs/wiki/src/config.md.

Run with:
    uv run python docs/wiki/generate_config.py

Reads PARAMS and PARAM_SPACE from src/config.py, validates that their key
sets match (excluding intentionally-fixed keys), then rewrites the section
between <!-- AUTO-GENERATED-START --> and <!-- AUTO-GENERATED-END --> markers
in docs/wiki/src/config.md.
"""

import sys
from pathlib import Path

# Resolve repo root relative to this script's location
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import PARAM_SPACE, PARAMS  # noqa: E402

CONFIG_MD = REPO_ROOT / "docs" / "wiki" / "src" / "config.md"

# Keys intentionally absent from PARAM_SPACE (fixed constants, not tunable).
FIXED_KEYS = {"game_length"}

# ---------------------------------------------------------------------------
# Behavioral impact descriptions (hardcoded — cannot be derived from config.py)
# ---------------------------------------------------------------------------
IMPACT: dict[str, str] = {
    "fortress_min_ships": "Raise → fewer FORTRESS planets, more ships available for attack",
    "fortress_min_production": "Raise → fewer FORTRESS planets",
    "factory_min_production": "Raise → fewer FACTORY planets, more OUTPOST",
    "stationary_value_bonus": "Raise → more attractive to attack stationary planets",
    "weak_ratio": "Raise → fewer EASY_NEUTRAL / SOFT_ENEMY targets (more conservative)",
    "contested_ratio": "Raise → fewer CONTESTED targets (more conservative)",
    "frac_fortress_easy_neutral": "Raise → send more ships from FORTRESS to EASY_NEUTRAL",
    "frac_fortress_hard_neutral": "Raise → send more ships from FORTRESS to HARD_NEUTRAL",
    "frac_fortress_soft_enemy": "Raise → send more ships from FORTRESS to SOFT_ENEMY",
    "frac_fortress_contested_enemy": "Raise → send more ships from FORTRESS to CONTESTED_ENEMY",
    "frac_factory_easy_neutral": "Raise → send more ships from FACTORY to EASY_NEUTRAL",
    "frac_factory_soft_enemy": "Raise → send more ships from FACTORY to SOFT_ENEMY",
    "frac_fortress_hardened_enemy": "Raise → send more ships from FORTRESS to HARDENED_ENEMY",
    "frac_outpost_easy_neutral": "Raise → send more ships from OUTPOST to EASY_NEUTRAL",
    "frac_outpost_soft_enemy": "Raise → send more ships from OUTPOST to SOFT_ENEMY",
    "threat_radius": "Raise → detect threats from farther away",
    "threat_eta_window": "Raise → react earlier to incoming fleets",
    "defense_reinforce_fraction": "Raise → send more reinforcements when threatened",
    "defense_incoming_multiplier": "Raise → treats incoming fleets as more threatening (multiplies combined incoming ship count against defense threshold)",
    "eta_buffer": "Raise → more conservative ETA margin for defense",
    "min_garrison": "Raise → keep more ships at home before attacking",
    "aggression_max": "Raise → more ships sent earlier in game",
    "aggression_min": "Raise → more ships sent later in game",
    "game_length": "Fixed: 500 — reflects Kaggle competition rule, not tunable",
    "min_garrison_early": "Raise → more conservative in early game",
    "garrison_ramp_turns": "Raise → take longer to reach full garrison threshold",
    "distance_power_early": "Raise → penalise distant targets more in early game",
    "distance_power_late": "Raise → penalise distant targets more in late game",
    "distance_ramp_turns": "Raise → take longer to ramp from early to late distance exponent",
    "comet_value_multiplier": "Raise → treat comets as more attractive targets",
    "endgame_threshold_turn": "Raise → switch to defensive mode later",
    "endgame_lead_margin": "Raise → require larger lead before going defensive",
    "lookahead_turns": "Raise → simulate further ahead (slower)",
    "lookahead_blend": "Raise → trust simulator more vs greedy heuristic",
    "lookahead_ship_weight": "Raise → value ship counts more vs production in scoring",
}

# ---------------------------------------------------------------------------
# Param groupings — ordered list of (header, [param_keys])
# ---------------------------------------------------------------------------
GROUPS: list[tuple[str, list[str]]] = [
    (
        "Planet Classification",
        ["fortress_min_ships", "fortress_min_production", "factory_min_production", "stationary_value_bonus"],
    ),
    (
        "Target Classification",
        ["weak_ratio", "contested_ratio"],
    ),
    (
        "Send Fractions",
        [
            "frac_fortress_easy_neutral",
            "frac_fortress_hard_neutral",
            "frac_fortress_soft_enemy",
            "frac_fortress_contested_enemy",
            "frac_fortress_hardened_enemy",
            "frac_factory_easy_neutral",
            "frac_factory_soft_enemy",
            "frac_outpost_easy_neutral",
            "frac_outpost_soft_enemy",
        ],
    ),
    (
        "Defense",
        [
            "threat_radius",
            "threat_eta_window",
            "defense_reinforce_fraction",
            "defense_incoming_multiplier",
            "eta_buffer",
            "min_garrison",
        ],
    ),
    (
        "Aggression",
        ["aggression_max", "aggression_min", "game_length"],
    ),
    (
        "Garrison Ramp",
        ["min_garrison_early", "garrison_ramp_turns"],
    ),
    (
        "Distance Power",
        ["distance_power_early", "distance_power_late", "distance_ramp_turns"],
    ),
    (
        "Comets",
        ["comet_value_multiplier"],
    ),
    (
        "Endgame",
        ["endgame_threshold_turn", "endgame_lead_margin"],
    ),
    (
        "Lookahead",
        ["lookahead_turns", "lookahead_blend", "lookahead_ship_weight"],
    ),
]


def validate_keys() -> None:
    """Raise ValueError if PARAMS and PARAM_SPACE key sets diverge unexpectedly."""
    params_keys = set(PARAMS.keys())
    space_keys = set(PARAM_SPACE.keys())

    # Keys in PARAMS but not PARAM_SPACE (should only be FIXED_KEYS)
    params_only = params_keys - space_keys - FIXED_KEYS
    if params_only:
        raise ValueError(
            f"Keys in PARAMS but not in PARAM_SPACE (and not fixed): {sorted(params_only)}\n"
            "Add them to PARAM_SPACE or to the FIXED_KEYS set in generate_config.py."
        )

    # Keys in PARAM_SPACE but not PARAMS
    space_only = space_keys - params_keys
    if space_only:
        raise ValueError(
            f"Keys in PARAM_SPACE but not in PARAMS: {sorted(space_only)}\n"
            "Add them to PARAMS or remove from PARAM_SPACE."
        )

    # Keys in PARAMS not covered by any GROUPS entry (would be silently omitted)
    groups_keys = {k for _, keys in GROUPS for k in keys}
    missing_from_groups = (params_keys - FIXED_KEYS) - groups_keys
    if missing_from_groups:
        raise ValueError(
            f"Keys in PARAMS missing from GROUPS (would be silently omitted): "
            f"{sorted(missing_from_groups)}\n"
            "Add them to the appropriate group in generate_config.py."
        )

    # Reverse: keys in GROUPS or IMPACT that no longer exist in PARAMS (stale entries)
    stale_groups = groups_keys - params_keys
    if stale_groups:
        raise ValueError(
            f"Keys in GROUPS absent from PARAMS (stale): {sorted(stale_groups)}\n"
            "Remove them from GROUPS in generate_config.py."
        )
    impact_keys = set(IMPACT.keys())
    stale_impact = impact_keys - params_keys - FIXED_KEYS
    if stale_impact:
        raise ValueError(
            f"Keys in IMPACT absent from PARAMS (stale): {sorted(stale_impact)}\n"
            "Remove them from IMPACT in generate_config.py."
        )


def format_value(v) -> str:
    """Format a param value for the table."""
    if isinstance(v, float):
        # Show up to 6 significant digits without trailing zeros
        return f"{v:.6g}"
    return str(v)


def format_range(key: str) -> str:
    """Format the Optuna range for a param, or 'fixed' if absent."""
    if key not in PARAM_SPACE:
        return "fixed"
    lo, hi, typ = PARAM_SPACE[key]
    type_label = "int" if typ is int else "float"
    return f"{format_value(lo)} – {format_value(hi)} ({type_label})"


def build_table(keys: list[str]) -> str:
    """Build a markdown table for a list of param keys."""
    header = "| Param | Default | Optuna range | Behavioral impact |"
    separator = "|---|---|---|---|"
    rows = [header, separator]
    for key in keys:
        default = format_value(PARAMS[key])
        optuna_range = format_range(key)
        impact = IMPACT.get(key)
        if impact is None:
            raise ValueError(
                f"Key '{key}' has no entry in IMPACT. "
                "Add a description to the IMPACT dict in generate_config.py."
            )
        rows.append(f"| `{key}` | `{default}` | {optuna_range} | {impact} |")
    return "\n".join(rows)


def build_generated_section() -> str:
    """Build the full auto-generated markdown content."""
    parts = []
    for group_name, keys in GROUPS:
        parts.append(f"### {group_name}\n")
        parts.append(build_table(keys))
        parts.append("")  # blank line between groups
    return "\n".join(parts)


def update_config_md(generated: str) -> None:
    """Replace content between AUTO-GENERATED-START and AUTO-GENERATED-END markers."""
    text = CONFIG_MD.read_text(encoding="utf-8")

    start_marker = "<!-- AUTO-GENERATED-START -->"
    end_marker = "<!-- AUTO-GENERATED-END -->"

    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        raise RuntimeError(
            f"Could not find AUTO-GENERATED-START/END markers in {CONFIG_MD}.\n"
            "Ensure both markers are present in config.md."
        )
    if end_idx <= start_idx:
        raise RuntimeError(
            f"AUTO-GENERATED-END marker appears before AUTO-GENERATED-START in {CONFIG_MD}.\n"
            "Check config.md for swapped or duplicated markers."
        )

    before = text[: start_idx + len(start_marker)]
    after = text[end_idx:]

    new_text = before + "\n" + generated + "\n" + after
    CONFIG_MD.write_text(new_text, encoding="utf-8")


def main() -> None:
    validate_keys()
    generated = build_generated_section()
    update_config_md(generated)
    print("config.md updated")


if __name__ == "__main__":
    main()
