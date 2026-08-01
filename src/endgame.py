from .math_utils import sum_owned


def total_ships(planets: list, fleets: list, player: int) -> int:
    """Count combined ships for player across all planets and in-transit fleets."""
    return sum_owned(planets, player) + sum_owned(fleets, player)


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

    # Enemy bucket spans every non-player, non-neutral owner over both planets and
    # in-transit fleets — the same planets+fleets shape as total_ships above.
    # sum_owned(..., enemy=True) is the shared definition of that filter, which
    # score_state in lookahead.py uses too.
    enemy_ships = sum_owned(planets, player, enemy=True) + sum_owned(
        fleets, player, enemy=True
    )

    if enemy_ships == 0:
        return False

    my_ships = total_ships(planets, fleets, player)
    return (my_ships / enemy_ships) >= lead_margin
