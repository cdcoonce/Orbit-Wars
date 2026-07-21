"""Self-play game runner for Optuna trial evaluation.

The Kaggle ``orbit_wars`` engine builds every map (planet groups, ships,
``angular_velocity``) and spawns comets from Python's *global* ``random``
module, and it exposes no seed config. Threads within one process share that
single global RNG, so ``run_trials.py`` — which runs Optuna with ``n_jobs=4``
(a thread pool) — would have concurrent games clobber one another's seed.

To make seeding reproducible *and* keep that parallelism, each game runs in a
worker of a shared :class:`ProcessPoolExecutor`. Separate processes have
independent global RNGs, so seeding inside a worker is isolated from the caller
and from sibling workers. Reusing one pool amortises the engine import cost
across the thousands of games a tuning run plays.
"""
import concurrent.futures
import logging
import random
import threading

from kaggle_environments import make

from src.agent import plan_turn

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60

# Lazily-created shared worker pool (see module docstring). Guarded so the
# Optuna threads that call run_game concurrently all share one pool.
_pool: concurrent.futures.ProcessPoolExecutor | None = None
_pool_lock = threading.Lock()


def _get_pool() -> concurrent.futures.ProcessPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = concurrent.futures.ProcessPoolExecutor()
        return _pool


def make_agent(params: dict):
    """Return a closure that plans each turn via the shared comet-aware wrapper.

    Delegates to :func:`src.agent.plan_turn` — the same per-turn wrapper the
    deployed agent uses — so Optuna tunes against the comet-velocity-aware
    targeting that actually ships, rather than a comet-blind agent. Each closure
    keeps its own initial-planet and comet-position state so parallel games
    don't share it.
    """
    initial_planets = None
    prev_comet_positions: dict[int, tuple[float, float]] = {}

    def agent(obs: dict) -> list:
        nonlocal initial_planets, prev_comet_positions
        moves, initial_planets, prev_comet_positions = plan_turn(
            obs, initial_planets, prev_comet_positions, params=params,
        )
        return moves

    return agent


def _play_game(
    challenger_params: dict,
    champion_params: dict,
    challenger_player: int,
    seed: int | None,
) -> str:
    """Worker body — runs in a separate process so its global RNG is isolated.

    Agents are rebuilt here (closures can't cross the process boundary; only the
    picklable params dicts do). When ``seed`` is given, the process-local global
    RNG is seeded immediately before ``env.run`` so the engine builds an
    identical map. Returns 'challenger', 'champion', or 'draw'.
    """
    challenger = make_agent(challenger_params)
    champion = make_agent(champion_params)
    agents = [challenger, champion] if challenger_player == 0 else [champion, challenger]

    if seed is not None:
        random.seed(seed)
    env = make("orbit_wars", debug=False)
    env.run(agents)
    rewards = [env.state[i].reward for i in range(2)]
    if rewards[0] > rewards[1]:
        winner = 0
    elif rewards[1] > rewards[0]:
        winner = 1
    else:
        return "draw"
    return "challenger" if winner == challenger_player else "champion"


def run_game(
    challenger_params: dict,
    champion_params: dict,
    challenger_player: int = 0,
    timeout: float = TIMEOUT_SECONDS,
    seed: int | None = None,
) -> str:
    """Run one game in an isolated worker process. Returns the winner string.

    Because the game runs in its own process, a ``seed`` reproducibly controls
    the map without disturbing the caller's RNG — so paired games (one seed,
    challenger on each side) and concurrent trials stay deterministic. A game
    exceeding ``timeout`` (or erroring) is scored a 'draw'.
    """
    global _pool
    try:
        future = _get_pool().submit(
            _play_game, challenger_params, champion_params, challenger_player, seed,
        )
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return "draw"
    except concurrent.futures.process.BrokenProcessPool:
        logger.exception("Worker pool broke; resetting pool and scoring as draw")
        with _pool_lock:
            _pool = None
        return "draw"
    except Exception:
        logger.exception("Worker raised an unexpected exception; scoring as draw")
        return "draw"


def tally_results(results: list[str]) -> dict[str, int]:
    """Count wins, losses, and draws from a results list.

    Returns ``{"challenger": w, "champion": l, "draw": d}`` — all three keys
    are always present, even when a result type does not appear in the list.
    """
    base: dict[str, int] = {"challenger": 0, "champion": 0, "draw": 0}
    for r in results:
        base[r] += 1
    return base


def run_games(
    challenger_params: dict,
    champion_params: dict,
    n_games: int = 10,
    seed: int | None = None,
) -> tuple[float, list[str]]:
    """Run n_games with alternating player assignment.

    Challenger is player ``i % 2`` for game index ``i``, so neither side
    has a consistent first-move advantage over the series.

    When ``seed`` is given, games are played in paired batches: games ``2k`` and
    ``2k+1`` share the map seed ``seed + k`` but swap the challenger's side, so
    map-luck cancels and the whole series is reproducible. With ``seed=None`` the
    games use fresh, unseeded maps (legacy behaviour).

    Returns ``(win_rate, results)`` where results is a list of
    'challenger' | 'champion' | 'draw' strings.
    """
    results = []
    for i in range(n_games):
        challenger_player = i % 2
        if seed is None:
            result = run_game(
                challenger_params, champion_params,
                challenger_player=challenger_player,
            )
        else:
            result = run_game(
                challenger_params, champion_params,
                challenger_player=challenger_player, seed=seed + i // 2,
            )
        results.append(result)
    tally = tally_results(results)
    win_rate = tally["challenger"] / n_games
    return win_rate, results
