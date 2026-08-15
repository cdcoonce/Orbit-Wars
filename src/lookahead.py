"""Lightweight 1–2 turn simulator for lookahead scoring."""

import math
from dataclasses import dataclass

from .math_utils import distance, fleet_speed, predict_planet_position, sum_owned


@dataclass
class SimPlanet:
    id: int
    owner: int
    x: float
    y: float
    radius: float
    ships: int
    production: int


@dataclass
class SimFleet:
    owner: int
    x: float
    y: float
    angle: float
    ships: int
    # sentinel for sim-spawned fleets; real fleets get kaggle id. None (not -1)
    # so this can never be mistaken for the owner==-1 neutral-owner convention.
    id: int | None = None


@dataclass
class GameState:
    planets: list  # list[SimPlanet]
    fleets: list  # list[SimFleet]
    turn: int


def build_state(planets, fleets, turn: int) -> GameState:
    """Convert immutable kaggle namedtuples to mutable SimPlanet/SimFleet objects."""
    sim_planets = [
        SimPlanet(
            id=p.id,
            owner=p.owner,
            x=p.x,
            y=p.y,
            radius=p.radius,
            ships=p.ships,
            production=p.production,
        )
        for p in planets
    ]
    sim_fleets = [
        SimFleet(
            owner=f.owner,
            x=f.x,
            y=f.y,
            angle=f.angle,
            ships=f.ships,
            id=f.id,
        )
        for f in fleets
    ]
    return GameState(planets=sim_planets, fleets=sim_fleets, turn=turn)


def _resolve_combat(planet: SimPlanet, arrivals: list) -> None:
    """Resolve combat on a single planet when one or more fleets arrive.

    Mutates planet.owner and planet.ships in place. Assumes arrivals is non-empty
    (the caller is responsible for skipping planets with no arrivals).

    Four branches:
    1. New owner wins with surviving > 0 ships (minus 1 foothold cost).
    2. Defender holds with surviving > 0 ships.
    3. Exact tie (surviving == 0) won by the incumbent — planet held, 0 ships.
    4. Incumbent loses to combined attackers (surviving < 0) — planet goes neutral.
    """
    # Group by owner; include planet's own garrison as a defender.
    # Neutral planets (owner=-1) defend with their ships under key -1.
    owner_ships: dict[int, int] = {}
    owner_ships[planet.owner] = planet.ships
    for f in arrivals:
        owner_ships[f.owner] = owner_ships.get(f.owner, 0) + f.ships

    # Find the winner (largest total); ties go to current owner.
    winner = max(
        owner_ships, key=lambda o: (owner_ships[o], 1 if o == planet.owner else 0)
    )
    winner_ships = owner_ships[winner]
    total_others = sum(v for o, v in owner_ships.items() if o != winner)
    surviving = winner_ships - total_others

    if surviving > 0 and winner != planet.owner:
        planet.owner = winner
        # -1 ship cost models the "foothold" overhead of taking a new planet.
        # The real engine doesn't have this cost; it's a deliberate pessimism
        # bias in the 1-turn lookahead to avoid over-valuing conquest moves.
        planet.ships = surviving - 1
    elif surviving > 0:
        planet.ships = surviving
    elif surviving == 0 and winner == planet.owner:
        # EXACT tie won by the incumbent owner (ties break to current owner).
        # The defender holds the planet with no ships to spare, rather than
        # collapsing to neutral — keeps the lookahead from undervaluing holds.
        # For a neutral planet (owner=-1) this preserves neutral-stays-neutral.
        # Guarded on ``surviving == 0``: when the incumbent is only the
        # largest SINGLE stack but loses to the COMBINED attackers
        # (surviving < 0), it must NOT retain the planet — that falls through
        # to the neutral branch below.
        planet.ships = 0
    else:
        # No surviving victor — an exact tie not won by the incumbent, or the
        # incumbent was the largest single stack but lost to the combined
        # attackers (surviving < 0). The planet goes neutral with 0 ships.
        planet.owner = -1
        planet.ships = 0


def _launch_fleet(
    state: GameState, planet_id: int, angle: float, ships: int, owner: int
) -> None:
    """Launch a fleet from ``planet_id`` toward ``angle``, or silently skip.

    Deducts ``ships`` from the source planet and appends a SimFleet spawned
    just outside its radius (the ``+ 0.1`` offset keeps the fleet from
    landing back on its own source planet next combat pass). No-op if the
    source planet doesn't exist or doesn't have enough ships.
    """
    source = next((p for p in state.planets if p.id == planet_id), None)
    if source is not None and source.ships >= ships:
        source.ships -= ships
        state.fleets.append(
            SimFleet(
                owner=owner,
                x=source.x + math.cos(angle) * (source.radius + 0.1),
                y=source.y + math.sin(angle) * (source.radius + 0.1),
                angle=angle,
                ships=ships,
            )
        )


def step_state(
    state: GameState,
    move,
    player: int,
    angular_velocity: float,
    opponent_fn=None,
) -> GameState:
    """Simulate ONE turn forward.

    Args:
        state: Current game state (will be mutated in place; caller should not
               reuse it after calling step_state).
        move: [planet_id, angle, ships] or None.
        player: The acting player's index.
        angular_velocity: Global orbital angular velocity (rad/turn).
        opponent_fn: Optional callable (state) -> list[list]. If provided,
                     opponent moves are applied after our fleet launch and before
                     fleet movement.

    Returns:
        The mutated GameState after one simulated turn.
    """
    moves = [] if move is None else [move]
    return step_state_multi(state, moves, player, angular_velocity, opponent_fn)


def step_state_multi(
    state: GameState,
    moves,
    player: int,
    angular_velocity: float,
    opponent_fn=None,
) -> GameState:
    """Simulate ONE turn forward with a list of own-player moves.

    Identical to step_state except the launch phase iterates *moves* (a list of
    [planet_id, angle, ships]) rather than a single optional move.  An empty
    list applies no own launches.  Steps 1b, 2, 3, 4, and 5 are byte-for-byte
    equivalent to step_state.

    Args:
        state: Current game state (mutated in place; caller should not reuse).
        moves: List of [planet_id, angle, ships] launch instructions. An empty
               list produces no own launches. Moves whose source has insufficient
               ships are silently skipped.
        player: The acting player's index.
        angular_velocity: Global orbital angular velocity (rad/turn).
        opponent_fn: Optional callable (state) -> list[list]. Invoked exactly
                     once; opponent moves are applied after own launches.

    Returns:
        The mutated GameState after one simulated turn.
    """
    # --- Step 1: Launch one fleet per move (skips moves with insufficient ships) ---
    # Matches the engine's step order (orbit_wars.py interpreter): Fleet Launch
    # happens before Production and Planet Movement & Sweep, so the launch angle
    # is applied from each source planet's PRE-rotation position — exactly the
    # coordinates plan_expansion used to compute the angle in the first place.
    for move in moves:
        planet_id, angle, ships_to_send = move[0], move[1], move[2]
        _launch_fleet(state, planet_id, angle, ships_to_send, owner=player)

    # --- Step 1b: Opponent fleet launches ---
    if opponent_fn is not None:
        opp_moves = opponent_fn(state)
        for opp_move in opp_moves:
            planet_id, angle, ships = opp_move[0], opp_move[1], opp_move[2]
            _launch_fleet(state, planet_id, angle, ships, owner=1 - player)

    # --- Step 2: Production ---
    for planet in state.planets:
        if planet.owner != -1:
            planet.ships += planet.production

    # --- Step 3: Rotate orbiting planets ---
    for sim_planet in state.planets:
        new_x, new_y = predict_planet_position(sim_planet, angular_velocity, 1)
        sim_planet.x = new_x
        sim_planet.y = new_y

    # --- Step 4: Move all fleets ---
    for fleet in state.fleets:
        speed = fleet_speed(fleet.ships)
        fleet.x += speed * math.cos(fleet.angle)
        fleet.y += speed * math.sin(fleet.angle)

    # --- Step 5: Combat ---
    # Single pass: assign each fleet to the first planet it lands on, or keep flying.
    remaining_fleets = []
    planet_arrivals: dict[int, list] = {p.id: [] for p in state.planets}
    for fleet in state.fleets:
        landed = False
        for planet in state.planets:
            dist = distance(fleet.x, fleet.y, planet.x, planet.y)
            if dist <= planet.radius:
                planet_arrivals[planet.id].append(fleet)
                landed = True
                break
        if not landed:
            remaining_fleets.append(fleet)

    for planet in state.planets:
        arrivals = planet_arrivals[planet.id]
        if not arrivals:
            continue
        _resolve_combat(planet, arrivals)

    # Keep only fleets that didn't land on any planet
    state.fleets = remaining_fleets

    state.turn += 1
    return state


def score_state(state: GameState, player: int, ship_weight: float = 0.01) -> float:
    """Score a GameState from `player`'s perspective.

    The operative weight in real play is `lookahead_ship_weight` in PARAMS
    (`src/config.py`), passed explicitly by `score_candidate_lookahead`. The
    `ship_weight=0.01` signature default is only a fallback for direct or
    unit-test calls that omit the argument — no production caller relies on it.
    """
    my_prod = sum_owned(state.planets, player, attr="production")
    enemy_prod = sum_owned(state.planets, player, attr="production", enemy=True)
    # Includes in-transit fleet ships (not just planet-held ships), matching
    # src/endgame.py's total_ships — a fleet launched by step_state and still
    # flying at the lookahead horizon no longer vanishes from the score. This
    # changes the measurement lookahead_blend/lookahead_ship_weight/lookahead_turns
    # (src/config.py) were tuned against; not for promotion until re-tuned via #117.
    my_ships = sum_owned(state.planets, player) + sum_owned(state.fleets, player)
    enemy_ships = sum_owned(state.planets, player, enemy=True) + sum_owned(
        state.fleets, player, enemy=True
    )
    return (my_prod - enemy_prod) + ship_weight * (my_ships - enemy_ships)


def score_candidate_lookahead(
    initial_planets,
    fleets,
    turn: int,
    candidate_move,
    player: int,
    angular_velocity: float,
    opponent_fn,
    params,
    plan_moves_fn,
) -> float:
    """Score a candidate move by simulating it forward and scoring the result.

    Builds a state from the current board, applies our `candidate_move` plus the
    opponent's response (T+1), then rolls forward `lookahead_turns - 1` more turns
    with both sides applying their full planned move lists, and returns `score_state`
    from `player`'s view. `plan_moves_fn` is INJECTED rather than imported so this
    module never depends on strategy.py — the greedy roll-forward calls back into the
    real planner without creating a circular import. Behaviour-preserving extraction
    of the block formerly inline in strategy.plan_expansion.
    """
    # T+1: apply our candidate move + opponent response.
    state = build_state(initial_planets, fleets, turn)
    state = step_state(state, candidate_move, player, angular_velocity, opponent_fn)
    # T+2..N: both players apply their full planned move lists (lookahead disabled).
    n_extra = params.get("lookahead_turns", 1) - 1
    # Loop-invariant: greedy_params depends only on params, never on the evolving
    # state — build it once, mirroring the hoist in commit e9750e6 (#49).
    greedy_params = {**params, "lookahead_blend": 0.0}
    for _ in range(n_extra):
        our_greedy = plan_moves_fn(
            state.planets,
            state.fleets,
            player,
            angular_velocity,
            turn=state.turn,
            params=greedy_params,
            initial_planets=initial_planets,
        )
        # Fresh opponent response from the evolved state (not the frozen initial state).
        opp_greedy = plan_moves_fn(
            state.planets,
            state.fleets,
            1 - player,
            angular_velocity,
            turn=state.turn,
            params=greedy_params,
            initial_planets=initial_planets,
        )
        fresh_opp_fn = lambda s, m=opp_greedy: m  # noqa: E731
        state = step_state_multi(state, our_greedy, player, angular_velocity, fresh_opp_fn)
    return score_state(state, player, params.get("lookahead_ship_weight", 0.01))
