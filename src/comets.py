"""Comet utilities for Orbit Wars.

Comets are planets that temporarily visit the map. Their production value should
be scaled by a multiplier so the agent can treat them as less (or more) attractive
targets than permanent planets.
"""
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet


def get_comet_ids(obs: dict) -> set[int]:
    """Return the set of planet IDs that are currently comets.

    Uses ``obs.get("comet_planet_ids") or []`` so the result is always a set
    even when the key is absent or the value is None.
    """
    return set(obs.get("comet_planet_ids") or [])


def effective_production(planet: Planet, comet_ids: set, multiplier: float) -> float:
    """Return the production value used for scoring this planet.

    If *planet* is in *comet_ids* the raw production is scaled by *multiplier*;
    otherwise the raw production is returned unchanged.

    A *multiplier* of 0.0 makes comets invisible to targeting.
    A *multiplier* of 2.0 doubles their apparent value.
    Non-comet planets always return their raw production regardless of *multiplier*.
    """
    if planet.id in comet_ids:
        return planet.production * multiplier
    return float(planet.production)
