from src.config import PARAMS, PARAM_SPACE


def test_param_space_covers_all_tunable_params():
    assert set(PARAM_SPACE.keys()) == set(PARAMS.keys()) - {"game_length"}
