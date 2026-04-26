PARAMS = {
    # Own planet classification
    "fortress_min_ships": 34,
    "fortress_min_production": 2,
    "factory_min_production": 3,
    # Target value classification
    "high_value_production": 3,
    "medium_value_production": 4,
    "stationary_value_bonus": 2,
    # Threat level ratios
    "weak_ratio": 2.028630850140394,
    "contested_ratio": 1.4622854896730935,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.6850729390227452,
    "frac_fortress_hard_neutral":    0.635432463804873,
    "frac_fortress_soft_enemy":      0.7995777276875745,
    "frac_fortress_contested_enemy": 0.7765521943919609,
    "frac_factory_easy_neutral":     0.3979120121801534,
    "frac_factory_soft_enemy":       0.7588404343460309,
    "frac_outpost_easy_neutral":     0.4882309984822572,
    "frac_outpost_soft_enemy":       0.4781832242177646,
    # Defense
    "threat_radius": 3.193799342818691,
    "threat_eta_window": 23,
    "defense_reinforce_fraction": 0.34736962261667415,
    "eta_buffer": 2,
    "min_garrison": 30,
    # Aggression scaling
    "aggression_max": 0.9389541923645424,
    "aggression_min": 0.5089711211630356,
    "game_length": 500,
    # Early-game expansion ramp
    "min_garrison_early": 5,
    "garrison_ramp_turns": 50,
    # Comets
    "comet_value_multiplier": 1.0936708739730674,
    # Endgame
    "endgame_threshold_turn": 411,
    "endgame_lead_margin": 1.5693314177297815,
    # Lookahead
    "lookahead_turns": 2,
    "lookahead_blend": 0.5013346392962268,
    "lookahead_ship_weight": 0.004512981103330188,
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
