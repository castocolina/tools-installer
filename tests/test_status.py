from collections.abc import Sequence
from pathlib import Path

import pytest

from installer.model import Method, Tool, load_tools
from installer.status import (
    MACOS_STUBS,
    dangling_shim,
    is_default_shell,
    is_installed,
    macos_stub_reason,
)

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _tool(cmd: str) -> Tool:
    return Tool(
        id="t",
        name="t",
        category="c",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": "t"}),),
    )


def test_is_installed_true_when_cmd_on_path(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/jq" if cmd == "jq" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    assert is_installed(_tool("jq")) is True


def test_is_installed_false_when_cmd_absent(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    assert is_installed(_tool("jq")) is False


def _app_tool(app: str = "Demo.app") -> Tool:
    return Tool(
        id="d",
        name="d",
        category="editor",
        cmd="demo",
        methods=(Method(kind="app", params={"url": "https://example.test/a.zip", "app": app}),),
    )


def test_app_bundle_present_counts_as_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    (tmp_path / "Demo.app").mkdir()
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is True


def test_app_bundle_as_plain_file_is_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    (tmp_path / "Demo.app").touch()  # a file, not a bundle dir
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is False


def test_cask_app_bundle_present_counts_as_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    (tmp_path / "JetBrains Toolbox.app").mkdir()
    tool = Tool(
        id="jetbrains-toolbox",
        name="JetBrains Toolbox",
        category="editor",
        cmd="jetbrains-toolbox",
        methods=(
            Method(
                kind="cask",
                params={"cask": "jetbrains-toolbox", "app": "JetBrains Toolbox.app"},
            ),
        ),
    )
    assert is_installed(tool, app_roots=(tmp_path,)) is True


def test_app_tool_without_bundle_or_cmd_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is False


def test_app_method_without_app_param_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    tool = Tool(
        id="d",
        name="d",
        category="editor",
        cmd="demo",
        methods=(Method(kind="app", params={"url": "https://example.test/a.zip"}),),
    )
    assert is_installed(tool, app_roots=(tmp_path,)) is False


def test_default_app_roots_include_user_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "Applications" / "Tools Installer Probe.app").mkdir(parents=True)
    assert is_installed(_app_tool("Tools Installer Probe.app")) is True


def test_cmd_on_path_still_wins_for_app_tools(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_found(cmd: str) -> str | None:
        return "/usr/local/bin/demo"

    monkeypatch.setattr(status.shutil, "which", which_found)
    assert is_installed(_app_tool()) is True


def _detect_path_tool(detect_path: str) -> Tool:
    return Tool(
        id="sdkman",
        name="SDKMAN",
        category="runtime",
        cmd="sdkman-init.sh",
        methods=(
            Method(
                kind="script",
                params={"url": "https://example.test/i.sh", "detect_path": detect_path},
            ),
        ),
    )


def test_detect_path_present_counts_as_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    marker = tmp_path / "sdkman-init.sh"
    marker.touch()  # a non-executable file — `which` could never find this
    assert is_installed(_detect_path_tool(str(marker))) is True


def test_detect_path_absent_is_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    missing = tmp_path / "sdkman-init.sh"
    assert is_installed(_detect_path_tool(str(missing))) is False


def _uv_tool_tool() -> Tool:
    return Tool(
        id="graphify",
        name="Graphify",
        category="dev",
        cmd="graphify",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "graphifyy"}),),
    )


def test_uv_tool_status_is_detected_through_its_cli_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def which_graphify_only(cmd: str) -> str | None:
        return "/home/user/.local/bin/graphify" if cmd == "graphify" else None

    monkeypatch.setattr(status.shutil, "which", which_graphify_only)
    assert is_installed(_uv_tool_tool()) is True

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    assert is_installed(_uv_tool_tool()) is False


def test_gnu_bash_status_is_not_fooled_by_macos_system_bash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/bin/bash" if cmd == "bash" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    gnu_bash = next(tool for tool in load_tools(REGISTRY) if tool.id == "gnu-bash")
    swapped = tuple(
        Method(
            kind=method.kind,
            params={
                **method.params,
                "detect_path": str(tmp_path / Path(str(method.params["detect_path"])).name),
            },
            os=method.os,
            arch=method.arch,
        )
        for method in gnu_bash.methods
    )
    probed = Tool(
        id=gnu_bash.id,
        name=gnu_bash.name,
        category=gnu_bash.category,
        cmd=gnu_bash.cmd,
        methods=swapped,
        priority=gnu_bash.priority,
        audience=gnu_bash.audience,
        tier=gnu_bash.tier,
        desc=gnu_bash.desc,
    )
    assert is_installed(probed) is False


def _shell_tool(cmd: str) -> Tool:
    return Tool(
        id=cmd,
        name=cmd,
        category="shell",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": cmd}),),
    )


def test_is_default_shell_none_for_a_non_shell_category_tool() -> None:
    assert is_default_shell(_tool("zsh"), env={"SHELL": "/bin/zsh"}) is None


def test_is_default_shell_none_when_shell_env_is_unset() -> None:
    assert is_default_shell(_shell_tool("zsh"), env={}) is None


def test_is_default_shell_true_when_shell_env_basename_matches_cmd() -> None:
    assert is_default_shell(_shell_tool("zsh"), env={"SHELL": "/usr/bin/zsh"}) is True


def test_is_default_shell_false_when_shell_env_basename_differs() -> None:
    assert is_default_shell(_shell_tool("zsh"), env={"SHELL": "/bin/bash"}) is False


def _which_none(cmd: str) -> str | None:
    return None


def _bin_dir_tool(bin_dir: str, cmd: str = "spring") -> Tool:
    """An SDKMAN candidate: the binary lands in a declared `bin_dir` that only
    reaches PATH through a shell rc file, so `which` cannot see it until the
    user opens a brand-new shell."""
    return Tool(
        id="springbootcli",
        name="Spring Boot CLI",
        category="runtime",
        cmd=cmd,
        methods=(Method(kind="sdkman", params={"candidate": "springboot", "bin_dir": bin_dir}),),
    )


def test_declared_bin_dir_holding_the_command_counts_as_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live defect: an SDKMAN candidate installed into its declared bin_dir
    read as "not installed" in every shell started before the install, because
    only PATH was consulted. The tool is on disk; that is the question asked."""
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", _which_none)
    bin_dir = tmp_path / "candidates" / "springboot" / "current" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "spring").touch()
    assert is_installed(_bin_dir_tool(str(bin_dir))) is True


def test_empty_declared_bin_dir_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leftover directory an uninstall emptied must not read as installed —
    the command file is the marker, never the directory."""
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", _which_none)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    assert is_installed(_bin_dir_tool(str(bin_dir))) is False


def test_dangling_current_symlink_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SDKMAN's `current` is a symlink to the active version. When the version
    it points at is removed, the symlink survives and the path still "exists"
    by lstat — following it is what makes this answer honest."""
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", _which_none)
    versioned = tmp_path / "4.1.0" / "bin"
    versioned.mkdir(parents=True)
    (versioned / "spring").touch()
    current = tmp_path / "current"
    current.symlink_to(tmp_path / "4.1.0")
    tool = _bin_dir_tool(str(current / "bin"))
    assert is_installed(tool) is True

    import shutil as real_shutil

    real_shutil.rmtree(tmp_path / "4.1.0")
    assert is_installed(tool) is False


def test_bin_dir_holding_a_different_command_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A populated bin_dir is not a blanket yes: it must hold THIS tool's cmd.
    Pins that the check never degrades to `any(bin_dir.iterdir())`."""
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", _which_none)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "unrelated").touch()
    assert is_installed(_bin_dir_tool(str(bin_dir))) is False


def test_bin_dir_is_expanded_from_a_tilde_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every bin_dir in registry.toml is written `~/.sdkman/...`; an unexpanded
    `~` would make this whole check silently dead."""
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", _which_none)
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".sdkman" / "candidates" / "springboot" / "current" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "spring").touch()
    tool = _bin_dir_tool("~/.sdkman/candidates/springboot/current/bin")
    assert is_installed(tool) is True


def _mmdc() -> Tool:
    return Tool(
        id="mmdc",
        name="mmdc",
        category="diagram",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )


def test_dangling_shim_true_when_pnpm_package_is_gone(tmp_path: Path) -> None:
    pnpm = tmp_path / "pnpm"
    shim = pnpm / "mmdc"
    pnpm.mkdir()
    shim.touch()
    assert (
        dangling_shim(
            _mmdc(),
            active_path=shim,
            pnpm_dirs=(pnpm,),
            pnpm_globals=frozenset(),
        )
        is True
    )


def test_dangling_shim_false_when_package_is_listed(tmp_path: Path) -> None:
    pnpm = tmp_path / "pnpm"
    shim = pnpm / "mmdc"
    pnpm.mkdir()
    shim.touch()
    assert (
        dangling_shim(
            _mmdc(),
            active_path=shim,
            pnpm_dirs=(pnpm,),
            pnpm_globals=frozenset({"@mermaid-js/mermaid-cli"}),
        )
        is False
    )


def test_dangling_shim_false_when_inventory_is_unreadable(tmp_path: Path) -> None:
    pnpm = tmp_path / "pnpm"
    shim = pnpm / "mmdc"
    pnpm.mkdir()
    shim.touch()
    assert dangling_shim(_mmdc(), active_path=shim, pnpm_dirs=(pnpm,), pnpm_globals=None) is False


def test_dangling_shim_false_when_binary_is_outside_pnpm(tmp_path: Path) -> None:
    pnpm = tmp_path / "pnpm"
    pnpm.mkdir()
    assert (
        dangling_shim(
            _mmdc(),
            active_path=Path("/usr/bin/mmdc"),
            pnpm_dirs=(pnpm,),
            pnpm_globals=frozenset(),
        )
        is False
    )


def test_dangling_shim_false_when_binary_is_absent(tmp_path: Path) -> None:
    assert (
        dangling_shim(
            _mmdc(),
            active_path=None,
            pnpm_dirs=(tmp_path / "pnpm",),
            pnpm_globals=frozenset(),
        )
        is False
    )


def _java_tool(*, bin_dir: str | None = None) -> Tool:
    params: dict[str, object] = {"candidate": "java"}
    if bin_dir is not None:
        params["bin_dir"] = bin_dir
    return Tool(
        id="java",
        name="java",
        category="system",
        cmd="java",
        methods=(Method(kind="sdkman", params=params),),
    )


def test_java_stub_alone_is_not_installed_with_a_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/java" if cmd == "java" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)

    def probe_fail(argv: Sequence[str]) -> bool:
        return False

    tool = _java_tool()
    assert is_installed(tool, darwin=True, probe=probe_fail) is False
    reason = macos_stub_reason(tool, darwin=True, probe=probe_fail)
    assert reason is not None
    assert "/usr/bin/java" in reason
    assert "/usr/libexec/java_home" in reason


def test_java_stub_with_a_real_jdk_is_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/java" if cmd == "java" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)

    def probe_ok(argv: Sequence[str]) -> bool:
        return True

    tool = _java_tool()
    assert is_installed(tool, darwin=True, probe=probe_ok) is True
    assert macos_stub_reason(tool, darwin=True, probe=probe_ok) is None


def test_stub_falls_through_to_a_declared_bin_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/java" if cmd == "java" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)

    def probe_fail(argv: Sequence[str]) -> bool:
        return False

    bin_dir = tmp_path / "sdkman" / "candidates" / "java" / "current" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java").touch()
    tool = _java_tool(bin_dir=str(bin_dir))
    assert is_installed(tool, darwin=True, probe=probe_fail) is True


def _git_tool() -> Tool:
    return Tool(
        id="git",
        name="git",
        category="system",
        cmd="git",
        methods=(Method(kind="brew", params={"formula": "git"}),),
    )


def test_git_stub_without_clt_is_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/git" if cmd == "git" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    received: list[tuple[str, ...]] = []

    def probe_fail(argv: Sequence[str]) -> bool:
        received.append(tuple(argv))
        return False

    tool = _git_tool()
    assert is_installed(tool, darwin=True, probe=probe_fail) is False
    received.clear()
    reason = macos_stub_reason(tool, darwin=True, probe=probe_fail)
    assert reason is not None
    assert "/usr/bin/xcode-select -p" in reason.replace("  ", " ")
    assert received == [("/usr/bin/xcode-select", "-p")]


def test_every_stub_probe_is_an_absolute_path() -> None:
    for argv in MACOS_STUBS.values():
        assert argv[0].startswith("/")


def test_git_stub_with_clt_is_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/git" if cmd == "git" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)

    def probe_ok(argv: Sequence[str]) -> bool:
        return True

    assert is_installed(_git_tool(), darwin=True, probe=probe_ok) is True


def test_stub_table_is_ignored_off_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/git" if cmd == "git" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    calls: list[tuple[str, ...]] = []

    def recording_probe(argv: Sequence[str]) -> bool:
        calls.append(tuple(argv))
        return False

    assert is_installed(_git_tool(), darwin=False, probe=recording_probe) is True
    assert calls == []


def test_non_stub_path_on_macos_runs_no_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/opt/homebrew/bin/git" if cmd == "git" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    calls: list[tuple[str, ...]] = []

    def recording_probe(argv: Sequence[str]) -> bool:
        calls.append(tuple(argv))
        return False

    assert is_installed(_git_tool(), darwin=True, probe=recording_probe) is True
    assert calls == []


# --- 19-02: implicit ~/.local/bin presence, injected which and bin dir ---


def _github_tool(bin_dir: str | None = None, cmd: str = "yq", raw: bool = False) -> Tool:
    params: dict[str, object] = {
        "repo": "a/yq",
        "asset": "yq.tar.gz",
        "member": "yq_linux_amd64",
        "bin_name": cmd,
    }
    if bin_dir is not None:
        params["bin_dir"] = bin_dir
    if raw:
        params["raw"] = True
    return Tool(
        id="yq",
        name="yq",
        category="dev",
        cmd=cmd,
        methods=(Method(kind="github_release", params=params),),
    )


def test_implicit_local_bin_file_counts_as_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raw binary the installer placed in its implicit ~/.local/bin reads as
    present even when that dir is not on PATH (SPEC AC12)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    (local_bin / "yq").write_text("binary")
    assert is_installed(_github_tool(raw=True), which=_which_none) is True


def test_implicit_local_bin_link_into_opt_counts_as_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt = tmp_path / ".local" / "opt" / "rg"
    opt.mkdir(parents=True)
    (opt / "rg").write_text("binary")
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    (local_bin / "rg").symlink_to(opt / "rg")
    archive = Tool(
        id="rg",
        name="rg",
        category="dev",
        cmd="rg",
        methods=(
            Method(
                kind="github_release",
                params={"repo": "a/rg", "asset": "rg.tar.gz", "member": "rg"},
            ),
        ),
    )
    assert is_installed(archive, which=_which_none) is True


def test_dangling_implicit_link_is_not_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    (local_bin / "yq").symlink_to(tmp_path / "gone")
    assert is_installed(_github_tool(raw=True), which=_which_none) is False


def test_declared_bin_dir_methods_keep_their_own_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A method WITH a bin_dir is answered by the existing declared-bin_dir
    loop, never by the implicit ~/.local/bin check."""
    import installer.status as status

    monkeypatch.setattr(status.shutil, "which", _which_none)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    declared = tmp_path / "sdkman" / "bin"
    declared.mkdir(parents=True)
    implicit = tmp_path / ".local" / "bin"
    implicit.mkdir(parents=True)
    (implicit / "spring").write_text("binary")
    assert is_installed(_bin_dir_tool(str(declared))) is False
    (declared / "spring").write_text("binary")
    assert is_installed(_bin_dir_tool(str(declared))) is True


def test_is_installed_uses_the_injected_which(monkeypatch: pytest.MonkeyPatch) -> None:
    """The injected `which` answers presence without touching the real PATH,
    and macos_stub_reason reads the same lookup."""
    monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent-home"))
    assert is_installed(_tool("jq"), which=lambda _cmd: "/usr/bin/jq") is True
    reason = macos_stub_reason(
        _tool("java"),
        darwin=True,
        probe=lambda _argv: False,
        which=lambda _cmd: "/usr/bin/java",
    )
    assert reason is not None and "stub" in reason


def test_default_which_is_resolved_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """review H2: no `= shutil.which` default is bound at definition time —
    patching `status.shutil.which` AFTER the import must still be what the
    functions read."""
    import installer.status as status

    seen: list[str] = []

    def fake(cmd: str) -> str | None:
        seen.append(cmd)
        return None

    monkeypatch.setattr(status.shutil, "which", fake)
    monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent-home"))
    assert is_installed(_tool("jq")) is False
    assert macos_stub_reason(_tool("jq"), darwin=True, probe=lambda _argv: True) is None
    assert seen == ["jq", "jq"]


def test_implicit_presence_reads_the_given_default_bin_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """checker W2: the implicit check reads the bin dir the caller passes (the
    service passes its managed bin dir); the given dir REPLACES the default,
    it is not added to it."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "yq").write_text("binary")
    assert is_installed(_github_tool(raw=True), which=_which_none, default_bin_dir=managed) is True
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    (tmp_path / ".local" / "bin" / "yq").write_text("binary")
    other = tmp_path / "other"
    other.mkdir()
    assert is_installed(_github_tool(raw=True), which=_which_none, default_bin_dir=other) is False
