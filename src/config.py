PARAMS = {
    # Own planet classification
    "fortress_min_ships": 20,
    "fortress_min_production": 2,
    "factory_min_production": 2,
    # Target value classification
    "high_value_production": 4,
    "medium_value_production": 4,
    "stationary_value_bonus": 2,
    # Threat level ratios
    "weak_ratio": 1.154617395420197,
    "contested_ratio": 0.8407577228938329,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.8396621295827016,
    "frac_fortress_hard_neutral":    0.7390354888675388,
    "frac_fortress_soft_enemy":      0.8207825684121107,
    "frac_fortress_contested_enemy": 0.5988259338469294,
    "frac_factory_easy_neutral":     0.7077611944778195,
    "frac_factory_soft_enemy":       0.6780334958733476,
    "frac_outpost_easy_neutral":     0.53362289042428,
    "frac_outpost_soft_enemy":       0.5376892175236,
    # Defense
    "threat_radius": 5.265740056967727,
    "threat_eta_window": 17,
    "defense_reinforce_fraction": 0.6022826916905341,
    "eta_buffer": 10,
    "min_garrison": 28,
    # Aggression scaling
    "aggression_max": 0.9179119423124437,
    "aggression_min": 0.7369096209665795,
    "game_length": 500,
    # Early-game expansion ramp
    "min_garrison_early": 6,
    "garrison_ramp_turns": 35,
    # Comets
    "comet_value_multiplier": 2.2247498240243333,
    # Endgame
    "endgame_threshold_turn": 451,
    "endgame_lead_margin": 1.4126548981094489,
    # Lookahead
    "lookahead_turns": 2,
    "lookahead_blend": 0.4836506797909815,
    "lookahead_ship_weight": 0.08724646016341354,
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
    "lookahead_turns":               (1,    5,     int),
    "lookahead_blend":               (0.0,  1.0,   float),
    "lookahead_ship_weight":         (0.001, 0.1,  float),
}
