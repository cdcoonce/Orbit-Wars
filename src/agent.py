from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .comets import get_comet_ids
from .strategy import plan_moves

_initial_planets = None


def agent(obs: dict) -> list[list]:
    global _initial_planets
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)
    angular_velocity = obs.get("angular_velocity", 0.0)
    turn = obs.get("step", 0)
    comet_ids = get_comet_ids(obs)

    if turn == 0 or _initial_planets is None:
        _initial_planets = planets

    return plan_moves(
        planets, fleets, player, angular_velocity, turn,
        comet_ids=comet_ids,
        initial_planets=_initial_planets,
    )
