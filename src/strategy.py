import math
from collections import namedtuple

from kaggle_environments.envs.orbit_wars.orbit_wars import (
    Fleet,
    Planet,
)
from .math_utils import (
    BOARD_MAX,
    BOARD_MIN,
    _min_dist_pt_to_segment,
    angle_to_target,
    distance,
    fleet_speed,
    is_stationary,
    path_crosses_sun,
    predict_planet_position,
    turns_to_arrive,
)
from .config import PARAMS, SKIP_COMBOS
from .comets import effective_production
from .endgame import should_play_defensive
from .lookahead import build_state, score_candidate_lookahead

Threat = namedtuple("Threat", ["planet_id", "incoming_ships", "eta"])

# Safety cap for ETA fixed-point loops: the orbit/intercept system may not analytically
# converge, so we bound the iteration count rather than looping forever.
ETA_CONVERGENCE_ITERS = 10


def _turn_ramp(turn: int, ramp_turns: int, start: float, end: float) -> float:
    """Linearly interpolate from start to end over [0, ramp_turns], clamped at ramp_turns."""
    if ramp_turns <= 0:
        return end
    t = min(turn, ramp_turns) / ramp_turns
    return start + t * (end - start)


def aggression(turn: int, params: dict = PARAMS) -> float:
    return _turn_ramp(
        turn, params["game_length"], params["aggression_max"], params["aggression_min"]
    )


def classify_own(planet: Planet, threatened_ids: set, params: dict = PARAMS) -> str:
    if planet.id in threatened_ids:
        return "THREATENED"
    if (
        planet.ships >= params["fortress_min_ships"]
        and planet.production >= params["fortress_min_production"]
    ):
        return "FORTRESS"
    if planet.production >= params["factory_min_production"]:
        return "FACTORY"
    return "OUTPOST"


def classify_neutral(target: Planet, ships_to_send: int, params: dict = PARAMS) -> str:
    if target.ships == 0:
        return "EASY_NEUTRAL"
    ratio = ships_to_send / target.ships
    if ratio > params["weak_ratio"]:
        return "EASY_NEUTRAL"
    return "HARD_NEUTRAL"


def classify_enemy(
    target: Planet, ships_to_send: int, eta: int, params: dict = PARAMS
) -> str:
    expected_defenders = target.ships + target.production * eta
    if expected_defenders == 0:
        return "SOFT_ENEMY"
    ratio = ships_to_send / expected_defenders
    if ratio > params["weak_ratio"]:
        return "SOFT_ENEMY"
    if ratio > params["contested_ratio"]:
        return "CONTESTED_ENEMY"
    return "HARDENED_ENEMY"


def detect_threats(
    my_planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
    params: dict = PARAMS,
) -> list:
    # Aggregate every inbound fleet per planet: planet_id -> [summed_ships, earliest_eta].
    # Multiple enemy fleets converging on one planet collapse into a SINGLE threat so
    # handle_threats sizes reinforcement against the combined attack, not just one fleet.
    # Use id(fleet) (object identity) rather than fleet.id so that distinct fleet
    # objects sharing the same .id value (e.g. sim-spawned sentinels, which all
    # default to id=None) each contribute their ships exactly once.
    seen: set[tuple[int, int]] = set()
    # planet_id -> (summed_ships, earliest_eta). An explicit 2-tuple keeps each
    # slot self-documenting (no positional [0]/[1] mutation to accidentally swap).
    inbound_by_planet: dict[int, tuple[int, int]] = {}
    # (planet.id, t) -> (px, py). predict_planet_position depends only on
    # (planet, t), not on the enemy fleet, so precompute it once per planet/t
    # here rather than recomputing it for every enemy fleet in the loop below.
    # Skip the precompute entirely when no enemy fleets are present — the loop
    # below never consults planet_positions in that case.
    planet_positions: dict[tuple[int, int], tuple[float, float]] = {}
    if any(fleet.owner != player for fleet in fleets):
        planet_positions = {
            (planet.id, t): predict_planet_position(planet, angular_velocity, t - 1)
            for t in range(1, params["threat_eta_window"] + 1)
            for planet in my_planets
        }
    for fleet in fleets:
        if fleet.owner == player:
            continue
        speed = fleet_speed(fleet.ships)
        cos_a = math.cos(fleet.angle)
        sin_a = math.sin(fleet.angle)
        for t in range(1, params["threat_eta_window"] + 1):
            # Check the fleet's straight-line segment for interval [t-1, t] against
            # each planet's position at the start of that interval.  This catches
            # fleets whose closest approach falls between two integer samples.
            fx0 = fleet.x + (t - 1) * speed * cos_a
            fy0 = fleet.y + (t - 1) * speed * sin_a
            fx1 = fleet.x + t * speed * cos_a
            fy1 = fleet.y + t * speed * sin_a
            for planet in my_planets:
                # seen guards a single fleet object from contributing its ships
                # more than once to the same planet (it may stay in-radius across
                # several t). Keyed on object identity so fleets sharing
                # .id=None (lookahead sim-spawned sentinels) are not collapsed.
                if (id(fleet), planet.id) in seen:
                    continue
                px, py = planet_positions[(planet.id, t)]
                if _min_dist_pt_to_segment(px, py, fx0, fy0, fx1, fy1) < params["threat_radius"]:
                    seen.add((id(fleet), planet.id))
                    if planet.id in inbound_by_planet:
                        prev_ships, prev_eta = inbound_by_planet[planet.id]
                        # sum ships across fleets; keep the earliest sighting as ETA
                        inbound_by_planet[planet.id] = (
                            prev_ships + fleet.ships,
                            min(prev_eta, t),
                        )
                    else:
                        inbound_by_planet[planet.id] = (fleet.ships, t)
    return [
        Threat(planet_id=pid, incoming_ships=ships, eta=eta)
        for pid, (ships, eta) in inbound_by_planet.items()
    ]


def handle_threats(
    threats: list,
    owned: list[Planet],
    own_classes: dict,
    angular_velocity: float,
    params: dict = PARAMS,
) -> list[list]:
    moves = []
    already_used: set[int] = set()
    for threat in threats:
        target = next((p for p in owned if p.id == threat.planet_id), None)
        if target is None:
            continue
        for source in owned:
            if source.id == threat.planet_id or source.id in already_used:
                continue
            if own_classes.get(source.id) not in ("FORTRESS", "FACTORY"):
                # classify_own returns "THREATENED" (not "FORTRESS") when a fleet is inbound,
                # so THREATENED planets are naturally excluded here
                continue
            # Flat fraction (legacy behavior) vs. magnitude-aware reinforcement that
            # scales with the size of the incoming attack. At multiplier == 0.0,
            # magnitude collapses to 0 and ships_to_send == flat — byte-for-byte
            # identical to the pre-feature behavior.
            flat = int(source.ships * params["defense_reinforce_fraction"])
            magnitude = int(
                threat.incoming_ships * params["defense_incoming_multiplier"]
            )
            # Cap magnitude-driven growth so the source keeps min_garrison, but never
            # below the flat baseline (preserves the legacy floor when the knob is 0).
            # max(flat, min(max(flat, magnitude), cap)) collapses to max(flat, min(magnitude, cap)):
            # when magnitude >= flat both forms agree; when magnitude < flat both reduce to flat.
            cap = source.ships - params["min_garrison"]
            ships_to_send = max(flat, min(magnitude, cap))
            if ships_to_send < params["min_garrison"]:
                continue
            future_x, future_y, eta = intercept(
                source, target, angular_velocity, ships_to_send
            )
            if eta <= threat.eta - params["eta_buffer"]:
                if path_crosses_sun(source.x, source.y, future_x, future_y):
                    continue
                angle = angle_to_target(source.x, source.y, future_x, future_y)
                moves.append([source.id, angle, ships_to_send])
                already_used.add(source.id)
                break
    return moves


def _effective_min_garrison(turn: int, params: dict) -> int:
    """Linearly ramp min_garrison from min_garrison_early up to min_garrison."""
    early = params["min_garrison_early"]
    full = params["min_garrison"]
    ramp = params["garrison_ramp_turns"]
    return int(_turn_ramp(turn, ramp, early, full))


def _effective_distance_power(turn: int, params: dict) -> float:
    """Linearly ramp distance exponent from distance_power_early down to distance_power_late."""
    return _turn_ramp(
        turn,
        params["distance_ramp_turns"],
        params["distance_power_early"],
        params["distance_power_late"],
    )


def _blended_best(candidates: list, blend: float):
    """Select the winning (target, fraction, future_x, future_y) from scored expansion candidates.

    ``candidates`` is a list of ``(greedy_score, lookahead_score, target, fraction, future_x, future_y)``.
    A single candidate or ``blend == 0.0`` takes the greedy fast-path (highest
    greedy score wins). Otherwise greedy and lookahead scores are each min-max
    normalized to ``[0, 1]`` — the ``+1e-9`` guards against a zero range when all
    candidates share a score — and combined as ``(1 - blend) * ng + blend * nl``.
    Returns ``(target, fraction, future_x, future_y)`` so the caller can reuse
    the already-computed intercept geometry without a redundant ``intercept()`` call.
    """
    if len(candidates) == 1 or blend == 0.0:
        best = max(candidates, key=lambda c: c[0])
        return best[2], best[3], best[4], best[5]

    lo_g = min(c[0] for c in candidates)
    hi_g = max(c[0] for c in candidates)
    lo_l = min(c[1] for c in candidates)
    hi_l = max(c[1] for c in candidates)
    scored = []
    for greedy, look, tgt, frac, fx, fy in candidates:
        ng = (greedy - lo_g) / (hi_g - lo_g + 1e-9)
        nl = (look - lo_l) / (hi_l - lo_l + 1e-9)
        final = (1 - blend) * ng + blend * nl
        scored.append((final, tgt, frac, fx, fy))
    best_scored = max(scored, key=lambda x: x[0])
    return best_scored[1], best_scored[2], best_scored[3], best_scored[4]


def _build_opponent_fn(
    initial_planets, fleets, turn, player, angular_velocity, params, use_lookahead
):
    """Return a frozen opponent_fn (state -> precomputed moves) for lookahead, or None
    when use_lookahead is False. Forces blend=0 in the opponent plan to terminate recursion.

    Precompute the opponent's frozen response ONCE per plan_expansion call. Every
    input (initial_planets, fleets, turn, player, angular_velocity, params) is
    loop-invariant, so the result is identical for every source planet — hoisted
    out of the `for source in owned:` loop in plan_expansion to avoid recomputing a
    full opponent plan_moves per owned planet every turn (the lookahead path runs
    with lookahead_blend≈0.97 in real games and across self-play). Forces blend=0 to
    prevent recursive lookahead (recursion termination).
    """
    if not use_lookahead:
        return None

    opp_player = 1 - player
    greedy_params_opp = {**params, "lookahead_blend": 0.0}
    opp_base = build_state(initial_planets, fleets, turn)
    opp_moves = plan_moves(
        opp_base.planets,
        opp_base.fleets,
        opp_player,
        angular_velocity,
        turn=turn,
        params=greedy_params_opp,
        initial_planets=initial_planets,
    )
    return lambda state, m=opp_moves: m  # noqa: E731


def _generate_candidates(
    source: Planet,
    src_class: str,
    targets: list[Planet],
    dist_power: float,
    agg: float,
    angular_velocity: float,
    params: dict,
    comet_ids: set,
    comet_velocities: dict | None,
    opponent_fn,
    initial_planets,
    fleets,
    player: int,
    turn: int,
    use_lookahead: bool,
) -> list:
    """Return scored expansion candidates for one source planet.

    Each candidate is a ``(greedy_score, lookahead_score, target, fraction,
    future_x, future_y)`` tuple, scored via classification, intercept,
    ``can_capture``, sun-path checks, greedy scoring, and optional lookahead
    scoring against ``opponent_fn``.
    """
    # Use full fleet for classification so FACTORY correctly sees adjacent
    # enemies as SOFT rather than CONTESTED (half-fleet underestimates ratio).
    probe_ships = source.ships

    candidates = []  # list of (greedy_score, lookahead_score, target, fraction, future_x, future_y)

    for target in targets:
        if target.owner == -1:
            tgt_class = classify_neutral(target, probe_ships, params)
        else:
            probe_result = intercept(
                source,
                target,
                angular_velocity,
                probe_ships,
                comet_ids,
                comet_velocities,
            )
            if probe_result[0] is None:
                continue
            _, _, probe_eta = probe_result
            tgt_class = classify_enemy(target, probe_ships, probe_eta, params)

        if (src_class, tgt_class) in SKIP_COMBOS:
            continue
        # Deliberately optional: SKIP_COMBOS (src/config.py) means some
        # (src_class, tgt_class) pairs have no frac_* key in PARAMS at all,
        # so .get() + the None-check below is the documented control flow.
        fraction = params.get(f"frac_{src_class.lower()}_{tgt_class.lower()}")
        if fraction is None:
            continue

        ships_to_send = max(1, int(source.ships * fraction * agg))
        intercept_result = intercept(
            source,
            target,
            angular_velocity,
            ships_to_send,
            comet_ids,
            comet_velocities,
        )
        if intercept_result[0] is None:
            continue
        future_x, future_y, eta = intercept_result
        if not can_capture(ships_to_send, target, eta):
            continue
        if path_crosses_sun(source.x, source.y, future_x, future_y):
            continue

        bonus = params["stationary_value_bonus"] if is_stationary(target) else 0
        eff_prod = effective_production(
            target, comet_ids, params["comet_value_multiplier"]
        )
        greedy_score = (eff_prod + bonus) / (eta + 1) ** dist_power

        # Lookahead score — simulate the candidate forward and score it.
        # opponent_fn is constructed once per plan_expansion call and passed
        # in, reused across every source planet and candidate target.
        if use_lookahead:
            candidate_move = [
                source.id,
                angle_to_target(source.x, source.y, future_x, future_y),
                ships_to_send,
            ]
            # plan_moves injected so lookahead.py stays free of a strategy import.
            lookahead_score = score_candidate_lookahead(
                initial_planets,
                fleets,
                turn,
                candidate_move,
                player,
                angular_velocity,
                opponent_fn,
                params,
                plan_moves,
            )
        else:
            lookahead_score = greedy_score  # fallback keeps blend=0 equivalent

        candidates.append((greedy_score, lookahead_score, target, fraction, future_x, future_y))

    return candidates


def _try_send(
    source: Planet,
    target: Planet,
    ships: int,
    angular_velocity: float,
    comet_ids: set = frozenset(),
    comet_velocities: dict | None = None,
    *,
    validate: bool = False,
    aim: tuple[float, float] | None = None,
) -> list | None:
    """Build a ``[source.id, angle, ships]`` move, or ``None`` if un-sendable.

    Runs ``intercept`` to find the aim point and returns ``None`` when it can't
    find one. When ``validate=True``, also rejects when ``can_capture`` fails or
    the path crosses the sun.

    ``aim`` supplies an ``(future_x, future_y)`` already computed by the caller,
    skipping the intercept entirely — the primary launch reuses the winning
    candidate's geometry from the scoring loop rather than recomputing it.
    Incompatible with ``validate=True``, which needs the ``eta`` only
    ``intercept`` returns; that combination is a programming error.
    """
    if aim is not None:
        if validate:
            raise ValueError("aim= cannot be combined with validate=True (needs eta)")
        future_x, future_y = aim
    else:
        future_x, future_y, eta = intercept(
            source, target, angular_velocity, ships, comet_ids, comet_velocities
        )
        if future_x is None:
            return None
        if validate:
            if not can_capture(ships, target, eta):
                return None
            if path_crosses_sun(source.x, source.y, future_x, future_y):
                return None
    return [source.id, angle_to_target(source.x, source.y, future_x, future_y), ships]


def _drain_excess(
    source: Planet,
    candidates: list,
    best_target_id: int,
    ships_remaining: int,
    min_garrison: int,
    agg: float,
    angular_velocity: float,
    comet_ids: set = frozenset(),
    comet_velocities: dict | None = None,
) -> list:
    """Drain leftover ships from ``source`` into lower-scored candidates.

    Ranks by raw greedy c[0], not blended: lookahead is expensive and
    leftover-fleet stakes are low. Clamps each send so ``ships_remaining``
    never drops below ``min_garrison``.
    """
    moves = []
    already_sent = {best_target_id}
    for _, _, extra_target, extra_fraction, _, _ in sorted(
        candidates, key=lambda c: c[0], reverse=True
    ):
        if ships_remaining <= min_garrison:
            break
        if extra_target.id in already_sent:
            continue
        extra_send = max(1, int(ships_remaining * extra_fraction * agg))
        # Don't drop below min_garrison. The loop guard above ensures
        # ships_remaining > min_garrison here, so the clamped value is >= 1.
        if ships_remaining - extra_send < min_garrison:
            extra_send = ships_remaining - min_garrison
        extra_move = _try_send(
            source,
            extra_target,
            extra_send,
            angular_velocity,
            comet_ids,
            comet_velocities,
            validate=True,
        )
        if extra_move is None:
            continue
        moves.append(extra_move)
        ships_remaining -= extra_send
        already_sent.add(extra_target.id)

    return moves


def plan_expansion(
    owned: list[Planet],
    neutrals: list[Planet],
    enemies: list[Planet],
    own_classes: dict,
    angular_velocity: float,
    agg: float = 1.0,
    params: dict = PARAMS,
    comet_ids: set = frozenset(),
    initial_planets=None,
    fleets=None,
    player: int = 0,
    turn: int = 0,
    comet_velocities: dict | None = None,
) -> list[list]:
    moves = []
    targets = neutrals + enemies
    min_garrison = int(_effective_min_garrison(turn, params) / agg)
    dist_power = _effective_distance_power(turn, params)
    blend = params["lookahead_blend"]
    use_lookahead = blend > 0 and initial_planets is not None and fleets is not None
    opponent_fn = _build_opponent_fn(
        initial_planets, fleets, turn, player, angular_velocity, params, use_lookahead
    )

    for source in owned:
        src_class = own_classes.get(source.id, "OUTPOST")
        if src_class == "THREATENED":
            continue
        if source.ships < min_garrison:
            continue

        candidates = _generate_candidates(
            source,
            src_class,
            targets,
            dist_power,
            agg,
            angular_velocity,
            params,
            comet_ids,
            comet_velocities,
            opponent_fn,
            initial_planets,
            fleets,
            player,
            turn,
            use_lookahead,
        )

        if not candidates:
            continue

        best_target, best_fraction, best_fx, best_fy = _blended_best(candidates, blend)

        # Primary fleet — the candidate was fully validated during scoring, and
        # first_send equals the ships_to_send that produced (best_fx, best_fy),
        # so the geometry is reused via aim= and no intercept is repeated here.
        ships_remaining = source.ships
        first_send = max(1, int(ships_remaining * best_fraction * agg))
        move = _try_send(
            source,
            best_target,
            first_send,
            angular_velocity,
            comet_ids,
            comet_velocities,
            aim=(best_fx, best_fy),
        )
        if move is None:
            continue
        moves.append(move)
        ships_remaining -= first_send

        # Multi-target: drain excess ships to lower-scored candidates
        if ships_remaining > min_garrison:
            moves.extend(
                _drain_excess(
                    source,
                    candidates,
                    best_target.id,
                    ships_remaining,
                    min_garrison,
                    agg,
                    angular_velocity,
                    comet_ids,
                    comet_velocities,
                )
            )

    return moves


def plan_moves(
    planets: list[Planet],
    fleets: list[Fleet],
    player: int,
    angular_velocity: float,
    turn: int = 0,
    params: dict = PARAMS,
    comet_ids: set = frozenset(),
    initial_planets=None,
    comet_velocities: dict | None = None,
) -> list[list]:
    owned = my_planets(planets, player)
    neutrals = neutral_planets(planets)
    enemies = enemy_planets(planets, player)

    if not owned:
        return []

    agg = aggression(turn, params)
    threats = detect_threats(owned, fleets, player, angular_velocity, params)
    threatened_ids = {t.planet_id for t in threats}
    own_classes = {p.id: classify_own(p, threatened_ids, params) for p in owned}

    defense_moves = handle_threats(
        threats, owned, own_classes, angular_velocity, params
    )

    if should_play_defensive(
        planets,
        fleets,
        player,
        turn,
        params["endgame_threshold_turn"],
        params["endgame_lead_margin"],
    ):
        return defense_moves

    defense_used = {m[0] for m in defense_moves}

    expansion_owned = [p for p in owned if p.id not in defense_used]
    expansion_classes = {k: v for k, v in own_classes.items() if k not in defense_used}
    expansion_moves = plan_expansion(
        expansion_owned,
        neutrals,
        enemies,
        expansion_classes,
        angular_velocity,
        agg,
        params,
        comet_ids,
        initial_planets=initial_planets,
        fleets=fleets,
        player=player,
        turn=turn,
        comet_velocities=comet_velocities,
    )

    return defense_moves + expansion_moves


def my_planets(planets: list[Planet], player: int) -> list[Planet]:
    return [p for p in planets if p.owner == player]


def neutral_planets(planets: list[Planet]) -> list[Planet]:
    return [p for p in planets if p.owner == -1]


def enemy_planets(planets: list[Planet], player: int) -> list[Planet]:
    return [p for p in planets if p.owner not in (-1, player)]


def _intercept_comet_linear(
    sx: float,
    sy: float,
    tx: float,
    ty: float,
    vx: float,
    vy: float,
    ships: int,
) -> tuple[float, float, int] | None:
    """Iterative linear intercept for a comet moving at constant velocity.

    Returns (fx, fy, eta) when a safe on-board intercept converges, or None
    when the predicted aim point or the fleet's actual endpoint (accounting
    for overshoot) would leave the board.
    """
    speed = fleet_speed(ships)
    eta = turns_to_arrive(sx, sy, tx, ty, ships)
    fx, fy = tx, ty
    for _ in range(ETA_CONVERGENCE_ITERS):
        fx = tx + vx * eta
        fy = ty + vy * eta
        if not (BOARD_MIN <= fx <= BOARD_MAX and BOARD_MIN <= fy <= BOARD_MAX):
            return None  # comet off-board at predicted intercept time
        new_eta = turns_to_arrive(sx, sy, fx, fy, ships)
        if new_eta == eta:
            break
        eta = new_eta

    # Check fleet endpoint for overshoot: fleet travels eta*speed units in a
    # straight line; if that overshoots past the aim point toward the board
    # edge the fleet exits the board.
    d = distance(fx, fy, sx, sy)
    if d > 1e-9:
        scale = (eta * speed) / d
        ex = sx + scale * (fx - sx)
        ey = sy + scale * (fy - sy)
        if not (BOARD_MIN <= ex <= BOARD_MAX and BOARD_MIN <= ey <= BOARD_MAX):
            return None

    return fx, fy, eta


def intercept(
    source: Planet,
    target: Planet,
    angular_velocity: float,
    ships_to_send: int,
    comet_ids: set = frozenset(),
    comet_velocities: dict | None = None,
) -> tuple[float, float, int] | tuple[None, None, None]:
    """Return (future_x, future_y, eta) predicting the target's future position.

    Returns (None, None, None) for comet targets that cannot be safely
    intercepted — caller must skip those targets.

    For comets uses linear velocity extrapolation; for regular orbiting planets
    iterates until ETA converges.
    """
    if target.id in comet_ids:
        vel = (comet_velocities or {}).get(target.id)
        if not vel:
            # No velocity data yet (first sighting) — cannot aim accurately
            return None, None, None
        result = _intercept_comet_linear(
            source.x, source.y, target.x, target.y, vel[0], vel[1], ships_to_send
        )
        if result is None:
            return None, None, None
        return result

    # Regular orbiting planet: iterate until ETA converges
    eta = turns_to_arrive(source.x, source.y, target.x, target.y, ships_to_send)
    future_x, future_y = target.x, target.y
    for _ in range(ETA_CONVERGENCE_ITERS):
        future_x, future_y = predict_planet_position(target, angular_velocity, eta)
        new_eta = turns_to_arrive(source.x, source.y, future_x, future_y, ships_to_send)
        if new_eta == eta:
            break
        eta = new_eta
    return future_x, future_y, eta


def can_capture(ships_to_send: int, target: Planet, eta: int) -> bool:
    """True if our fleet will outnumber the target on arrival.
    Neutral planets don't produce ships (only owned planets do per game engine),
    so only add production*eta for enemy planets."""
    if target.owner == -1:
        expected_defenders = target.ships
    else:
        expected_defenders = target.ships + target.production * eta
    return ships_to_send > expected_defenders
