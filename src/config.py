PARAMS = {
    # Own planet classification
    "fortress_min_ships": 40,
    "fortress_min_production": 2,
    "factory_min_production": 3,
    # Target value classification
    "high_value_production": 4,
    "medium_value_production": 4,
    "stationary_value_bonus": 3,
    # Threat level ratios
    "weak_ratio": 1.8126598010948267,
    "contested_ratio": 1.4484642618814887,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.5940859190315988,
    "frac_fortress_hard_neutral":    0.687757882838061,
    "frac_fortress_soft_enemy":      0.6665338623176082,
    "frac_fortress_contested_enemy": 0.6212637037970997,
    "frac_factory_easy_neutral":     0.7941043976957939,
    "frac_factory_soft_enemy":       0.7700868214182174,
    "frac_outpost_easy_neutral":     0.45259996166904615,
    "frac_outpost_soft_enemy":       0.44381082550866613,
    # Defense
    "threat_radius": 6.731173964290402,
    "threat_eta_window": 29,
    "defense_reinforce_fraction": 0.3424281854153906,
    "eta_buffer": 2,
    "min_garrison": 29,
    # Aggression scaling
    "aggression_max": 0.8751757441200135,
    "aggression_min": 0.5290787202881425,
    "game_length": 500,
    # Comets
    "comet_value_multiplier": 2.7777108675926794,
    # Endgame
    "endgame_threshold_turn": 419,
    "endgame_lead_margin": 1.8394480028338263,
    # Lookahead
    "lookahead_turns": 1,
    "lookahead_blend": 0.9952268120447567,
    "lookahead_ship_weight": 0.007887206276555422,
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
    "comet_value_multiplier":        (0.0,  3.0,   float),
    "endgame_threshold_turn":        (380,  490,   int),
    "endgame_lead_margin":           (1.05, 2.0,   float),
    "lookahead_turns":               (1,    2,     int),
    "lookahead_blend":               (0.0,  1.0,   float),
    "lookahead_ship_weight":         (0.001, 0.1,  float),
}
