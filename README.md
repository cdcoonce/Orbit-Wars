# Orbit Wars

Kaggle competition bot — captures the most ships by turn 500 across orbiting planets.

## Quickstart

```bash
uv run pytest tests/ --ignore=tests/test_trial_runner.py   # fast test suite (no optuna)
uv run pytest tests/ -v                                     # full suite (requires optuna)
uv run python run_game.py                                   # local game vs starter agent
```

## Build & Submit

```bash
python build.py                                                              # → submission.py
kaggle competitions submit -c orbit-wars -f submission.py -m "description"  # submit to Kaggle
```

## Further Reading

- Architecture and data flow: [`.claude/docs/project.md`](.claude/docs/project.md)
- Tuning workflow and key files: [`CLAUDE.md`](CLAUDE.md)
