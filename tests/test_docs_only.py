"""Pin the CI docs-only fast pass and the drift guards that keep its file list honest.

The classifier in ``devtools/docs_only.py`` is standard-library only and never imports
``installer``. The tests inject a fake git runner; no test launches real git (the project
sandbox forbids it). Task 3 adds the reviewed ledger of Markdown literals and the runtime
link-target guard; Task 2 adds the rename and encoding backstops.
"""

import ast
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

GIT = "/usr/bin/git"

ROOT = Path(__file__).resolve().parent.parent


def _which(name: str) -> str | None:
    return GIT if name == "git" else None


# shortcut: a test that reads a repo file through a path with neither a `.md` or `.planning`
# literal nor a LINK_CHECKED_DOCS link is not seen; extend the scan if one appears.
def markdown_literals() -> set[tuple[str, str]]:
    """(test file, literal) for every .md / .planning string literal in the other tests."""
    pairs: set[tuple[str, str]] = set()
    for source in sorted((ROOT / "tests").rglob("*.py")):
        if source.resolve() == Path(__file__).resolve():
            continue
        rel = source.relative_to(ROOT).as_posix()
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            literal = node.value
            if (
                literal.endswith(".md")
                or literal == ".planning"
                or literal.startswith(".planning/")
            ):
                pairs.add((rel, literal))
    return pairs


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


# One reviewed entry per pair from markdown_literals(). A real file-glob the test reads maps to
# that glob (as Path.glob takes it); scratch paths under tmp_path and asserted text map to None.
LEDGER: dict[tuple[str, str], str | None] = {
    # tmp_path scratch paths and asserted text, never a repo file (D-16).
    ("tests/test_catalog_audit.py", ".md"): None,  # f-string report suffix
    ("tests/test_catalog_audit.py", ".planning"): None,
    ("tests/test_catalog_audit.py", "SUMMARY.md"): None,
    ("tests/test_catalog_audit.py", "alpha.md"): None,
    ("tests/test_catalog_audit.py", "beta.md"): None,
    ("tests/test_catalog_audit.py", "elsewhere.md"): None,
    ("tests/test_catalog_audit.py", "gone.md"): None,
    ("tests/test_catalog_audit.py", "scripts.md"): None,
    ("tests/test_catalog_audit.py", "stray.md"): None,
    ("tests/test_catalog_audit.py", "verify-registry.md"): None,
    # The three SKILLJUDGE verdict files are the .planning/ exception (D-16).
    (
        "tests/test_catalog_audit_skill.py",
        ".planning",
    ): ".planning/phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*.md",
    (
        "tests/test_catalog_audit_skill.py",
        "24.3-SKILLJUDGE-*.md",
    ): ".planning/phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*.md",
    ("tests/test_catalog_audit_skill.py", "SKILL.md"): ".claude/skills/*/SKILL.md",
    (
        "tests/test_catalog_audit_skill.py",
        "references/*.md",
    ): ".claude/skills/catalog-audit/references/*.md",
    (
        "tests/test_catalog_audit_skill.py",
        "report-template.md",
    ): ".claude/skills/catalog-audit/references/report-template.md",
    ("tests/test_container_e2e_landing.py", "AGENTS.md"): None,  # listing text, not a read
    ("tests/test_container_e2e_receipts.py", ".claude/CLAUDE.md"): None,  # scratch listing
    ("tests/test_docs.py", ".md"): None,  # suffix comparison
    ("tests/test_docs.py", "AGENTS.md"): "AGENTS.md",
    ("tests/test_docs.py", "README.md"): "README.md",
    ("tests/test_docs.py", "SKILL.md"): ".claude/skills/*/SKILL.md",
    ("tests/test_docs.py", "TROUBLESHOOTING.md"): "docs/TROUBLESHOOTING.md",
    ("tests/test_docs.py", "architecture.md"): ".claude/architecture.md",
    ("tests/test_docs.py", "dev-environment.md"): ".claude/dev-environment.md",
    ("tests/test_docs.py", "docs/**/*.md"): "docs/**/*.md",
    ("tests/test_docs.py", "git-workflow.md"): ".claude/git-workflow.md",
    ("tests/test_docs.py", "guide.md"): None,  # tmp_path
    ("tests/test_docs.py", "python-tooling.md"): ".claude/python-tooling.md",
    (
        "tests/test_docs.py",
        "report-template.md",
    ): ".claude/skills/catalog-audit/references/report-template.md",
    ("tests/test_docs.py", "root-only.md"): None,  # tmp_path
    ("tests/test_docs.py", "sibling.md"): None,  # tmp_path
    ("tests/test_docs.py", "testing.md"): ".claude/testing.md",
    ("tests/test_hook_wiring.py", "*.md"): ".claude/*.md",
    ("tests/test_hook_wiring.py", "*/SKILL.md"): ".claude/skills/*/SKILL.md",
    ("tests/test_hook_wiring.py", "AGENTS.md"): "AGENTS.md",
    ("tests/test_links.py", "docs/TROUBLESHOOTING.md"): None,  # URL suffix assertion
    ("tests/test_postinstall.py", "architecture.md"): ".claude/architecture.md",
    ("tests/test_postinstall.py", "skills/*/SKILL.md"): ".claude/skills/*/SKILL.md",
    ("tests/test_push_gate.py", ".planning"): None,  # asserted absent from a refusal
    ("tests/test_push_gate.py", ".planning/debug/x.log"): None,  # fake git output
    ("tests/test_push_gate.py", ".planning/notes.md"): None,  # fake git output
    ("tests/test_registry.py", "CLAUDE.md"): None,  # asserted block text
    (
        "tests/test_render.py",
        "  claude: codegraph also adds a prompt hook and ~/.claude/CLAUDE.md",
    ): None,
    ("tests/test_render.py", "  pi: codegraph also adds a block to Pi's AGENTS.md"): None,
    ("tests/test_render.py", "CLAUDE.md"): None,  # asserted render text
}


def test_every_markdown_literal_in_the_tests_is_classified() -> None:
    found, classified = markdown_literals(), set(LEDGER)
    new, stale = sorted(found - classified), sorted(classified - found)
    assert not new and not stale, (
        f"new pairs (classify them): {new}\nstale pairs (remove them): {stale}"
    )


def test_every_ledger_glob_reads_test_read_files_only() -> None:
    from devtools.docs_only import is_docs_path

    for (test_file, literal), glob in LEDGER.items():
        if glob is None:
            continue
        matches = sorted(ROOT.glob(glob))
        assert matches, f"{test_file}: {literal!r} -> {glob!r} resolves to no file"
        for path in matches:
            rel = path.relative_to(ROOT).as_posix()
            assert not is_docs_path(rel), f"{test_file}: {literal!r} -> {rel} is docs-only"


def test_the_ledger_covers_the_known_readers() -> None:
    assert LEDGER[("tests/test_catalog_audit_skill.py", "24.3-SKILLJUDGE-*.md")] == (
        ".planning/phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*.md"
    )
    assert LEDGER[("tests/test_postinstall.py", "skills/*/SKILL.md")] == (
        ".claude/skills/*/SKILL.md"
    )


# A drift test, not a link parser inside the CI classifier: a new link edits README or
# TROUBLESHOOTING (both test-read), so it runs the full suite where the drift test fails until the
# target joins TEST_READ. The classifier stays small and stdlib-only on its first push.
def docs_only_link_targets(doc: Path, root: Path) -> list[str]:
    from devtools.docs_only import is_docs_path
    from tests.test_docs import link_targets

    resolved_root = root.resolve()
    offenders: list[str] = []
    for target in link_targets(doc):
        path_part, _, _ = target.partition("#")
        if not path_part:
            continue
        dest = (doc.parent / path_part).resolve()
        if not dest.exists() or not dest.is_relative_to(resolved_root):
            continue
        rel = dest.relative_to(resolved_root).as_posix()
        if is_docs_path(rel):
            offenders.append(rel)
    return sorted(offenders)


def test_every_runtime_resolved_link_target_is_test_read() -> None:
    from devtools.docs_only import is_docs_path
    from tests.test_docs import LINK_CHECKED_DOCS, link_targets

    for doc in LINK_CHECKED_DOCS:
        assert not is_docs_path(doc.relative_to(ROOT).as_posix()), f"{doc.name} is docs-only"
        for target in link_targets(doc):
            path_part, _, _ = target.partition("#")
            if not path_part:
                continue
            dest = (doc.parent / path_part).resolve()
            assert dest.exists(), f"{doc.name}: {target} does not exist"
            assert dest.is_relative_to(ROOT), f"{doc.name}: {target} leaves the repo"
            rel = dest.relative_to(ROOT).as_posix()
            assert not is_docs_path(rel), (
                f"{doc.name}: link {target} resolves to docs-only {rel}; add the target to"
                " TEST_READ in devtools/docs_only.py"
            )


def test_the_link_drift_test_catches_a_planning_target(tmp_path: Path) -> None:
    doc = tmp_path / "README.md"
    doc.write_text("[a](notes.md) [b](.planning/plan.md) [c](installer/x.py)\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    (tmp_path / ".planning").mkdir()
    (tmp_path / ".planning" / "plan.md").write_text("", encoding="utf-8")
    (tmp_path / "installer").mkdir()
    (tmp_path / "installer" / "x.py").write_text("", encoding="utf-8")
    assert docs_only_link_targets(doc, tmp_path) == [".planning/plan.md", "notes.md"]
