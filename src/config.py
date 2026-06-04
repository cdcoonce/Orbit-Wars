PARAMS = {
    # Own planet classification
    "fortress_min_ships": 23,
    "fortress_min_production": 2,
    "factory_min_production": 4,
    "stationary_value_bonus": 4,
    # Threat level ratios
    "weak_ratio": 2.4300327426666266,
    "contested_ratio": 0.8924362720350362,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.44935688841208465,
    "frac_fortress_hard_neutral":    0.5066500574282683,
    "frac_fortress_soft_enemy":      0.8738325914206048,
    "frac_fortress_contested_enemy": 0.5280796959024844,
    "frac_fortress_hardened_enemy":  0.85,
    "frac_factory_easy_neutral":     0.32535978118571596,
    "frac_factory_soft_enemy":       0.6628658683197701,
    "frac_outpost_easy_neutral":     0.5590804691007405,
    "frac_outpost_soft_enemy":       0.6746444742586317,
    # Defense
    "threat_radius": 7.584744184323076,
    "threat_eta_window": 22,
    "defense_reinforce_fraction": 0.30468386610817616,
    "eta_buffer": 9,
    "min_garrison": 24,
    # Aggression scaling
    "aggression_max": 0.9679123297666566,
    "aggression_min": 0.46740595850913313,
    "game_length": 500,
    # Early-game expansion ramp
    "min_garrison_early": 3,
    "garrison_ramp_turns": 27,
    # Distance exponent ramp
    "distance_power_early": 4.234296711885922,
    "distance_power_late":  1.9459476610210327,
    "distance_ramp_turns":  80,
    # Comets
    "comet_value_multiplier": 1.7535352195923317,
    # Endgame
    "endgame_threshold_turn": 447,
    "endgame_lead_margin": 1.5683171297841578,
    # Lookahead
    "lookahead_turns": 2,
    "lookahead_blend": 0.9700116387768758,
    "lookahead_ship_weight": 0.08046935756296075,
}

SKIP_COMBOS = {
    ("FACTORY",  "HARD_NEUTRAL"),
    ("FACTORY",  "CONTESTED_ENEMY"),
    ("FACTORY",  "HARDENED_ENEMY"),
    ("OUTPOST",  "HARD_NEUTRAL"),
    ("OUTPOST",  "CONTESTED_ENEMY"),
    ("OUTPOST",  "HARDENED_ENEMY"),
}

PARAM_SPACE = {
    "fortress_min_ships":            (20,   60,    int),
    "fortress_min_production":       (2,    5,     int),
    "factory_min_production":        (2,    5,     int),
    "stationary_value_bonus":        (0,    8,     int),
    "weak_ratio":                    (1.1,  2.5,   float),
    "contested_ratio":               (0.8,  1.5,   float),
    "frac_fortress_easy_neutral":    (0.4,  0.9,   float),
    "frac_fortress_hard_neutral":    (0.5,  0.95,  float),
    "frac_fortress_soft_enemy":      (0.4,  0.9,   float),
    "frac_fortress_contested_enemy": (0.5,  0.95,  float),
    "frac_fortress_hardened_enemy":  (0.5,  0.95,  float),
    "frac_factory_easy_neutral":     (0.3,  0.8,   float),
    "frac_factory_soft_enemy":       (0.3,  0.8,   float),
    "frac_outpost_easy_neutral":     (0.2,  0.7,   float),
    "frac_outpost_soft_enemy":       (0.2,  0.7,   float),
    "threat_radius":                 (3.0,  8.0,   float),
    "threat_eta_window":             (10,   50,    int),
    "defense_reinforce_fraction":    (0.3,  0.7,   float),
    "eta_buffer":                    (2,    10,    int),
    "min_garrison":                  (5,    30,    int),
    "aggression_max":                (0.7,  1.0,   float),
    "aggression_min":                (0.3,  0.8,   float),
    "min_garrison_early":            (1,    15,    int),
    "garrison_ramp_turns":           (10,   100,   int),
    "distance_power_early":          (2.0,  5.0,   float),
    "distance_power_late":           (0.5,  3.0,   float),
    "distance_ramp_turns":           (10,   150,   int),
    "comet_value_multiplier":        (0.0,  3.0,   float),
    "endgame_threshold_turn":        (380,  490,   int),
    "endgame_lead_margin":           (1.05, 2.0,   float),
    "lookahead_turns":               (1,    5,     int),
    "lookahead_blend":               (0.0,  1.0,   float),
    "lookahead_ship_weight":         (0.001, 0.1,  float),
}
