"""Run a local game between our agent and the built-in random agent."""

from kaggle_environments import make

from src.agent import agent


def format_game_result(reward0: int | float, reward1: int | float) -> str:
    """Return a one-line human-readable summary of who won.

    Mirrors the winner logic in trials/game_runner.py: reward[0] > reward[1]
    means player 0 (our agent) wins; equal rewards are a draw.
    """
    if reward0 > reward1:
        return f"Result: our agent WINS (reward {reward0} vs {reward1})"
    if reward1 > reward0:
        return f"Result: starter WINS (reward {reward0} vs {reward1})"
    return f"Result: DRAW (reward {reward0} vs {reward1})"


if __name__ == "__main__":
    env = make("orbit_wars", debug=True)
    env.run([agent, "starter"])

    reward0 = env.state[0].reward
    reward1 = env.state[1].reward
    print(format_game_result(reward0, reward1))

    # Final observation for quick eyeballing of planet/ship counts
    print(env.steps[-1][0]["observation"])
