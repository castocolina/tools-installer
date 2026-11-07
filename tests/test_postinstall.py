import shutil
from itertools import combinations
from pathlib import Path

import pytest

import installer.engine as engine_mod
import installer.postinstall as pi
from installer import receipts, skill_lifecycle
from installer.engine import install_tool
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.run import CommandError

_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"

_CODEGRAPH = "codegraph-mcp-register"
# Harness ids: the keys of every hook target map. `cursor` is the Cursor harness;
# the catalog id `cursor-agent` is display-only (HOST_CATALOG_IDS).
_HARNESSES = ("claude", "codex", "opencode", "cursor")
_ALL_SUBSETS: list[tuple[str, ...]] = [
    subset for size in range(len(_HARNESSES) + 1) for subset in combinations(_HARNESSES, size)
]
# Mirrors installer.postinstall's codegraph target map, kept here so the test
# does not reach into private module state.
_EXPECTED_TARGET_FOR = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor",
}
_GITHUB = Method(kind="github_release", params={})
_BREW = Method(kind="brew", params={"formula": "codegraph"})


def _codegraph_tool() -> Tool:
    return Tool(
        id="codegraph",
        name="codegraph",
        category="ai",
        cmd="codegraph",
        methods=(_GITHUB,),
        tier="ai",
        postinstall=_CODEGRAPH,
    )


def _argv(targets: str) -> list[str]:
    return [
        str(Path.home() / ".local" / "bin" / "codegraph"),
        "install",
        "--target",
        targets,
        "--location",
        "global",
        "--yes",
        "--no-permissions",
    ]


def _write_receipt(hooks: dict[str, tuple[str, ...]] | None = None) -> None:
    receipts.write(
        receipts.Receipt(
            tool="codegraph",
            at="2026-11-07T00:00:00+00:00",
            method=receipts.ReceiptMethod(kind="github_release", key="test"),
            package=None,
            artifacts=(),
            smoke=None,
            hooks=hooks or {},
        )
    )


def test_codegraph_hook_composes_csv_from_present_hosts_only() -> None:
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude", "cursor"})
    )
    assert outcome == (("claude", "cursor"), None)
    assert calls == [_argv("claude,cursor")]


def test_codegraph_hook_noops_when_no_host_present() -> None:
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset())
    assert outcome == ((), None)
    assert calls == []


def test_codegraph_hook_invokes_the_resolved_absolute_binary_path_not_a_bare_name() -> None:
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude"}))
    assert calls[0][0] == str(Path.home() / ".local" / "bin" / "codegraph")

    calls.clear()
    custom_method = Method(kind="github_release", params={"bin_dir": "/custom/dir"})
    pi.run_postinstall(
        _CODEGRAPH, custom_method, lambda cmd: calls.append(cmd), frozenset({"claude"})
    )
    assert calls[0][0] == "/custom/dir/codegraph"


@pytest.mark.parametrize("bad_bin_dir", [True, 123])
def test_codegraph_hook_ignores_a_non_string_bin_dir_param(bad_bin_dir: object) -> None:
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={"bin_dir": bad_bin_dir})
    pi.run_postinstall(_CODEGRAPH, method, lambda cmd: calls.append(cmd), frozenset({"claude"}))
    assert calls[0][0] == str(Path.home() / ".local" / "bin" / "codegraph")


def _which_found(name: str) -> str | None:
    return f"/found/{name}"


def _which_missing(_name: str) -> str | None:
    return None


def test_codegraph_hook_brew_prefers_the_binary_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi.shutil, "which", _which_found)
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _BREW, lambda cmd: calls.append(cmd), frozenset({"claude"}))
    assert calls[0][0] == "/found/codegraph"


def test_codegraph_hook_brew_finds_a_well_known_prefix_by_disk_presence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pi.shutil, "which", _which_missing)
    brew_dir = tmp_path / "brew"
    brew_dir.mkdir()
    (brew_dir / "codegraph").write_text("", encoding="utf-8")
    monkeypatch.setattr(pi, "BREW_BIN_DIRS", (tmp_path / "missing", brew_dir))
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _BREW, lambda cmd: calls.append(cmd), frozenset({"claude"}))
    assert calls[0][0] == str(brew_dir / "codegraph")


def test_codegraph_hook_brew_falls_back_to_the_userspace_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pi.shutil, "which", _which_missing)
    monkeypatch.setattr(pi, "BREW_BIN_DIRS", (tmp_path / "missing",))
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _BREW, lambda cmd: calls.append(cmd), frozenset({"claude"}))
    assert calls[0][0] == str(Path.home() / ".local" / "bin" / "codegraph")


def test_codegraph_hook_returns_a_warning_string_on_command_error_not_raise() -> None:
    def failing_runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    outcome = pi.run_postinstall(_CODEGRAPH, _GITHUB, failing_runner, frozenset({"claude"}))
    assert outcome[0] == ()
    assert outcome[1] is not None
    assert outcome[1].startswith("codegraph MCP registration failed")


def test_run_postinstall_unknown_name_is_a_noop() -> None:
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        "not-a-real-hook", _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude"})
    )
    assert outcome == ((), None)
    assert calls == []


@pytest.mark.parametrize("present_subset", _ALL_SUBSETS, ids=lambda s: ",".join(s) or "none")
def test_codegraph_hook_matches_expected_argv_for_every_host_presence_subset(
    present_subset: tuple[str, ...],
) -> None:
    """Every one of the 16 subsets of the four harnesses produces either the exact
    expected argv (never "auto") or a genuine no-op, never anything else."""
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset(present_subset)
    )
    if not present_subset:
        assert outcome == ((), None)
        assert calls == []
        return
    expected_csv = ",".join(
        _EXPECTED_TARGET_FOR[harness] for harness in _HARNESSES if harness in present_subset
    )
    assert outcome == (tuple(sorted(present_subset)), None)
    assert calls == [_argv(expected_csv)]
    assert "auto" not in calls[0]


def test_codegraph_hook_preserves_declared_host_order() -> None:
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset(_HARNESSES))
    assert calls[0][calls[0].index("--target") + 1] == "claude,codex,opencode,cursor"


def test_codegraph_hook_maps_cursor_alone_to_cursor() -> None:
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"cursor"})
    )
    assert outcome == (("cursor",), None)
    assert calls[0][calls[0].index("--target") + 1] == "cursor"


def test_codegraph_hook_always_passes_no_permissions() -> None:
    """codegraph's own --yes also enables a Claude auto-allow list and a
    UserPromptSubmit hook, not merely non-interactivity. --no-permissions keeps
    this call scoped to MCP registration only."""
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude"}))
    assert "--no-permissions" in calls[0]


def test_a_recorded_host_is_not_registered_again() -> None:
    _write_receipt({_CODEGRAPH: ("claude",)})
    calls: list[list[str]] = []
    outcome = pi.register_hooks(
        _codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude", "codex"})
    )
    assert outcome == (("codex",), None)
    assert calls == [_argv("codex")]
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks == {_CODEGRAPH: ("claude", "codex")}


def test_a_host_already_recorded_runs_nothing() -> None:
    _write_receipt({_CODEGRAPH: ("claude",)})
    calls: list[list[str]] = []
    outcome = pi.register_hooks(
        _codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude"})
    )
    assert outcome == ((), None)
    assert calls == []


@pytest.mark.parametrize("hosts", [frozenset[str](), frozenset({"pi"})], ids=["none", "pi-only"])
def test_no_present_supported_host_runs_nothing(hosts: frozenset[str]) -> None:
    _write_receipt()
    calls: list[list[str]] = []
    outcome = pi.register_hooks(_codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), hosts)
    assert outcome == ((), None)
    assert calls == []
    receipt = receipts.read("codegraph")
    assert receipt is not None
    # Known, none registered: the new-host sweep picks it up for the next host (CR-06).
    assert receipt.hooks == {"codegraph-mcp-register": ()}


def test_pi_is_in_no_target_map() -> None:
    for name, pair in pi.POSTINSTALL_HOOKS.items():
        if pair.targets is None:
            continue
        assert "pi" not in pair.targets, name
        assert set(pair.targets) <= set(skill_lifecycle.HARNESS_PRESENCE), name


def test_no_receipt_means_no_registration() -> None:
    calls: list[list[str]] = []
    outcome = pi.register_hooks(
        _codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), frozenset({"codex"})
    )
    assert outcome == ((), "hook not registered: no install receipt to record it in")
    assert calls == []


@pytest.mark.usefixtures("real_present_hosts")
def test_one_host_list_has_no_second_host_table(monkeypatch: pytest.MonkeyPatch) -> None:
    for source in Path(pi.__file__).parent.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "_AGENT_HOST_IDS" not in text, source.name
        assert "present_agent_hosts" not in text, source.name

    seen: list[tuple[Path, object]] = []

    def spy(home: Path, which: object) -> frozenset[str]:
        seen.append((home, which))
        return frozenset({"claude"})

    monkeypatch.setattr(pi, "present_harnesses", spy)
    assert pi.present_hosts() == frozenset({"claude"})
    assert seen == [(Path.home(), shutil.which)]


def test_installing_graphify_runs_no_host_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Phase 17 SAFE-02/D-03: installing graphify runs exactly
    `uv tool install graphifyy` and nothing else -- the registry entry declares
    no postinstall hook, so even with all four agent hosts present no
    `graphify <host> install` call is issued and the working directory stays
    empty (SPEC R2 acceptance)."""
    tools = {t.id: t for t in load_tools(_REGISTRY)}
    graphify = tools["graphify"]

    def none_installed(_tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine_mod, "is_installed", none_installed)
    monkeypatch.setattr(pi, "present_hosts", lambda: frozenset(_HARNESSES))
    home = tmp_path / "home"
    home.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(cwd)
    path_sandbox = tmp_path / "path-sandbox"
    path_sandbox.mkdir()
    monkeypatch.setenv("PATH", str(path_sandbox))
    calls: list[list[str]] = []
    outcome = install_tool(
        graphify,
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=calls.append,
    )
    assert outcome.status == "installed"
    assert calls == [["uv", "tool", "install", "graphifyy"]]
    assert list(cwd.iterdir()) == []


def _uninstall(targets: str) -> tuple[str, ...]:
    return (
        "/b/codegraph",
        "uninstall",
        "--target",
        targets,
        "--location",
        "global",
        "--yes",
        "--keep-cli",
    )


def _receipt_for(kind: str, key: str) -> receipts.Receipt:
    return receipts.Receipt(
        tool="demo",
        at="2026-11-07T00:00:00+00:00",
        method=receipts.ReceiptMethod(kind=kind, key=key),
        package=None,
        artifacts=(),
        smoke=None,
        hooks={},
    )


def test_codegraph_unregister_targets_only_recorded_hosts() -> None:
    assert pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("codex", "claude")) == (
        _uninstall("claude,codex"),
    )
    assert pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("cursor",)) == (_uninstall("cursor"),)


def test_unregister_drops_unknown_and_tampered_ids() -> None:
    kept = pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("claude", "all", "../x", "pi"))
    assert kept == (_uninstall("claude"),)
    assert pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("all", "auto")) == ()
    assert pi.unregister_argvs("not-a-real-hook", "/b/codegraph", ("claude",)) == ()


@pytest.mark.parametrize("subset", _ALL_SUBSETS, ids=lambda s: ",".join(s) or "none")
def test_unregister_never_passes_all(subset: tuple[str, ...]) -> None:
    for argv in pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", subset):
        assert "all" not in argv
        assert "auto" not in argv


def test_hook_method_matches_the_receipt_key() -> None:
    first = Method(kind="github_release", params={"repo": "a/a"})
    second = Method(kind="github_release", params={"repo": "b/b"})
    brew = Method(kind="brew", params={"formula": "demo"})
    keyed = Tool(id="demo", name="demo", category="ai", cmd="demo", methods=(first, second))
    lone = Tool(id="demo", name="demo", category="ai", cmd="demo", methods=(first, brew))
    assert (
        pi.hook_method(keyed, _receipt_for("github_release", receipts.method_key(second))) is second
    )
    assert pi.hook_method(lone, _receipt_for("github_release", "stale")) is first
    assert pi.hook_method(keyed, _receipt_for("github_release", "stale")) is None


def test_host_labels_use_catalog_ids() -> None:
    assert pi.host_labels(("cursor", "claude")) == "claude, cursor-agent"
    assert pi.host_labels(()) == ""


_HERDR = "herdr-integration"
_TEALDEER = "tealdeer-cache"
_TLDR_NOTE = "fetching the tldr page cache — tldr --update"


def test_herdr_registers_and_unregisters_per_host() -> None:
    method = Method(kind="github_release", params={"bin_dir": "/b"})
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        _HERDR, method, lambda cmd: calls.append(cmd), frozenset({"cursor", "claude", "pi"})
    )
    assert outcome == (("claude", "cursor"), None)
    assert calls == [
        ["/b/herdr", "integration", "install", "claude"],
        ["/b/herdr", "integration", "install", "cursor"],
    ]
    assert pi.unregister_argvs(_HERDR, "/b/herdr", ("cursor", "claude")) == (
        ("/b/herdr", "integration", "uninstall", "claude"),
        ("/b/herdr", "integration", "uninstall", "cursor"),
    )

    def cursor_fails(cmd: list[str]) -> None:
        if cmd[-1] == "cursor":
            raise CommandError(cmd, 1, detail="boom")

    failed = pi.run_postinstall(_HERDR, method, cursor_fails, frozenset({"cursor", "claude", "pi"}))
    assert failed == (("claude",), "cursor: boom")


def test_tealdeer_fetches_its_cache_after_install() -> None:
    method = Method(kind="github_release", params={"bin_dir": "/b"})
    seen: list[object] = []

    class _NotingRunner:
        def __call__(self, cmd: list[str]) -> None:
            seen.append(cmd)

        def note(self, text: str) -> None:
            seen.append(text)

    assert pi.run_postinstall(_TEALDEER, method, _NotingRunner(), frozenset()) == ((), None)
    assert seen == [_TLDR_NOTE, ["/b/tldr", "--update"]]

    calls: list[list[str]] = []
    assert pi.run_postinstall(_TEALDEER, method, lambda cmd: calls.append(cmd), frozenset()) == (
        (),
        None,
    )
    assert calls == [["/b/tldr", "--update"]]


def test_a_failed_tldr_update_is_a_warning() -> None:
    method = Method(kind="github_release", params={"bin_dir": "/b"})

    def failing(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="boom\nmore")

    assert pi.run_postinstall(_TEALDEER, method, failing, frozenset()) == (
        (),
        "tldr --update failed: boom; run it yourself later",
    )


def test_which_with_brew_finds_a_linuxbrew_binary_shutil_which_cannot_see(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CR-04: right after a brew install, `shutil.which` cannot see the brew bin dir yet.

    `which_with_brew` falls back to the well-known brew prefixes, by disk presence.
    """

    def which_misses(_name: str) -> str | None:
        return None

    monkeypatch.setattr(shutil, "which", which_misses)
    linuxbrew = tmp_path / "linuxbrew"
    linuxbrew.mkdir()
    (linuxbrew / "zsh").write_text("#!/bin/sh\n")
    monkeypatch.setattr(pi, "BREW_BIN_DIRS", (linuxbrew,))

    assert pi.which_with_brew("zsh") == str(linuxbrew / "zsh")
    assert pi.which_with_brew("does-not-exist") is None


def test_which_with_brew_prefers_a_real_shutil_which_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    def which_hits(_name: str) -> str | None:
        return "/usr/bin/zsh"

    monkeypatch.setattr(shutil, "which", which_hits)

    assert pi.which_with_brew("zsh") == "/usr/bin/zsh"
