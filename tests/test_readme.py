"""README.md content integrity tests (issue #91).

Verifies that README.md is a well-formed, non-duplicating entry point:
- non-empty with required sections
- commands match CLAUDE.md verbatim (no drift)
- links to .claude/docs/project.md and CLAUDE.md resolve
- no duplication of full architecture detail
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
README = REPO_ROOT / "README.md"

# Verbatim command prefixes pulled from CLAUDE.md; README must contain each.
_REQUIRED_COMMANDS = [
    "uv run pytest tests/ --ignore=tests/test_trial_runner.py",
    "uv run pytest tests/ -v",
    "uv run python run_game.py",
    "python build.py",
    "kaggle competitions submit -c orbit-wars -f submission.py -m",
]

# Strings that belong only in .claude/docs/project.md, not the README.
_ARCH_STRINGS = [
    "### Tiered Planet Classifier",
    "ROTATION_RADIUS_LIMIT",
    "SimPlanet",
]


def _text():
    return README.read_text()


class TestReadmeExists:
    def test_readme_is_nonempty(self):
        assert README.exists()
        assert len(_text().strip()) > 0

    def test_readme_has_title(self):
        assert any(line.startswith("# ") for line in _text().splitlines())

    def test_readme_mentions_orbit_wars(self):
        assert "Orbit Wars" in _text()

    def test_readme_mentions_kaggle(self):
        text = _text()
        assert "Kaggle" in text or "kaggle" in text


class TestReadmeCommands:
    def test_all_required_commands_present(self):
        text = _text()
        missing = [cmd for cmd in _REQUIRED_COMMANDS if cmd not in text]
        assert not missing, f"commands missing from README: {missing}"


class TestReadmeLinks:
    def test_links_to_project_md(self):
        assert ".claude/docs/project.md" in _text()

    def test_links_to_claude_md(self):
        assert "CLAUDE.md" in _text()

    def test_project_md_path_resolves(self):
        assert (REPO_ROOT / ".claude" / "docs" / "project.md").exists()

    def test_claude_md_path_resolves(self):
        assert (REPO_ROOT / "CLAUDE.md").exists()


class TestReadmeIsIndex:
    def test_no_full_architecture_duplication(self):
        text = _text()
        duplication = [s for s in _ARCH_STRINGS if s in text]
        assert not duplication, f"architecture detail duplicated in README: {duplication}"
