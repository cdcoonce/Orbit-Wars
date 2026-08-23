"""docs/wiki/Tuning-Pipeline.md must describe the real game-runner executor.

`trials/game_runner.py::_get_pool` lazily creates a shared, module-level
`concurrent.futures.ProcessPoolExecutor` — not a per-call
`ThreadPoolExecutor(max_workers=1)`. The module docstring explains this is
deliberate: separate *processes* give each game an isolated global `random`
RNG so seeded self-play games stay reproducible under Optuna's `n_jobs=4`
thread pool (issue #200).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TUNING_PIPELINE_MD = REPO_ROOT / "docs" / "wiki" / "Tuning-Pipeline.md"


def _wiki_files():
    return list((REPO_ROOT / "docs" / "wiki").rglob("*.md"))


class TestGameRunnerExecutorDescription:
    def test_tuning_pipeline_describes_process_pool_executor(self):
        text = TUNING_PIPELINE_MD.read_text()
        assert "ProcessPoolExecutor" in text, (
            "Tuning-Pipeline.md must describe the shared ProcessPoolExecutor "
            "that trials/game_runner.py::_get_pool actually uses."
        )

    def test_tuning_pipeline_explains_process_isolation_rationale(self):
        text = TUNING_PIPELINE_MD.read_text().lower()
        assert "rng" in text or "random" in text, (
            "Tuning-Pipeline.md must explain why the pool is process-based: "
            "separate processes give each game an isolated global random RNG "
            "for reproducible seeding (see trials/game_runner.py docstring)."
        )

    def test_no_wiki_page_references_stale_thread_pool_description(self):
        offenders = [
            p for p in _wiki_files() if "ThreadPoolExecutor(max_workers=1)" in p.read_text()
        ]
        rel = sorted(str(p.relative_to(REPO_ROOT)) for p in offenders)
        assert not offenders, f"stale ThreadPoolExecutor(max_workers=1) description still present in: {rel}"
