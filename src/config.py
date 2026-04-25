PARAMS = {
    # Own planet classification
    "fortress_min_ships": 40,
    "fortress_min_production": 3,
    "factory_min_production": 3,
    # Target value classification
    "high_value_production": 4,
    "medium_value_production": 2,
    "stationary_value_bonus": 1,
    # Threat level ratios
    "weak_ratio": 1.5,
    "contested_ratio": 1.1,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.60,
    "frac_fortress_hard_neutral":    0.75,
    "frac_fortress_soft_enemy":      0.65,
    "frac_fortress_contested_enemy": 0.75,
    "frac_factory_easy_neutral":     0.50,
    "frac_factory_soft_enemy":       0.50,
    "frac_outpost_easy_neutral":     0.40,
    "frac_outpost_soft_enemy":       0.40,
    # Defense
    "threat_radius": 5.0,
    "threat_eta_window": 30,
    "defense_reinforce_fraction": 0.5,
    "eta_buffer": 5,
    "min_garrison": 15,
    # Aggression scaling
    "aggression_max": 1.0,
    "aggression_min": 0.6,
    "game_length": 500,
    # Comets (added in Phase 2 — include now so PARAM_SPACE is complete)
    "comet_value_multiplier": 1.0,
    # Endgame (added in Phase 3)
    "endgame_threshold_turn": 450,
    "endgame_lead_margin": 1.2,
    # Lookahead (added in Phase 4)
    "lookahead_turns": 1,
    "lookahead_blend": 0.5,
    "lookahead_ship_weight": 0.01,
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
