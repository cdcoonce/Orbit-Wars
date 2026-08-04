from src.config import PARAMS


def assert_covers_params(d, name="params", exact=False):
    """Assert `d` contains every key in src.config.PARAMS.

    Shared by champion/benchmark/trial_runner integrity checks: a missing
    tunable raises KeyError during game simulation, so any gap here is a bug.

    With `exact=True` the key sets must match exactly — extra keys in `d`
    (obsolete tunables that no longer exist in PARAMS) also fail.
    """
    missing = set(PARAMS) - set(d)
    assert not missing, f"{name} is missing keys: {sorted(missing)}"
    if exact:
        extra = set(d) - set(PARAMS)
        assert not extra, f"{name} has unknown keys: {sorted(extra)}"
