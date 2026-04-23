"""Run a local game between our agent and the built-in random agent."""

from kaggle_environments import make

from src.agent import agent

env = make("orbit_wars", debug=True)
env.run([agent, "starter"])

# Render a summary to stdout
print(env.steps[-1][0]["observation"])
