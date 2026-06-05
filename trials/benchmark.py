"""Quick benchmark: champion vs original hand-tuned defaults."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PARAMS
from trials.game_runner import run_games
from trials.champion import CHAMPION_PARAMS

# Start from the full current defaults so every key strategy.py indexes with
# params[...] is present (new ramp params get added here automatically), then
# override only the hand-tuned originals this benchmark is meant to compare against.
ORIGINAL_DEFAULTS = {
    **PARAMS,
    'fortress_min_ships': 40, 'fortress_min_production': 3,
    'factory_min_production': 3,
    'stationary_value_bonus': 1,
    'weak_ratio': 1.5, 'contested_ratio': 1.1,
    'frac_fortress_easy_neutral': 0.60, 'frac_fortress_hard_neutral': 0.75,
    'frac_fortress_soft_enemy': 0.65, 'frac_fortress_contested_enemy': 0.75,
    'frac_factory_easy_neutral': 0.50, 'frac_factory_soft_enemy': 0.50,
    'frac_outpost_easy_neutral': 0.40, 'frac_outpost_soft_enemy': 0.40,
    'threat_radius': 5.0, 'threat_eta_window': 30,
    'defense_reinforce_fraction': 0.5, 'defense_incoming_multiplier': 0.0,
    'eta_buffer': 5, 'min_garrison': 15,
    'aggression_max': 1.0, 'aggression_min': 0.6, 'game_length': 500,
    'comet_value_multiplier': 1.0, 'endgame_threshold_turn': 450,
    'endgame_lead_margin': 1.2, 'lookahead_turns': 1,
    'lookahead_blend': 0.5, 'lookahead_ship_weight': 0.01,
}


if __name__ == "__main__":
    win_rate, results = run_games(CHAMPION_PARAMS, ORIGINAL_DEFAULTS, n_games=20)
    w = results.count('challenger')
    d = results.count('draw')
    l = results.count('champion')
    print(f"Champion vs original defaults: {win_rate:.0%}  ({w}W / {d}D / {l}L)")
