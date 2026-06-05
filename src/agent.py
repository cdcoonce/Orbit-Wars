from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .comets import get_comet_ids
from .strategy import plan_moves

_initial_planets = None
_prev_comet_positions: dict[int, tuple[float, float]] = {}


def plan_turn(obs, initial_planets, prev_comet_positions, params=None):
    """Shared per-turn wrapper: parse obs, track comet velocities, plan moves.

    Both the deployed agent (``agent`` below) and the self-play tuning agent
    (``trials.game_runner.make_agent``) call this so tuning and deployment
    exercise the *same* comet-aware targeting code. A comet's velocity is
    estimated from its one-turn position delta between sightings and handed to
    ``plan_moves`` as ``comet_velocities`` so the linear-intercept path is
    actually attempted.

    State is threaded explicitly rather than stored here, so each caller keeps
    its own: the deployed agent uses module globals while each trial closure
    uses its own locals (parallel games mustn't share state). Returns
    ``(moves, new_initial_planets, new_prev_comet_positions)``.
    """
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)
    angular_velocity = obs.get("angular_velocity", 0.0)
    turn = obs.get("step", 0)
    comet_ids = get_comet_ids(obs)

    if turn == 0 or initial_planets is None:
        initial_planets = planets
        prev_comet_positions = {}

    # Build comet velocity estimates from position deltas (one turn apart)
    comet_velocities: dict[int, tuple[float, float]] = {}
    current_comet_positions: dict[int, tuple[float, float]] = {}
    for p in planets:
        if p.id in comet_ids:
            current_comet_positions[p.id] = (p.x, p.y)
            if p.id in prev_comet_positions:
                px, py = prev_comet_positions[p.id]
                comet_velocities[p.id] = (p.x - px, p.y - py)

    kwargs = dict(
        comet_ids=comet_ids,
        comet_velocities=comet_velocities,
        initial_planets=initial_planets,
    )
    if params is not None:
        kwargs["params"] = params

    moves = plan_moves(planets, fleets, player, angular_velocity, turn, **kwargs)
    return moves, initial_planets, current_comet_positions


def agent(obs: dict) -> list[list]:
    global _initial_planets, _prev_comet_positions
    moves, _initial_planets, _prev_comet_positions = plan_turn(
        obs, _initial_planets, _prev_comet_positions,
    )
    return moves
