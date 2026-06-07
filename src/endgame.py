def total_ships(planets: list, fleets: list, player: int) -> int:
    """Count combined ships for player across all planets and in-transit fleets."""
    planet_ships = sum(p.ships for p in planets if p.owner == player)
    fleet_ships = sum(f.ships for f in fleets if f.owner == player)
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

    # Sum every enemy's ships — across all non-player, non-neutral owners — over
    # both planets and in-transit fleets (same planets+fleets shape as
    # total_ships above; the owner filter matches score_state in lookahead.py).
    enemy_ships = sum(
        p.ships for p in planets if p.owner not in (-1, player)
    ) + sum(
        f.ships for f in fleets if f.owner not in (-1, player)
    )

    if enemy_ships == 0:
        return False

    my_ships = total_ships(planets, fleets, player)
    return (my_ships / enemy_ships) >= lead_margin
