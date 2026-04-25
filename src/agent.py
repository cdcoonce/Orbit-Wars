from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from .strategy import plan_moves


def agent(obs: dict) -> list[list]:
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)
    angular_velocity = obs.get("angular_velocity", 0.0)
    turn = obs.get("step", 0)

    return plan_moves(planets, fleets, player, angular_velocity, turn)
