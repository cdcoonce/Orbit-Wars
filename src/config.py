PARAMS = {
    # Own planet classification
    "fortress_min_ships": 31,
    "fortress_min_production": 2,
    "factory_min_production": 5,
    "stationary_value_bonus": 0,
    # Threat level ratios
    "weak_ratio": 1.9947103092400609,
    "contested_ratio": 1.3116870693167089,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.6373798481888991,
    "frac_fortress_hard_neutral":    0.8280958418348433,
    "frac_fortress_soft_enemy":      0.7693872378844533,
    "frac_fortress_contested_enemy": 0.8513568427887089,
    "frac_fortress_hardened_enemy":  0.6205349006008141,
    "frac_factory_easy_neutral":     0.7918877418991281,
    "frac_factory_soft_enemy":       0.5716368569289937,
    "frac_outpost_easy_neutral":     0.6091691624282816,
    "frac_outpost_soft_enemy":       0.5040091397305635,
    # Defense
    "threat_radius": 7.361366948460609,
    "threat_eta_window": 15,
    "defense_reinforce_fraction": 0.3476899630999006,
    "defense_incoming_multiplier": 0.6176537815824305,
    "eta_buffer": 8,
    "min_garrison": 26,
    # Aggression scaling
    "aggression_max": 0.9797831434048456,
    "aggression_min": 0.4881980293792295,
    "game_length": 500,
    # Early-game expansion ramp
    "min_garrison_early": 13,
    "garrison_ramp_turns": 32,
    # Distance exponent ramp
    "distance_power_early": 3.482732599302752,
    "distance_power_late":  0.5051929832754551,
    "distance_ramp_turns":  25,
    # Comets
    "comet_value_multiplier": 0.7187932590356509,
    # Endgame
    "endgame_threshold_turn": 445,
    "endgame_lead_margin": 1.6098319822666625,
    # Lookahead
    "lookahead_turns": 5,
    "lookahead_blend": 0.9032151725931578,
    "lookahead_ship_weight": 0.07240125896738046,
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
    "defense_incoming_multiplier":   (0.0,  2.0,   float),
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
