PARAMS = {
    # Own planet classification
    "fortress_min_ships": 27,
    "fortress_min_production": 2,
    "factory_min_production": 2,
    # Target value classification
    "high_value_production": 4,
    "medium_value_production": 4,
    "stationary_value_bonus": 1,
    # Threat level ratios
    "weak_ratio": 1.2435279747536865,
    "contested_ratio": 1.0180063681418952,
    # Send fractions (flattened from nested dict)
    "frac_fortress_easy_neutral":    0.5175876861067729,
    "frac_fortress_hard_neutral":    0.8831958136636119,
    "frac_fortress_soft_enemy":      0.4687468356841888,
    "frac_fortress_contested_enemy": 0.7083098805056031,
    "frac_factory_easy_neutral":     0.7122518842971215,
    "frac_factory_soft_enemy":       0.46279169242232376,
    "frac_outpost_easy_neutral":     0.44082297819801247,
    "frac_outpost_soft_enemy":       0.35091917236010356,
    # Defense
    "threat_radius": 4.75333641071924,
    "threat_eta_window": 31,
    "defense_reinforce_fraction": 0.5135159343309514,
    "eta_buffer": 2,
    "min_garrison": 29,
    # Aggression scaling
    "aggression_max": 0.9955814029680378,
    "aggression_min": 0.7438244636829526,
    "game_length": 500,
    # Early-game expansion ramp
    "min_garrison_early": 1,
    "garrison_ramp_turns": 24,
    # Distance exponent ramp
    "distance_power_early": 3.5,
    "distance_power_late":  2.0,
    "distance_ramp_turns":  50,
    # Comets
    "comet_value_multiplier": 0.0014806651778525755,
    # Endgame
    "endgame_threshold_turn": 409,
    "endgame_lead_margin": 1.9575513762822003,
    # Lookahead
    "lookahead_turns": 3,
    "lookahead_blend": 0.0807842932601907,
    "lookahead_ship_weight": 0.03345479834212885,
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
    "distance_power_early":          (2.0,  5.0,   float),
    "distance_power_late":           (1.0,  3.0,   float),
    "distance_ramp_turns":           (10,   150,   int),
    "comet_value_multiplier":        (0.0,  3.0,   float),
    "endgame_threshold_turn":        (380,  490,   int),
    "endgame_lead_margin":           (1.05, 2.0,   float),
    "lookahead_turns":               (1,    5,     int),
    "lookahead_blend":               (0.0,  1.0,   float),
    "lookahead_ship_weight":         (0.001, 0.1,  float),
}
