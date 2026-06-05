from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .comets import get_comet_ids
from .strategy import plan_moves

_initial_planets = None
_prev_comet_positions: dict[int, tuple[float, float]] = {}


def agent(obs: dict) -> list[list]:
    global _initial_planets, _prev_comet_positions
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)
    angular_velocity = obs.get("angular_velocity", 0.0)
    turn = obs.get("step", 0)
    comet_ids = get_comet_ids(obs)

    if turn == 0 or _initial_planets is None:
        _initial_planets = planets
        _prev_comet_positions = {}

    # Build comet velocity estimates from position deltas (one turn apart)
    comet_velocities: dict[int, tuple[float, float]] = {}
    current_comet_positions: dict[int, tuple[float, float]] = {}
    for p in planets:
        if p.id in comet_ids:
            current_comet_positions[p.id] = (p.x, p.y)
            if p.id in _prev_comet_positions:
                px, py = _prev_comet_positions[p.id]
                comet_velocities[p.id] = (p.x - px, p.y - py)
    _prev_comet_positions = current_comet_positions

    return plan_moves(
        planets, fleets, player, angular_velocity, turn,
        comet_ids=comet_ids,
        comet_velocities=comet_velocities,
        initial_planets=_initial_planets,
    )
