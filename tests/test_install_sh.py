"""Black-box tests for the install.sh bootstrap.

install.sh runs before the Python package exists, so it can't be tested
in-process. We exercise it as a subprocess with a stubbed PATH: each external
command (uname, git, curl, uv) is a tiny shell stub that logs its invocation to
$TI_LOG, so tests assert on *what the script called* -- never on real network,
git, or uv. This mirrors the injected-seam pattern the Python code uses.

Functions are tested in isolation by sourcing install.sh with TI_SOURCED set
(which suppresses the bottom-of-file `main "$@"` call) and invoking the target
function directly.
"""

import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "install.sh"


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@dataclass
class Harness:
    fakebin: Path
    home: Path
    log: Path
    repo_dir: Path

    def stub(self, name: str, body: str) -> None:
        path = self.fakebin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        _make_executable(path)

    def _env(self, extra: dict[str, str]) -> dict[str, str]:
        env: dict[str, str] = {
            "PATH": f"{self.fakebin}:/usr/bin:/bin",
            "HOME": str(self.home),
            "TI_LOG": str(self.log),
            "TI_DIR": str(self.repo_dir),
        }
        env.update(extra)
        return env

    def source(self, snippet: str, **extra: str) -> "subprocess.CompletedProcess[str]":
        env = self._env(extra)
        env["TI_SOURCED"] = "1"
        return subprocess.run(
            ["/bin/sh", "-c", f'. "{INSTALL_SH}"; {snippet}'],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def run(self, *args: str, **extra: str) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            ["/bin/sh", str(INSTALL_SH), *args],
            env=self._env(extra),
            capture_output=True,
            text=True,
            check=False,
        )

    def log_text(self) -> str:
        return self.log.read_text() if self.log.exists() else ""


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    h = Harness(
        fakebin=fakebin,
        home=home,
        log=tmp_path / "calls.log",
        repo_dir=tmp_path / "repo",
    )
    h.stub(
        "uname",
        'printf "uname %s\\n" "$*" >> "$TI_LOG"\n'
        'case "${1:-}" in\n'
        '  -s) printf "%s\\n" "${TI_OS:-Linux}" ;;\n'
        '  -m) printf "%s\\n" "${TI_ARCH:-x86_64}" ;;\n'
        '  *) printf "Linux\\n" ;;\n'
        "esac",
    )
    h.stub(
        "git",
        'printf "git %s\\n" "$*" >> "$TI_LOG"\n'
        'case "${1:-}" in\n'
        '  clone) mkdir -p "$TI_DIR" ;;\n'
        "esac",
    )
    return h


def test_detect_os_maps_darwin_to_macos(harness: Harness) -> None:
    result = harness.source("detect_os", TI_OS="Darwin")
    assert result.returncode == 0
    assert result.stdout.strip() == "macos"


def test_detect_os_maps_linux(harness: Harness) -> None:
    result = harness.source("detect_os", TI_OS="Linux")
    assert result.returncode == 0
    assert result.stdout.strip() == "linux"


def test_detect_os_rejects_unsupported(harness: Harness) -> None:
    result = harness.source("detect_os", TI_OS="MINGW64_NT")
    assert result.returncode != 0
    assert "unsupported OS" in result.stderr


def test_ensure_uv_skips_when_already_present(harness: Harness) -> None:
    harness.stub("uv", 'printf "uv %s\\n" "$*" >> "$TI_LOG"')
    result = harness.source("ensure_uv")
    assert result.returncode == 0
    assert "curl" not in harness.log_text()  # no install attempt


def test_ensure_uv_installs_via_curl_when_missing(harness: Harness) -> None:
    # uv is absent from PATH; the curl stub simulates the official installer by
    # dropping a uv stub into the fake bin (and emits nothing to the `| sh` pipe).
    harness.stub(
        "curl",
        'printf "curl %s\\n" "$*" >> "$TI_LOG"\n'
        f"cat > \"{harness.fakebin}/uv\" <<'INNER'\n"
        "#!/bin/sh\n"
        'printf "uv %s\\n" "$*" >> "$TI_LOG"\n'
        "INNER\n"
        f'chmod +x "{harness.fakebin}/uv"',
    )
    result = harness.source("ensure_uv")
    assert result.returncode == 0
    log = harness.log_text()
    assert "curl" in log
    assert "astral.sh" in log
    assert (harness.fakebin / "uv").exists()


def test_fetch_repo_clones_when_absent(harness: Harness) -> None:
    result = harness.source("fetch_repo")
    assert result.returncode == 0
    log = harness.log_text()
    assert "clone" in log
    assert str(harness.repo_dir) in log
    assert harness.repo_dir.exists()  # proves $TI_DIR was passed to git clone


def test_fetch_repo_pulls_when_present(harness: Harness) -> None:
    (harness.repo_dir / ".git").mkdir(parents=True)
    result = harness.source("fetch_repo")
    assert result.returncode == 0
    log = harness.log_text()
    assert "pull" in log
    assert "git clone" not in log


def test_fetch_repo_requires_git(harness: Harness) -> None:
    # Drop git and restrict PATH to the fake bin so no system git is found.
    (harness.fakebin / "git").unlink()
    result = harness.source("fetch_repo", PATH=str(harness.fakebin))
    assert result.returncode != 0
    assert "git is required" in result.stderr
