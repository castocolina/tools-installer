"""Pin the CI docs-only fast pass and the drift guards that keep its file list honest.

The classifier in ``devtools/docs_only.py`` is standard-library only and never imports
``installer``. The tests inject a fake git runner; no test launches real git (the project
sandbox forbids it). Task 3 adds the reviewed ledger of Markdown literals and the runtime
link-target guard; Task 2 adds the rename and encoding backstops.
"""

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

GIT = "/usr/bin/git"

ROOT = Path(__file__).resolve().parent.parent


def _which(name: str) -> str | None:
    return GIT if name == "git" else None


def _fake_runner(
    stdout: bytes, *, returncode: int = 0
) -> tuple[Callable[[Sequence[str]], subprocess.CompletedProcess[bytes]], list[list[str]]]:
    calls: list[list[str]] = []

    def run(args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        calls.append(list(args))
        return subprocess.CompletedProcess(list(args), returncode, stdout, b"")

    return run, calls


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ([".planning/STATE.md", ".planning/phases/26-x/26-01-SUMMARY.md"], True),
        (["notes/x.md"], True),
        (["installer/a.py"], False),
        ([".github/workflows/ci.yml"], False),
        (["Makefile"], False),
        ([".claude/architecture.md"], False),
        (["AGENTS.md"], False),
        (["README.md"], False),
        (["docs/TROUBLESHOOTING.md"], False),
        ([".claude/skills/catalog-audit/SKILL.md"], False),
        ([".planning/phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-1.md"], False),
        ([".planning/x.md", "installer/a.py"], False),
        ([], False),
    ],
)
def test_the_rule_matrix(paths: list[str], expected: bool) -> None:
    from devtools.docs_only import is_docs_only

    assert is_docs_only(paths) is expected


def test_main_writes_full_false_for_a_planning_only_change(tmp_path: Path) -> None:
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, calls = _fake_runner(b".planning/x.md\0")
    rc = main(["--base", "origin/main", "--github-output", str(output)], run=run, which=_which)
    assert rc == 0
    assert output.read_text().endswith("full=false\n")
    assert calls == [[GIT, "diff", "--name-only", "-z", "--no-renames", "origin/main...HEAD"]]


def test_main_writes_full_true_for_a_code_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, calls = _fake_runner(b"installer/a.py\0")
    rc = main(["--base", "origin/main", "--github-output", str(output)], run=run, which=_which)
    assert rc == 0
    assert output.read_text().endswith("full=true\n")
    assert "installer/a.py" in capsys.readouterr().out
    assert calls == [[GIT, "diff", "--name-only", "-z", "--no-renames", "origin/main...HEAD"]]


def test_a_python_file_renamed_into_planning_runs_everything(tmp_path: Path) -> None:
    """SPEC R5 encoding backstop: --no-renames lists both paths of a rename (D-16)."""
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, _ = _fake_runner(b"installer/a.py\0.planning/a.py\0")
    assert main(["--github-output", str(output)], run=run, which=_which) == 0
    assert output.read_text().endswith("full=true\n")


def test_a_path_with_a_space_or_newline_is_one_path(tmp_path: Path) -> None:
    """SPEC R5 encoding backstop: -z keeps a space and a newline inside one path (D-16)."""
    from devtools.docs_only import is_docs_only, main

    output = tmp_path / "github_output"
    run, _ = _fake_runner(b".planning/a b.md\0.planning/c\nd.md\0")
    assert main(["--github-output", str(output)], run=run, which=_which) == 0
    assert output.read_text().endswith("full=false\n")
    assert is_docs_only([".planning/a b.md", ".planning/c\nd.md"]) is True

    output = tmp_path / "github_output_code"
    run, _ = _fake_runner(b"installer/a b.py\0")
    assert main(["--github-output", str(output)], run=run, which=_which) == 0
    assert output.read_text().endswith("full=true\n")


def test_uppercase_md_is_not_markdown() -> None:
    """SPEC R5 encoding backstop: the .md suffix match is exact and lowercase (D-16)."""
    from devtools.docs_only import is_docs_only

    assert is_docs_only(["NOTES.MD"]) is False


def test_git_failure_runs_everything(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """D-16: a git failure, such as no merge base, fails closed to a full run."""
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, _ = _fake_runner(b"", returncode=128)
    assert main(["--github-output", str(output)], run=run, which=_which) == 0
    assert output.read_text().endswith("full=true\n")
    assert "no change list" in capsys.readouterr().out


def test_missing_git_runs_everything(tmp_path: Path) -> None:
    """D-16: a missing git fails closed to a full run and never runs a command."""
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, calls = _fake_runner(b"")
    assert main(["--github-output", str(output)], run=run, which=lambda name: None) == 0
    assert output.read_text().endswith("full=true\n")
    assert calls == []


def test_empty_change_runs_everything(tmp_path: Path) -> None:
    """D-16: an empty change list fails closed to a full run, never a fast pass."""
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, _ = _fake_runner(b"")
    assert main(["--github-output", str(output)], run=run, which=_which) == 0
    assert output.read_text().endswith("full=true\n")


def test_output_file_gets_exactly_one_line(tmp_path: Path) -> None:
    """D-16: one classification appends exactly one full=... line to the output file."""
    from devtools.docs_only import main

    output = tmp_path / "github_output"
    run, _ = _fake_runner(b".planning/x.md\0")
    assert main(["--github-output", str(output)], run=run, which=_which) == 0
    assert output.read_text().splitlines() == ["full=false"]
