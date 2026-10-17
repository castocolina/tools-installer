"""Black-box tests for container shell rc file appends and shell-script PATH scanning.

Task 1: Extract the guarded PATH export from scripts/container-e2e-verify.sh and run
it in real bash, zsh, and /bin/sh to prove runtime idempotency. The guard's own line
is extracted from the committed file (never re-typed), run three times, then re-sourced
five times in each shell to assert exactly one copy of the directory on PATH.

Task 2: Scan every shell script in the repository for accumulating PATH prepends
(the same parameter-expansion coverage as plan 15.8-03's Python needle) and reject
any hit not explicitly classified by property. The only accepted hits are three
one-shot exports that execute once per process and are never re-sourced by a nested
shell.

This test file follows tests/test_prune_tmp_linux_sh.py's pattern: minimal explicit
env (never os.environ wholesale), absolute shell path from shutil.which with explicit
skips, subprocess.run with timeout, and extracted source-of-truth from the committed
files rather than re-typed assertions.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "container-e2e-verify.sh"
INSTALL_SCRIPT = ROOT / "install.sh"
SCRIPTS_DIR = ROOT / "scripts"
SHELLRC = ROOT / "installer" / "shellrc.py"


def _get_bash() -> str | None:
    """Absolute path to bash, or None if not found."""
    return shutil.which("bash")


def _get_zsh() -> str | None:
    """Absolute path to zsh, or None if not found."""
    return shutil.which("zsh")


def _get_sh() -> str | None:
    """Absolute path to /bin/sh, or None if not found."""
    return shutil.which("sh")


# ============================================================================
# TASK 1: End-to-end container rc idempotency proof
# ============================================================================


def _write_tester_path_payload() -> str:
    """Extract the payload passed to exec_tester in write_tester_path().

    Reads scripts/container-e2e-verify.sh, finds the write_tester_path() function,
    and extracts the string between the first ' after exec_tester and the closing '
    on its own line. Assert the extracted payload is non-empty and contains
    '.local/bin' so a future refactor that renames the function fails loudly.
    """
    script_text = SCRIPT.read_text()

    # Find write_tester_path function
    match = re.search(
        r"^write_tester_path\(\)\s*\{",
        script_text,
        re.MULTILINE,
    )
    assert match, "write_tester_path() function not found in container-e2e-verify.sh"
    func_start = match.start()

    # Find the exec_tester call and extract its payload
    payload_match = re.search(
        r"exec_tester\s+'(.*?)'(?:\n[}'\s]*)?$",
        script_text[func_start:],
        re.MULTILINE | re.DOTALL,
    )
    assert payload_match, "exec_tester payload not found in write_tester_path()"

    payload = payload_match.group(1)
    assert payload.strip(), "extracted payload is empty"
    assert ".local/bin" in payload, "extracted payload does not contain .local/bin"

    return payload


pytestmark = pytest.mark.skipif(_get_bash() is None, reason="bash not on PATH")


def test_the_container_rc_append_is_runtime_idempotent(tmp_path: Path) -> None:
    """Run the extracted rc append payload three times, then source the result
    five times in bash to prove the guard prevents accumulation.

    The payload writes to ~/.bash_profile and ~/.bashrc under tmp_path (so no real
    dotfile is touched). Run it three times sequentially. Then assert each file
    contains exactly ONE line naming .local/bin. Finally, source each file five
    times and assert exactly one copy of the directory on PATH each time.
    """
    bash_path = _get_bash()
    assert bash_path, "bash not found"

    payload = _write_tester_path_payload()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}

    # Run the payload three times
    for run_num in range(3):
        result = subprocess.run(
            [bash_path, "-c", payload],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, f"payload run {run_num + 1} failed: {result.stderr}"

    bash_profile = tmp_path / ".bash_profile"
    bashrc = tmp_path / ".bashrc"

    # After three runs, each file should have exactly one line containing .local/bin
    bash_profile_text = bash_profile.read_text()
    bashrc_text = bashrc.read_text()

    bash_profile_lines = [line for line in bash_profile_text.splitlines() if ".local/bin" in line]
    bashrc_lines = [line for line in bashrc_text.splitlines() if ".local/bin" in line]

    assert len(bash_profile_lines) == 1, (
        f"~/.bash_profile has {len(bash_profile_lines)} .local/bin lines, expected 1"
    )
    assert len(bashrc_lines) == 1, f"~/.bashrc has {len(bashrc_lines)} .local/bin lines, expected 1"

    # Now source each file five times and verify PATH has exactly one copy
    # of the directory
    for source_file, expected_count in [
        (".bash_profile", 1),
        (".bashrc", 1),
    ]:
        result = subprocess.run(
            [
                bash_path,
                "-c",
                f"""
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                printf '%s' "$PATH"
                """,
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, f"sourcing {source_file} failed: {result.stderr}"

        path_entries = result.stdout.split(":")
        local_bin_path = str(tmp_path / ".local" / "bin")
        local_bin_count = sum(1 for entry in path_entries if entry == local_bin_path)

        assert local_bin_count == expected_count, (
            f"{source_file} has {local_bin_count} copies of "
            f"{local_bin_path} on PATH, expected {expected_count}"
        )


@pytest.mark.skipif(_get_zsh() is None, reason="zsh not on PATH")
def test_the_container_rc_append_is_idempotent_under_zsh(tmp_path: Path) -> None:
    """Same test as above, but run under zsh (with -f to skip user rc files)."""
    zsh_path = _get_zsh()
    assert zsh_path, "zsh not found"

    payload = _write_tester_path_payload()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}

    # Run the payload three times
    for run_num in range(3):
        result = subprocess.run(
            [zsh_path, "-f", "-c", payload],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"payload run {run_num + 1} failed under zsh: {result.stderr}"
        )

    bash_profile = tmp_path / ".bash_profile"
    bashrc = tmp_path / ".bashrc"

    bash_profile_lines = [
        line for line in bash_profile.read_text().splitlines() if ".local/bin" in line
    ]
    bashrc_lines = [line for line in bashrc.read_text().splitlines() if ".local/bin" in line]

    assert len(bash_profile_lines) == 1
    assert len(bashrc_lines) == 1

    # Source five times under zsh
    for source_file in [".bash_profile", ".bashrc"]:
        result = subprocess.run(
            [
                zsh_path,
                "-f",
                "-c",
                f"""
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                source {tmp_path / source_file}
                printf '%s' "$PATH"
                """,
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, f"sourcing {source_file} failed under zsh: {result.stderr}"

        path_entries = result.stdout.split(":")
        local_bin_path = str(tmp_path / ".local" / "bin")
        local_bin_count = sum(1 for entry in path_entries if entry == local_bin_path)
        assert local_bin_count == 1


@pytest.mark.skipif(_get_sh() is None, reason="/bin/sh not on PATH")
def test_the_container_rc_append_is_idempotent_under_sh(tmp_path: Path) -> None:
    """Same test under /bin/sh. Note: /bin/sh on this host is bash invoked as sh,
    so this is POSIX-DIALECT coverage rather than dash proof, as documented in
    the module docstring."""
    sh_path = _get_sh()
    assert sh_path, "/bin/sh not found"

    payload = _write_tester_path_payload()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}

    # Run the payload three times
    for run_num in range(3):
        result = subprocess.run(
            [sh_path, "-c", payload],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"payload run {run_num + 1} failed under /bin/sh: {result.stderr}"
        )

    bash_profile = tmp_path / ".bash_profile"
    bashrc = tmp_path / ".bashrc"

    bash_profile_lines = [
        line for line in bash_profile.read_text().splitlines() if ".local/bin" in line
    ]
    bashrc_lines = [line for line in bashrc.read_text().splitlines() if ".local/bin" in line]

    assert len(bash_profile_lines) == 1
    assert len(bashrc_lines) == 1

    # Source five times under /bin/sh
    for source_file in [".bash_profile", ".bashrc"]:
        result = subprocess.run(
            [
                sh_path,
                "-c",
                f"""
                . {tmp_path / source_file}
                . {tmp_path / source_file}
                . {tmp_path / source_file}
                . {tmp_path / source_file}
                . {tmp_path / source_file}
                printf '%s' "$PATH"
                """,
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"sourcing {source_file} failed under /bin/sh: {result.stderr}"
        )

        path_entries = result.stdout.split(":")
        local_bin_path = str(tmp_path / ".local" / "bin")
        local_bin_count = sum(1 for entry in path_entries if entry == local_bin_path)
        assert local_bin_count == 1


def test_the_container_guard_and_the_python_emitter_share_one_shape() -> None:
    """Assert the guard line from the script and path_export_guard(Path("/a/bin"))
    share structural properties.

    Both must start with 'case', read PATH through the default-applying expansion
    ${PATH-}, and contribute the new value through the conditional expansion
    ${PATH:+:$PATH}. Both will have the :/dir: pattern in the case guard, which
    is the structural commonality, not a defect.
    """
    from installer.shellrc import path_export_guard

    payload = _write_tester_path_payload()

    # Extract the guard line from the payload (the one containing 'case')
    guard_line = None
    for line in payload.splitlines():
        if "case" in line and ".local/bin" in line:
            guard_line = line.strip()
            break

    assert guard_line, "guard line not found in extracted payload"

    # Generate the Python emitter's guard for comparison
    python_guard = path_export_guard(Path("/a/bin"))

    # Structural assertions
    assert guard_line.startswith("case"), "shell guard does not start with 'case'"
    assert python_guard.startswith("case"), "Python guard does not start with 'case'"

    assert "${PATH-}" in guard_line, "shell guard does not read PATH via ${PATH-}"
    assert "${PATH-}" in python_guard, "Python guard does not read PATH via ${PATH-}"

    assert "${PATH:+:" in guard_line, "shell guard does not use conditional expansion"
    assert "${PATH:+:" in python_guard, "Python guard does not use conditional expansion"

    # Both should have the case pattern match for the directory
    assert "in *" in guard_line, "shell guard missing case pattern"
    assert "in *" in python_guard, "Python guard missing case pattern"


# ============================================================================
# TASK 2: Shell-script accumulating PATH scan and classification
# ============================================================================


class Hit:
    """One line in a shell script matching the accumulating PATH pattern."""

    def __init__(self, file_rel: Path, line_num: int, line_text: str) -> None:
        self.file = file_rel
        self.line_num = line_num
        self.text = line_text

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hit):
            return NotImplemented
        return self.file == other.file and self.line_num == other.line_num

    def __hash__(self) -> int:
        return hash((self.file, self.line_num))

    def __repr__(self) -> str:
        return f"Hit({self.file}:{self.line_num})"


def _accumulating_shell_hits(files: list[Path]) -> list[Hit]:
    """Scan shell files for accumulating PATH prepends.

    For each file, walk its lines and report any line matching: an assignment to
    PATH (optional 'export' prefix, negative lookbehind on a word character so
    MANPATH= and MYPATH= are not hits) whose value later references the PATH
    variable through any expansion form covered by plan 15.8-03's Python needle:
    bare $PATH plus every braced operator ({-, :-, +, :+, =, :=, ?, :?, #, ##, %, %%}).

    Skip a line whose stripped form starts with '#' (commented out) or 'case'
    (this mirrors installer/rcclean.py:16's _PATH_EXPORT anchor: the guard's own
    value DOES reference a PATH expansion, so we key on the ASSIGNMENT being
    unguarded rather than on the mere presence of the two halves).

    Return a list of Hit objects, each carrying the file's path relative to
    repo root, the 1-based line number, and the line's text.

    This is a line scan, not a parse: a shell script has no AST this repo can
    use, and the split-construction case that justified parsing on the Python
    side does not arise in four small scripts.
    """
    # Pattern: optional 'export', then PATH not preceded by a word character,
    # then assignment, then value containing a PATH expansion.
    # Expansion forms: $PATH, ${PATH-}, ${PATH:-}, ${PATH+}, ${PATH:+},
    # ${PATH=}, ${PATH:=}, ${PATH?}, ${PATH:?}, ${PATH#...}, ${PATH##...},
    # ${PATH%...}, ${PATH%%...}
    expansion_pattern = r"\$(?:PATH|\{PATH(?:[-:+]|:[-+]|=|:=|\?|:\?|#|##|%|%%)[^}]*\})"
    # Allow leading whitespace, then optional 'export', then PATH= (not preceded by word char)
    pattern = re.compile(
        rf"^\s*(?!.*(?:[A-Z_]+PATH|[A-Z_]*PATH[A-Z_]+)=)(?:export\s+)?PATH=.*{expansion_pattern}"
    )

    hits: list[Hit] = []

    for filepath in files:
        if not filepath.exists():
            continue

        try:
            lines = filepath.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip comments and case-guarded lines
            if stripped.startswith("#") or stripped.startswith("case"):
                continue

            if pattern.search(line):
                # Path is relative to repo root
                try:
                    rel_path = filepath.relative_to(ROOT)
                except ValueError:
                    rel_path = filepath

                hits.append(Hit(rel_path, line_idx, line))

    return hits


_EXCLUDED_PATH_PARTS = frozenset({".venv", ".git", ".worktrees", ".superpowers"})


def _is_excluded(path: Path) -> bool:
    """Whether any path component is a directory the repo scan must skip.

    Extracted so the exclusion rule can be exercised directly. It used to be an
    inline set comprehension inside the scan, which left its own test with
    nothing to call -- that test built `.venv_test`-style names matching no
    pattern, never invoked the rule, and asserted `len(hits) >= 1`, which held
    whatever the rule did.
    """
    return any(part in _EXCLUDED_PATH_PARTS for part in path.parts)


def test_no_unclassified_accumulating_path_line_in_any_shell_script() -> None:
    """Scan every shell script in the repo for accumulating PATH prepends.

    File set: install.sh plus every .sh under scripts/ recursively, sorted,
    resolved from repo root. Exclude any path containing .venv, .git,
    .worktrees or .superpowers as a component. (.worktrees holds checkouts of
    OTHER branches of this same repository, so a hit there is another branch's
    code, not this tree's.)

    CLASSIFIED tuple: the ONLY accepted hits, each (file, line, reason) where
    reason states the property rather than restating the line. Equality in both
    directions: an unclassified hit fails as a new violation, and a classified
    location that no longer produces a hit ALSO fails, forcing the table to be
    updated instead of decaying into a permanent exemption.
    """
    # Build the file list
    files_to_scan: list[Path] = []

    # Add install.sh
    if INSTALL_SCRIPT.exists():
        files_to_scan.append(INSTALL_SCRIPT)

    # Add all .sh under scripts/
    if SCRIPTS_DIR.exists():
        for sh_file in sorted(SCRIPTS_DIR.glob("**/*.sh")):
            if _is_excluded(sh_file):
                continue
            files_to_scan.append(sh_file)

    files_to_scan.sort()

    # Run the scan
    hits = _accumulating_shell_hits(files_to_scan)

    # Classified locations: (file relative to repo, 1-based line, reason)
    CLASSIFIED = {
        (
            Path("install.sh"),
            60,
            "sets PATH for the remainder of its own bootstrap process and is never sourced",
        ),
        (
            Path("scripts/container-e2e-verify.sh"),
            202,
            "one-shot command prefix inside su -c; executes once in a fresh "
            "process and is never sourced",
        ),
        (
            Path("scripts/container-e2e-verify.sh"),
            319,
            "one-shot command prefix inside su -c; executes once in a fresh "
            "process and is never sourced",
        ),
        (
            Path("scripts/container-e2e-verify.sh"),
            342,
            "one-shot command prefix inside su -c; executes once in a fresh "
            "process and is never sourced",
        ),
    }

    # Build hit set for comparison (ignore reason, just file:line)
    hit_set = {(hit.file, hit.line_num) for hit in hits}
    classified_set = {(filepath, line_num) for filepath, line_num, _ in CLASSIFIED}

    # Find mismatches
    unclassified_hits = hit_set - classified_set
    stale_classifications = classified_set - hit_set

    # Build detailed error message
    error_lines: list[str] = []
    if unclassified_hits:
        error_lines.append("NEW VIOLATIONS (unclassified hits):")
        for hit in hits:
            if (hit.file, hit.line_num) in unclassified_hits:
                error_lines.append(f"  {hit.file}:{hit.line_num}: {hit.text.strip()}")

    if stale_classifications:
        error_lines.append("STALE CLASSIFICATIONS (no longer produce hits):")
        for filepath, line_num, reason in sorted(CLASSIFIED):
            if (filepath, line_num) in stale_classifications:
                error_lines.append(f"  {filepath}:{line_num}: {reason}")

    assert not error_lines, "\n".join(error_lines)


@pytest.mark.parametrize("shell_path", [_get_bash(), _get_zsh(), _get_sh()])
def test_shell_scan_reports_a_plain_export_prepend(tmp_path: Path, shell_path: str | None) -> None:
    """Shell scan reports the classic export PATH="$HOME/bin:$PATH" line."""
    if shell_path is None:
        pytest.skip("shell not on PATH")

    test_script = tmp_path / "test.sh"
    test_script.write_text('export PATH="$HOME/bin:$PATH"\n')

    hits = _accumulating_shell_hits([test_script])
    assert len(hits) == 1
    assert hits[0].line_num == 1


def test_shell_scan_reports_every_path_expansion_spelling(tmp_path: Path) -> None:
    """Shell scan reports every expansion form from plan 15.8-03's needle."""
    test_script = tmp_path / "test.sh"

    expansions = [
        ('export PATH="$PATH:/new"', True),  # bare $PATH
        ('export PATH="${PATH-}:/new"', True),  # ${PATH-}
        ('export PATH="${PATH:-}:/new"', True),  # ${PATH:-}
        ('export PATH="${PATH+}:/new"', True),  # ${PATH+}
        ('export PATH="${PATH:+}:/new"', True),  # ${PATH:+}
        ('export PATH="${PATH=}:/new"', True),  # ${PATH=}
        ('export PATH="${PATH:=}:/new"', True),  # ${PATH:=}
        ('export PATH="${PATH?}:/new"', True),  # ${PATH?}
        ('export PATH="${PATH:?}:/new"', True),  # ${PATH:?}
        ('export PATH="${PATH#x}:/new"', True),  # ${PATH#...}
        ('export PATH="${PATH##x}:/new"', True),  # ${PATH##...}
        ('export PATH="${PATH%x}:/new"', True),  # ${PATH%...}
        ('export PATH="${PATH%%x}:/new"', True),  # ${PATH%%...}
        ('export MANPATH="$MANPATH:/new"', False),  # MANPATH, not PATH
        ('export MYPATH="$PATH:/new"', False),  # MYPATH assignment (not PATH=)
        ('export PATHOLOGICAL="$PATH"', False),  # longer name ending in PATH
    ]

    lines = [line for line, _ in expansions]
    test_script.write_text("\n".join(lines) + "\n")

    hits = _accumulating_shell_hits([test_script])
    hit_lines = {hit.line_num for hit in hits}

    for line_num, (line, should_hit) in enumerate(expansions, start=1):
        if should_hit:
            assert line_num in hit_lines, f"expected hit on line {line_num}: {line}"
        else:
            assert line_num not in hit_lines, f"unexpected hit on line {line_num}: {line}"


def test_shell_scan_does_not_report_the_guarded_form(tmp_path: Path) -> None:
    """Shell scan does not report the guard line Task 1 put into container script.

    The guard's own value DOES reference a PATH expansion, so the scan keys on
    the ASSIGNMENT being unguarded rather than on the mere presence of the two
    halves. This mirrors installer/rcclean.py:16's _PATH_EXPORT anchor.
    """
    test_script = tmp_path / "test.sh"

    # The guard line: starts with 'case', so should NOT be reported
    guard_line = (
        'case ":${PATH-}:" in *":$HOME/.local/bin:"*) ;; *) '
        'export PATH="$HOME/.local/bin${PATH:+:$PATH}";;esac'
    )
    test_script.write_text(guard_line + "\n")

    hits = _accumulating_shell_hits([test_script])
    assert len(hits) == 0, "scan should not report case-guarded lines"


def test_shell_scan_does_not_report_a_commented_line(tmp_path: Path) -> None:
    """Shell scan does not report a commented-out export PATH line."""
    test_script = tmp_path / "test.sh"
    test_script.write_text('# export PATH="$HOME/bin:$PATH"\n')

    hits = _accumulating_shell_hits([test_script])
    assert len(hits) == 0, "scan should not report commented lines"


def test_shell_scan_excludes_venv_git_worktrees_superpowers(tmp_path: Path) -> None:
    """Exercise the exclusion rule itself, with the names it actually matches.

    Both directions are asserted: every excluded directory name is excluded at
    any depth, and a path that merely RESEMBLES one is not. The previous version
    of this test used `.venv_test`-style names, which match no pattern, never
    called the rule, and ended on an assertion that held regardless.
    """
    for name in _EXCLUDED_PATH_PARTS:
        assert _is_excluded(tmp_path / name / "test.sh")
        assert _is_excluded(tmp_path / name / "nested" / "deep" / "test.sh")

    for name in (".venv_test", "venv", "git", "superpowers", "included"):
        assert not _is_excluded(tmp_path / name / "test.sh")
