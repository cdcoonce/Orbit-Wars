"""Tests for trials/benchmark.py ORIGINAL_DEFAULTS integrity."""

from conftest import assert_covers_params
from src.config import PARAMS
from trials.game_runner import tally_results


class TestTallyResults:
    def test_mixed_results_returns_correct_counts(self):
        results = ["challenger", "champion", "draw", "challenger", "draw", "challenger"]
        tally = tally_results(results)
        assert tally["challenger"] == 3
        assert tally["champion"] == 1
        assert tally["draw"] == 2

    def test_empty_list_returns_all_zeros(self):
        tally = tally_results([])
        assert tally["challenger"] == 0
        assert tally["champion"] == 0
        assert tally["draw"] == 0


class TestOriginalDefaults:
    def test_contains_every_params_key(self):
        """ORIGINAL_DEFAULTS must hold every key strategy.py indexes with params[...].

        plan_moves/plan_expansion read params via bracket indexing (not .get),
        so a missing key (e.g. the ramp params) makes the opponent agent raise
        KeyError every turn and the benchmark silently reports all-draws.
        """
        from trials.benchmark import ORIGINAL_DEFAULTS

        assert_covers_params(ORIGINAL_DEFAULTS, "ORIGINAL_DEFAULTS")

    def test_preserves_hand_tuned_overrides(self):
        """The original hand-tuned values must survive the full-defaults merge."""
        from trials.benchmark import ORIGINAL_DEFAULTS

        assert ORIGINAL_DEFAULTS["fortress_min_ships"] == 40
        assert ORIGINAL_DEFAULTS["weak_ratio"] == 1.5
        assert ORIGINAL_DEFAULTS["stationary_value_bonus"] == 1
        assert ORIGINAL_DEFAULTS["min_garrison"] == 15

    def test_every_frac_key_has_explicit_override(self):
        """Every frac_* key in PARAMS must be explicitly overridden, not inherited from the tuned merge.

        ORIGINAL_DEFAULTS is `{**PARAMS, <hand-picked overrides>}`, so any frac_*
        key without an explicit entry in HAND_TUNED_OVERRIDES silently leaks the
        current tuned PARAMS value into the "original" benchmark arm. This
        happened for frac_fortress_hardened_enemy after dc7f697 removed
        ("FORTRESS", "HARDENED_ENEMY") from SKIP_COMBOS and introduced the knob.
        """
        from trials.benchmark import HAND_TUNED_OVERRIDES

        frac_keys = {key for key in PARAMS if key.startswith("frac_")}
        missing = frac_keys - set(HAND_TUNED_OVERRIDES)
        assert not missing, (
            f"frac_* keys missing an explicit ORIGINAL_DEFAULTS override: {sorted(missing)}"
        )


class TestBenchmarkSeed:
    def test_benchmark_seed_is_non_none_integer(self):
        """BENCHMARK_SEED must be a non-None integer so the benchmark is reproducible.

        Importing the constant (not just checking the call site) ensures the
        determinism guarantee cannot silently regress if the constant is removed
        or set to None.
        """
        from trials.benchmark import BENCHMARK_SEED

        assert BENCHMARK_SEED is not None
        assert isinstance(BENCHMARK_SEED, int)
