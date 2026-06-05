"""Frozen baseline strategy config — the self-play regression sparring partner.

A snapshot of src.config.PARAMS at the time the no-regression benchmark was
established. The benchmark (tests/test_strategy_benchmark.py) pits the CURRENT
strategy against this frozen config over fixed-seed self-play; a change that
regresses play drops the win-rate below the floor and fails the gate.

Update this ONLY by deliberate human act when a strategy improvement is accepted
(copy the new src.config.PARAMS here in the same commit that ships it).
"""

BASELINE_PARAMS = {'fortress_min_ships': 23,
 'fortress_min_production': 2,
 'factory_min_production': 4,
 'stationary_value_bonus': 4,
 'weak_ratio': 2.4300327426666266,
 'contested_ratio': 0.8924362720350362,
 'frac_fortress_easy_neutral': 0.44935688841208465,
 'frac_fortress_hard_neutral': 0.5066500574282683,
 'frac_fortress_soft_enemy': 0.8738325914206048,
 'frac_fortress_contested_enemy': 0.5280796959024844,
 'frac_fortress_hardened_enemy': 0.85,
 'frac_factory_easy_neutral': 0.32535978118571596,
 'frac_factory_soft_enemy': 0.6628658683197701,
 'frac_outpost_easy_neutral': 0.5590804691007405,
 'frac_outpost_soft_enemy': 0.6746444742586317,
 'threat_radius': 7.584744184323076,
 'threat_eta_window': 22,
 'defense_reinforce_fraction': 0.30468386610817616,
 'eta_buffer': 9,
 'min_garrison': 24,
 'aggression_max': 0.9679123297666566,
 'aggression_min': 0.46740595850913313,
 'game_length': 500,
 'min_garrison_early': 3,
 'garrison_ramp_turns': 27,
 'distance_power_early': 4.234296711885922,
 'distance_power_late': 1.9459476610210327,
 'distance_ramp_turns': 80,
 'comet_value_multiplier': 1.7535352195923317,
 'endgame_threshold_turn': 447,
 'endgame_lead_margin': 1.5683171297841578,
 'lookahead_turns': 2,
 'lookahead_blend': 0.9700116387768758,
 'lookahead_ship_weight': 0.08046935756296075}
