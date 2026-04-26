"""Self-play game runner for Optuna trial evaluation."""
import concurrent.futures

from kaggle_environments import make
from kaggle_environments.envs.orbit_wars.orbit_wars import Fleet, Planet

from src.comets import get_comet_ids
from src.strategy import plan_moves

TIMEOUT_SECONDS = 60


def make_agent(params: dict):
    """Return a closure that runs plan_moves with the given params.

    Each agent closure maintains its own initial_planets cache so parallel
    games don't share state.
    """
    initial_planets = None

    def agent(obs: dict) -> list:
        nonlocal initial_planets
        planets = [Planet(*p) for p in obs.get("planets", [])]
        fleets = [Fleet(*f) for f in obs.get("fleets", [])]
        player = obs.get("player", 0)
        angular_velocity = obs.get("angular_velocity", 0.0)
        turn = obs.get("step", 0)
        comet_ids = get_comet_ids(obs)

        if turn == 0 or initial_planets is None:
            initial_planets = planets

        return plan_moves(
            planets, fleets, player, angular_velocity, turn,
            params=params, comet_ids=comet_ids, initial_planets=initial_planets,
        )

    return agent


def run_game(
    challenger_params: dict,
    champion_params: dict,
    challenger_player: int = 0,
    timeout: float = TIMEOUT_SECONDS,
) -> str:
    """Run one game. Returns 'challenger', 'champion', or 'draw'."""
    challenger = make_agent(challenger_params)
    champion = make_agent(champion_params)

    if challenger_player == 0:
        agents = [challenger, champion]
    else:
        agents = [champion, challenger]

    def _run():
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return "draw"


def run_games(
    challenger_params: dict,
    champion_params: dict,
    n_games: int = 10,
) -> tuple[float, list[str]]:
    """Run n_games with alternating player assignment.

    Challenger is player ``i % 2`` for game index ``i``, so neither side
    has a consistent first-move advantage over the series.

    Returns ``(win_rate, results)`` where results is a list of
    'challenger' | 'champion' | 'draw' strings.
    """
    results = []
    for i in range(n_games):
        result = run_game(challenger_params, champion_params, challenger_player=i % 2)
        results.append(result)
    wins = sum(1 for r in results if r == "challenger")
    win_rate = wins / n_games
    return win_rate, results
