PARAMS = {
    # Own planet classification
    "fortress_min_ships": 21,
    "fortress_min_production": 2,
    "factory_min_production": 4,
    # Target value classification
    "high_value_production": 3,
    "medium_value_production": 2,
    "stationary_value_bonus": 2,
    # Threat level ratios
    "weak_ratio": 1.2511158548053918,
    "contested_ratio": 1.1595885324156752,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.6392386642660567,
    "frac_fortress_hard_neutral":    0.9031985601054257,
    "frac_fortress_soft_enemy":      0.6502705382394975,
    "frac_fortress_contested_enemy": 0.5427211066333779,
    "frac_factory_easy_neutral":     0.37382628566100107,
    "frac_factory_soft_enemy":       0.5321366660496892,
    "frac_outpost_easy_neutral":     0.4296790016441959,
    "frac_outpost_soft_enemy":       0.5009284338067023,
    # Defense
    "threat_radius": 7.539870578690189,
    "threat_eta_window": 18,
    "defense_reinforce_fraction": 0.5630024490285308,
    "eta_buffer": 9,
    "min_garrison": 27,
    # Aggression scaling
    "aggression_max": 0.9806186153678897,
    "aggression_min": 0.4734191579755174,
    "game_length": 500,
    # Early-game expansion ramp
    "min_garrison_early": 2,
    "garrison_ramp_turns": 71,
    # Comets
    "comet_value_multiplier": 0.5487415241565519,
    # Endgame
    "endgame_threshold_turn": 389,
    "endgame_lead_margin": 1.2999600959021158,
    # Lookahead
    "lookahead_turns": 2,
    "lookahead_blend": 0.6409693360903598,
    "lookahead_ship_weight": 0.06027730618268315,
}

SKIP_COMBOS = {
    ("FORTRESS", "HARDENED_ENEMY"),
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
    "high_value_production":         (3,    6,     int),
    "medium_value_production":       (1,    4,     int),
    "stationary_value_bonus":        (0,    3,     int),
    "weak_ratio":                    (1.1,  2.5,   float),
    "contested_ratio":               (0.8,  1.5,   float),
    "frac_fortress_easy_neutral":    (0.4,  0.9,   float),
    "frac_fortress_hard_neutral":    (0.5,  0.95,  float),
    "frac_fortress_soft_enemy":      (0.4,  0.9,   float),
    "frac_fortress_contested_enemy": (0.5,  0.95,  float),
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
    "comet_value_multiplier":        (0.0,  3.0,   float),
    "endgame_threshold_turn":        (380,  490,   int),
    "endgame_lead_margin":           (1.05, 2.0,   float),
    "lookahead_turns":               (1,    2,     int),
    "lookahead_blend":               (0.0,  1.0,   float),
    "lookahead_ship_weight":         (0.001, 0.1,  float),
}
