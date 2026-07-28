from .math_utils import sum_owned


def total_ships(planets: list, fleets: list, player: int) -> int:
    """Count combined ships for player across all planets and in-transit fleets."""
    planet_ships = sum_owned(planets, player)
    fleet_ships = sum_owned(fleets, player)
    return planet_ships + fleet_ships


def should_play_defensive(
    planets: list,
    fleets: list,
    player: int,
    turn: int,
    threshold_turn: int,
    lead_margin: float,
) -> bool:
    """Return True when winning by lead_margin and past threshold_turn.

    Returns False when enemy_ships == 0 to avoid ZeroDivisionError.
    Returns False when losing (ratio < lead_margin), even past threshold turn.
    Returns False before threshold turn, even when winning.
    """
    if turn < threshold_turn:
        return False

    # Sum every enemy's ships via the shared sum_owned helper (src/math_utils.py),
    # across both planets and in-transit fleets.
    enemy_ships = sum_owned(planets, player, enemy=True) + sum_owned(
        fleets, player, enemy=True
    )

    if enemy_ships == 0:
        return False

    my_ships = total_ships(planets, fleets, player)
    return (my_ships / enemy_ships) >= lead_margin
