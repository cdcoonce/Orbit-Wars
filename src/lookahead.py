"""Lightweight 1–2 turn simulator for lookahead scoring."""
import math
from dataclasses import dataclass

from .math_utils import fleet_speed, predict_planet_position


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
    id: int = -1  # sentinel for sim-spawned fleets; real fleets get kaggle id


@dataclass
class GameState:
    planets: list  # list[SimPlanet]
    fleets: list   # list[SimFleet]
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


def step_state(
    state: GameState,
    move,
    player: int,
    angular_velocity: float,
    initial_planets,
    opponent_fn=None,
) -> GameState:
    """Simulate ONE turn forward.

    Args:
        state: Current game state (will be mutated in place; caller should not
               reuse it after calling step_state).
        move: [planet_id, angle, ships] or None.
        player: The acting player's index.
        angular_velocity: Global orbital angular velocity (rad/turn).
        initial_planets: Planet list at the start of the lookahead window —
                         used to track orbital angles.
        opponent_fn: Optional callable (state) -> list[list]. If provided,
                     opponent moves are applied after our fleet launch and before
                     fleet movement.

    Returns:
        The mutated GameState after one simulated turn.
    """
    # --- Step 1: Production ---
    for planet in state.planets:
        if planet.owner != -1:
            planet.ships += planet.production

    # --- Step 2: Rotate orbiting planets ---
    for sim_planet in state.planets:
        new_x, new_y = predict_planet_position(sim_planet, angular_velocity, 1)
        sim_planet.x = new_x
        sim_planet.y = new_y

    # --- Step 3: Launch fleet from move ---
    if move is not None:
        planet_id, angle, ships_to_send = move[0], move[1], move[2]
        source = next((p for p in state.planets if p.id == planet_id), None)
        if source is not None and source.ships >= ships_to_send:
            source.ships -= ships_to_send
            new_fleet = SimFleet(
                owner=player,
                x=source.x,
                y=source.y,
                angle=angle,
                ships=ships_to_send,
            )
            state.fleets.append(new_fleet)

    # --- Step 3b: Opponent fleet launches ---
    if opponent_fn is not None:
        opp_moves = opponent_fn(state)
        for opp_move in opp_moves:
            planet_id, angle, ships = opp_move[0], opp_move[1], opp_move[2]
            opp_source = next((p for p in state.planets if p.id == planet_id), None)
            if opp_source is not None and opp_source.ships >= ships:
                opp_source.ships -= ships
                state.fleets.append(SimFleet(
                    owner=1 - player,
                    x=opp_source.x,
                    y=opp_source.y,
                    angle=angle,
                    ships=ships,
                ))

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
            dist = math.sqrt((fleet.x - planet.x) ** 2 + (fleet.y - planet.y) ** 2)
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

        # Group by owner; include planet's own garrison as a defender.
        # Neutral planets (owner=-1) defend with their ships under key -1.
        owner_ships: dict[int, int] = {}
        owner_ships[planet.owner] = planet.ships  # always include planet garrison
        for f in arrivals:
            owner_ships[f.owner] = owner_ships.get(f.owner, 0) + f.ships

        # Find the winner (largest total); ties go to current owner
        winner = max(owner_ships, key=lambda o: (owner_ships[o], 1 if o == planet.owner else 0))
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
        else:
            # Tie — planet stays neutral with 0 ships
            planet.owner = -1
            planet.ships = 0

    # Keep only fleets that didn't land on any planet
    state.fleets = remaining_fleets

    state.turn += 1
    return state


def score_state(state: GameState, player: int, ship_weight: float = 0.01) -> float:
    """Score a GameState from `player`'s perspective."""
    my_prod = sum(p.production for p in state.planets if p.owner == player)
    enemy_prod = sum(
        p.production for p in state.planets if p.owner not in (-1, player)
    )
    my_ships = sum(p.ships for p in state.planets if p.owner == player)
    enemy_ships = sum(
        p.ships for p in state.planets if p.owner not in (-1, player)
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
    with both sides playing greedily, and returns `score_state` from `player`'s
    view. `plan_moves_fn` is INJECTED rather than imported so this module never
    depends on strategy.py — the greedy roll-forward calls back into the real
    planner without creating a circular import. Behaviour-preserving extraction
    of the block formerly inline in strategy.plan_expansion.
    """
    # T+1: apply our candidate move + opponent response.
    state = build_state(initial_planets, fleets, turn)
    state = step_state(
        state, candidate_move, player, angular_velocity, initial_planets, opponent_fn
    )
    # T+2..N: both players play greedily (lookahead disabled) from the evolved state.
    n_extra = params.get("lookahead_turns", 1) - 1
    for _ in range(n_extra):
        greedy_params = {**params, "lookahead_blend": 0.0}
        our_greedy = plan_moves_fn(
            state.planets, state.fleets, player, angular_velocity,
            turn=state.turn, params=greedy_params,
            initial_planets=initial_planets,
        )
        our_move = our_greedy[0] if our_greedy else None  # one move per sim step (approximation)
        # Fresh opponent response from the evolved state (not the frozen initial state).
        opp_greedy = plan_moves_fn(
            state.planets, state.fleets, 1 - player, angular_velocity,
            turn=state.turn, params=greedy_params,
            initial_planets=initial_planets,
        )
        fresh_opp_fn = lambda s, m=opp_greedy: m  # noqa: E731
        state = step_state(
            state, our_move, player, angular_velocity, initial_planets, fresh_opp_fn
        )
    return score_state(state, player, params.get("lookahead_ship_weight", 0.01))
