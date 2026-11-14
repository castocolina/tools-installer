import hashlib
import shutil
import tomllib
from collections.abc import Callable
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import pytest

import installer.engine as engine_mod
import installer.postinstall as pi
from installer import app, receipts
from installer.engine import install_tool
from installer.enums import InstallStatus
from installer.model import HARNESS_MARKER_DIRS, Method, Tool, load_tools
from installer.platform import Platform
from installer.run import CommandError
from installer.uninstall import removal_plan, remove_paths
from installer.versions import Release
from tests.test_download import fixture_runner

_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"

_CODEGRAPH = "codegraph-mcp-register"
# Harness ids: the keys of every hook target map. `cursor` is the Cursor harness;
# the catalog id `cursor-agent` is display-only (HOST_CATALOG_IDS).
_HARNESSES = ("claude", "codex", "opencode", "cursor", "copilot", "pi")
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
    "copilot": "copilot-cli",
    "pi": "pi",
}
_GITHUB = Method(kind="github_release", params={})
_BREW = Method(kind="brew", params={"formula": "codegraph"})


def _pi_gate() -> list[str]:
    return [str(Path.home() / ".local" / "bin" / "codegraph"), "install", "--print-config", "pi"]


_PI_SKIPPED = "pi: this codegraph has no pi target, so Pi is not registered"


def _answers_config(_argv: list[str]) -> str | None:
    return "{}"


@pytest.fixture(autouse=True)
def codegraph_supports_pi(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Pi gate's probe never launches codegraph: by default it answers a config text."""
    monkeypatch.setattr(pi, "codegraph_query", _answers_config)


def _fake_codegraph(monkeypatch: pytest.MonkeyPatch, *, supports_pi: bool) -> list[list[str]]:
    """Replace the gate's probe, recording every argv it is asked."""
    seen: list[list[str]] = []

    def query(argv: list[str]) -> str | None:
        seen.append(argv)
        return "{}" if supports_pi else None

    monkeypatch.setattr(pi, "codegraph_query", query)
    return seen


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
    """Every subset of the codegraph harnesses produces either the exact expected argv
    (never "auto" or "all") or a genuine no-op, never anything else."""
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
    assert "all" not in calls[0]


def test_codegraph_hook_preserves_declared_host_order() -> None:
    calls: list[list[str]] = []
    pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset(_HARNESSES))
    assert calls[0][calls[0].index("--target") + 1] == "claude,codex,opencode,cursor,copilot-cli,pi"


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


def test_no_present_supported_host_runs_nothing() -> None:
    _write_receipt()
    calls: list[list[str]] = []
    outcome = pi.register_hooks(
        _codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), frozenset[str]()
    )
    assert outcome == ((), None)
    assert calls == []
    receipt = receipts.read("codegraph")
    assert receipt is not None
    # Known, none registered: the new-host sweep picks it up for the next host (CR-06).
    assert receipt.hooks == {"codegraph-mcp-register": ()}


def test_a_pi_only_host_registers_when_codegraph_supports_pi() -> None:
    _write_receipt()
    calls: list[list[str]] = []
    outcome = pi.register_hooks(
        _codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), frozenset({"pi"})
    )
    assert outcome == (("pi",), None)
    assert calls == [_argv("pi")]
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks == {_CODEGRAPH: ("pi",)}


def test_a_pi_only_host_runs_nothing_when_codegraph_lacks_pi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_codegraph(monkeypatch, supports_pi=False)
    _write_receipt()
    calls: list[list[str]] = []
    outcome = pi.register_hooks(
        _codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd), frozenset({"pi"})
    )
    assert outcome == ((), _PI_SKIPPED)
    assert calls == []
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks == {_CODEGRAPH: ()}


def test_only_herdr_and_codegraph_map_pi_and_targets_stay_harnesses() -> None:
    for name, pair in pi.POSTINSTALL_HOOKS.items():
        if pair.targets is None:
            continue
        assert ("pi" in pair.targets) == (name in {"herdr-integration", _CODEGRAPH}), name
        assert set(pair.targets) <= set(pi.HARNESS_PRESENCE), name


def test_harness_presence_matches_the_marker_dirs() -> None:
    expected: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "antigravity": (("agy",), (".gemini/antigravity",)),
        "claude": (("claude",), (".claude",)),
        "codex": (("codex",), (".codex",)),
        "copilot": (("copilot",), (".copilot",)),
        "cursor": (("cursor-agent", "cursor"), (".cursor", ".local/share/cursor-agent")),
        "devin": (("devin",), ()),
        "factory-droid": (("droid",), (".factory",)),
        "gemini-cli": (("gemini",), (".gemini",)),
        "grok": (("grok",), ()),
        "hermes": (("hermes",), ()),
        "kilo": ((), (".config/kilo",)),
        "kimi": ((), (".kimi-code",)),
        "muse": (("muse",), ()),
        "opencode": (("opencode",), (".config/opencode", ".opencode")),
        "pi": (("pi",), (".pi",)),
        "qwen": (("qwen",), ()),
        "windsurf": ((), (".codeium/windsurf",)),
    }
    assert expected == pi.HARNESS_PRESENCE
    assert HARNESS_MARKER_DIRS.keys() == pi.HARNESS_PRESENCE.keys()
    assert all(pi.HARNESS_PRESENCE[h][1] == HARNESS_MARKER_DIRS[h] for h in pi.HARNESS_PRESENCE)


def test_a_marker_dir_alone_makes_a_host_present(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()

    assert "cursor" in pi.present_harnesses(tmp_path, lambda _command: None)


@pytest.mark.usefixtures("real_present_hosts")
def test_copilot_codegraph_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """24.3-08 tracer (SPEC R9): a copilot CLI footprint registers codegraph as `copilot-cli`,
    records `copilot`, shows it as `copilot`, and removal's argv names `copilot-cli`."""
    monkeypatch.setenv("PATH", str(Path.home()))
    (Path.home() / ".copilot").mkdir()
    (Path.home() / ".copilot" / "settings.json").write_text("{}", encoding="utf-8")
    _write_receipt({_CODEGRAPH: ()})
    calls: list[list[str]] = []
    outcome = pi.register_hooks(_codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd))
    assert outcome == (("copilot",), None)
    assert calls == [_argv("copilot-cli")]
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks == {_CODEGRAPH: ("copilot",)}
    assert pi.host_labels(("copilot",)) == "copilot"
    assert pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("copilot",)) == (
        _uninstall("copilot-cli"),
    )


@pytest.mark.usefixtures("real_present_hosts")
@pytest.mark.parametrize(
    ("entries", "present"),
    [
        (("settings.json",), True),
        (("session-state/",), True),
        (("ide/", "settings.json"), True),
        (("ide/",), False),
        ((), False),
        (None, False),
    ],
    ids=["settings", "session-state", "ide-and-settings", "ide-only", "empty", "no-dir"],
)
def test_copilot_presence_needs_a_cli_footprint(
    monkeypatch: pytest.MonkeyPatch, entries: tuple[str, ...] | None, present: bool
) -> None:
    """CONTEXT D-13 amendment: the VS Code extension's `~/.copilot/ide/` alone is not the CLI."""
    monkeypatch.setenv("PATH", str(Path.home()))
    if entries is not None:
        root = Path.home() / ".copilot"
        root.mkdir()
        for entry in entries:
            if entry.endswith("/"):
                (root / entry).mkdir()
            else:
                (root / entry).write_text("{}", encoding="utf-8")
    assert ("copilot" in pi.present_hosts()) is present


@pytest.mark.usefixtures("real_present_hosts")
def test_copilot_on_path_is_present_without_a_footprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = tmp_path / "copilot"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert "copilot" in pi.present_hosts()


@pytest.mark.parametrize(
    "present_subset",
    [subset for subset in _ALL_SUBSETS if "copilot" not in subset],
    ids=lambda s: ",".join(s) or "none",
)
def test_copilot_absent_never_in_the_csv(present_subset: tuple[str, ...]) -> None:
    calls: list[list[str]] = []
    pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset(present_subset)
    )
    assert all("copilot-cli" not in cmd for cmd in calls)


def _pi_home() -> None:
    """A scratch HOME with Pi and claude footprints and no command on PATH."""
    (Path.home() / ".pi").mkdir()
    (Path.home() / ".claude").mkdir()


@pytest.mark.usefixtures("real_present_hosts")
def test_pi_registered_when_codegraph_supports_it(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_codegraph(monkeypatch, supports_pi=True)
    monkeypatch.setenv("PATH", str(Path.home()))
    _pi_home()
    _write_receipt({_CODEGRAPH: ()})
    herdr_receipt = replace(
        _receipt_for("github_release", "test"), tool="herdr", hooks={_HERDR: ("pi",)}
    )
    receipts.write(herdr_receipt)
    calls: list[list[str]] = []
    outcome = pi.register_hooks(_codegraph_tool(), _GITHUB, lambda cmd: calls.append(cmd))
    assert outcome == (("claude", "pi"), None)
    assert seen == [_pi_gate()]
    assert calls == [_argv("claude,pi")]
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks == {_CODEGRAPH: ("claude", "pi")}
    assert pi.host_labels(("pi",)) == "pi"
    assert pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("pi",)) == (_uninstall("pi"),)
    assert receipts.read("herdr") == herdr_receipt


def test_codegraph_query_turns_telemetry_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review R1-13: the gate's probe must not queue codegraph telemetry under ~/.codegraph."""
    answers: list[object] = ["config", CommandError(["codegraph"], 1), OSError("gone")]
    envs: list[object] = []

    def fake_run_query(argv: list[str], *, env: dict[str, str] | None = None) -> str:
        envs.append(env)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return str(answer)

    monkeypatch.setattr(pi, "run_query", fake_run_query)
    query = vars(pi)["_run_codegraph_query"]
    assert [query(["codegraph", "x"]) for _ in range(3)] == ["config", None, None]
    assert envs == [{"CODEGRAPH_TELEMETRY": "0", "DO_NOT_TRACK": "1"}] * 3


def test_unsupported_pi_never_reaches_the_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_codegraph(monkeypatch, supports_pi=False)
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude", "pi"})
    )
    assert outcome == (("claude",), _PI_SKIPPED)
    assert calls == [_argv("claude")]

    calls.clear()
    outcome = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"pi"})
    )
    assert outcome == ((), _PI_SKIPPED)
    assert calls == []


def test_a_failed_registration_keeps_the_pi_skip_note(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_codegraph(monkeypatch, supports_pi=False)

    def failing(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="boom")

    registered, warning = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, failing, frozenset({"claude", "pi"})
    )
    assert registered == ()
    assert warning is not None
    assert warning.startswith("codegraph MCP registration failed")
    assert warning.endswith(_PI_SKIPPED)


def test_pi_gate_probes_only_when_pi_is_wanted(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_codegraph(monkeypatch, supports_pi=True)
    pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda _cmd: None, frozenset({"claude", "copilot"}))
    assert seen == []
    pi.run_postinstall(_CODEGRAPH, _GITHUB, lambda _cmd: None, frozenset({"claude", "pi"}))
    assert seen == [_pi_gate()]


def test_pi_agent_dir_is_left_to_codegraph(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """SPEC R8 encoding edge: no Pi path or `auto`/`all` in an argv; nothing written under ~/.pi."""
    custom = tmp_path / "pi-agent"
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(custom))
    seen = _fake_codegraph(monkeypatch, supports_pi=True)
    calls: list[list[str]] = []
    outcome = pi.run_postinstall(
        _CODEGRAPH, _GITHUB, lambda cmd: calls.append(cmd), frozenset({"claude", "pi"})
    )
    undo = pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", outcome[0])
    for argv in (*calls, *seen, *undo):
        assert "auto" not in argv
        assert "all" not in argv
        assert not any(str(Path.home() / ".pi") in part or str(custom) in part for part in argv)
    assert not (Path.home() / ".pi").exists()
    assert not custom.exists()


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
    kept = pi.unregister_argvs(_CODEGRAPH, "/b/codegraph", ("claude", "all", "../x", "nope", "pi"))
    assert kept == (_uninstall("claude,pi"),)
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


_STATUS_ALL_NEW = "claude: not installed (/x)\ncursor: not installed (/x)\npi: not installed (/x)\n"
# src/cli/integration.rs parse_integration_target, herdr v0.9.5, read 2026-11-12
_HERDR_V095_TARGETS = {
    *("pi", "omp", "claude", "codex", "copilot", "devin", "droid", "kimi", "opencode", "kilo"),
    *("hermes", "qodercli", "qwen", "letta", "cursor", "mastracode", "antigravity-cli", "grok"),
}


def test_herdr_targets_are_shared_hosts() -> None:
    targets = pi.POSTINSTALL_HOOKS[_HERDR].targets
    assert targets is not None
    assert set(targets) == {
        "claude",
        "codex",
        "opencode",
        "cursor",
        "pi",
        "copilot",
        "kilo",
        "kimi",
        "qwen",
        "devin",
        "grok",
        "hermes",
        "factory-droid",
    }
    assert set(targets) <= set(HARNESS_MARKER_DIRS)
    assert set(targets.values()) <= _HERDR_V095_TARGETS
    assert targets["factory-droid"] == "droid"
    assert {"antigravity", "gemini-cli"}.isdisjoint(targets)
    assert {"pi", "copilot"} <= set(pi.HOST_CATALOG_IDS)


def test_herdr_registers_and_unregisters_per_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_herdr(monkeypatch, status=_STATUS_ALL_NEW)
    method = Method(kind="github_release", params={"bin_dir": "/b"})
    calls: list[list[str]] = []
    hosts = frozenset({"cursor", "claude", "pi"})
    outcome = pi.run_postinstall(_HERDR, method, lambda cmd: calls.append(cmd), hosts)
    assert outcome == (("claude", "cursor", "pi"), None)
    assert calls == [
        ["/b/herdr", "integration", "install", "claude"],
        ["/b/herdr", "integration", "install", "cursor"],
        ["/b/herdr", "integration", "install", "pi"],
    ]
    assert pi.unregister_argvs(_HERDR, "/b/herdr", ("pi", "cursor", "claude")) == (
        ("/b/herdr", "integration", "uninstall", "claude"),
        ("/b/herdr", "integration", "uninstall", "cursor"),
        ("/b/herdr", "integration", "uninstall", "pi"),
    )

    def cursor_fails(cmd: list[str]) -> None:
        if cmd[-1] == "cursor":
            raise CommandError(cmd, 1, detail="boom")

    failed = pi.run_postinstall(_HERDR, method, cursor_fails, hosts)
    assert failed == (("claude", "pi"), "cursor: boom")


def test_current_hosts_are_left_out_of_the_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    status = (
        "claude: current (v10) (/x)\nopencode: needs repair (v13) (/x)\npi: not installed (/x)\n"
    )
    _fake_herdr(monkeypatch, status=status)
    method = Method(kind="github_release", params={"bin_dir": "/b"})
    calls: list[list[str]] = []
    registered, warning = pi.run_postinstall(
        _HERDR, method, lambda cmd: calls.append(cmd), frozenset({"claude", "opencode", "pi"})
    )
    assert registered == ("opencode", "pi")
    assert calls == [
        ["/b/herdr", "integration", "install", "opencode"],
        ["/b/herdr", "integration", "install", "pi"],
    ]
    assert warning is not None
    assert "claude" in warning
    assert "yours" in warning


@pytest.mark.parametrize("unreadable", [None, "no recognisable line\n"], ids=["none", "garbage"])
def test_unreadable_status_registers_nothing(
    monkeypatch: pytest.MonkeyPatch, unreadable: str | None
) -> None:
    _fake_herdr(monkeypatch, status=unreadable)
    calls: list[list[str]] = []
    registered, warning = pi.run_postinstall(
        _HERDR,
        Method(kind="github_release", params={"bin_dir": "/b"}),
        calls.append,
        frozenset({"claude"}),
    )
    assert (registered, calls) == ((), [])
    assert warning is not None
    assert "status" in warning


def test_herdr_query_reads_output_whatever_the_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes: list[object] = [
        "ok\n",
        CommandError(["herdr"], 1, stdout="partial\n"),
        CommandError(["herdr"], 127),
        CommandError(["herdr"], 124, detail="timed out after 20s"),
    ]

    def fake_run_query(argv: list[str]) -> str:
        outcome = outcomes.pop(0)
        if isinstance(outcome, CommandError):
            raise outcome
        return str(outcome)

    monkeypatch.setattr(pi, "run_query", fake_run_query)
    assert [pi.herdr_query(["herdr", "x"]) for _ in range(4)] == ["ok\n", "partial\n", None, None]


def test_one_host_failure_keeps_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    status = "opencode: not installed (/x)\npi: not installed (/x)\n"
    _fake_herdr(monkeypatch, status=status)

    def pi_fails(cmd: list[str]) -> None:
        if cmd[-1] == "pi":
            raise CommandError(cmd, 1, detail="boom")

    registered, warning = pi.run_postinstall(
        _HERDR,
        Method(kind="github_release", params={"bin_dir": "/b"}),
        pi_fails,
        frozenset({"opencode", "pi"}),
    )
    assert registered == ("opencode",)
    assert warning == "pi: boom"
    assert pi.unregister_argvs(_HERDR, "/b/herdr", registered) == (
        ("/b/herdr", "integration", "uninstall", "opencode"),
    )


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


_SIDEBAR_REF = "2b5ca2aedf06a5a988a5087da22e65b469ffc84d"
_SIDEBAR_SOURCE = "castocolina/herdr-setup/plugins/workspace-here"
_NO_PLUGINS = '{"id": "cli:plugin", "result": {"type": "plugin_list", "plugins": []}}'


def _herdr_tool() -> Tool:
    return next(tool for tool in load_tools(_REGISTRY) if tool.id == "herdr")


def _fake_herdr(
    monkeypatch: pytest.MonkeyPatch,
    status: str | None = "claude: not installed (/x)\n",
    plugins: str = _NO_PLUGINS,
) -> list[list[str]]:
    """Replace the read-only herdr probe: `integration status` and `plugin list` answer from
    the arguments, so no herdr process is ever launched."""
    seen: list[list[str]] = []

    def query(argv: list[str]) -> str | None:
        seen.append(argv)
        if argv[1:3] == ["integration", "status"]:
            return status
        if argv[1:3] == ["plugin", "list"]:
            return plugins
        return None

    monkeypatch.setattr(pi, "herdr_query", query)
    return seen


def test_herdr_installs_registers_and_removes_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """24-07 tracer: the shipped herdr row installs, registers claude and the sidebar plugin,
    records both, and its removal undoes exactly those, integration first."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("HERDR_CONFIG_PATH", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    herdr = _herdr_tool()
    asset = "herdr-linux-x86_64"
    payload = b"#!/bin/sh\nexit 0\n"
    digest = hashlib.sha256(payload).hexdigest()
    workdir = tmp_path / "dl"
    workdir.mkdir()

    def not_installed(_tool: Tool) -> bool:
        return False

    def release_resolver(_resolve_tag: object) -> Callable[[str], Release]:
        return lambda _repo: Release("v0.9.5", {asset: digest})

    def pinned_workdir(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(engine_mod, "is_installed", not_installed)
    monkeypatch.setattr(engine_mod, "release_resolver", release_resolver)
    monkeypatch.setattr(engine_mod.download.tempfile, "mkdtemp", pinned_workdir)
    calls, runner = fixture_runner(workdir, {asset: payload})
    monkeypatch.setattr(pi, "present_hosts", lambda: frozenset({"claude"}))
    monkeypatch.setattr(pi, "has_python3", lambda: True)
    _fake_herdr(monkeypatch)

    outcome = install_tool(
        herdr,
        Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        runner=runner,
    )

    binary = str(tmp_path / ".local" / "bin" / "herdr")
    assert outcome.status == InstallStatus.INSTALLED
    assert outcome.postinstall_warning is None
    assert [cmd for cmd in calls if cmd[0] == binary] == [
        [binary, "integration", "install", "claude"],
        [binary, "plugin", "install", "--ref", _SIDEBAR_REF, "--yes", _SIDEBAR_SOURCE],
        [binary, "server", "reload-config"],
    ]
    config = tmp_path / ".config" / "herdr" / "config.toml"
    sidebar = tomllib.loads(config.read_text(encoding="utf-8"))["ui"]["sidebar"]
    assert set(sidebar["agents"]) == {"rows", "row_gap"}
    assert set(sidebar["spaces"]) == {"rows"}
    receipt = receipts.read("herdr")
    assert receipt is not None
    assert receipt.hooks == {_HERDR: ("claude", "sidebar-markers")}

    plan = removal_plan(herdr, tmp_path / ".local" / "bin")
    assert plan.unregister == (
        (binary, "integration", "uninstall", "claude"),
        (binary, "plugin", "uninstall", "herdr-setup.markers"),
    )
    assert remove_paths([plan.artifacts[path] for path in plan.removable]) == ()
    app._after_removal(  # pyright: ignore[reportPrivateUsage]
        herdr,
        bundles=(),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        extra_policies=(),
        platform_os="linux",
    )
    assert not config.exists() or "sidebar" not in config.read_text(encoding="utf-8")


def test_standalone_targets_are_not_hosts() -> None:
    """R1-06, R2-13: a standalone id is never a harness; the host-target maps stay harnesses."""
    for name, pair in pi.POSTINSTALL_HOOKS.items():
        if pair.targets is not None:
            assert set(pair.targets) <= set(pi.HARNESS_PRESENCE), name
        assert set(pair.standalone).isdisjoint(pi.HARNESS_PRESENCE), name
    assert pi.unregister_hosts(_HERDR, ("claude", "sidebar-markers", "all")) == (
        "claude",
        "sidebar-markers",
    )


def test_host_labels_never_names_a_standalone_target() -> None:
    assert pi.host_labels(("claude", "sidebar-markers")) == "claude"
    assert pi.host_labels(("sidebar-markers",)) == ""


_SIDEBAR_ONLY = frozenset({"sidebar-markers"})
_PLUGIN_LISTED = (
    '{"id": "cli:plugin", "result": {"type": "plugin_list", "plugins": '
    '[{"plugin_id": "herdr-setup.markers"}]}}'
)


def _sidebar_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    python3: bool = True,
    plugins: str = _NO_PLUGINS,
    fail: str | None = None,
) -> tuple[pi.HookOutcome, list[list[str]], Path]:
    """Run the sidebar step in the scratch HOME; `fail` names the herdr verb whose call raises."""
    monkeypatch.delenv("HERDR_CONFIG_PATH", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(pi, "has_python3", lambda: python3)
    _fake_herdr(monkeypatch, plugins=plugins)
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if fail is not None and fail in cmd:
            raise CommandError(cmd, 1, detail=f"{fail} failed")

    outcome = pi.run_postinstall(
        _HERDR, Method(kind="github_release", params={"bin_dir": "/b"}), runner, _SIDEBAR_ONLY
    )
    return outcome, calls, Path.home() / ".config" / "herdr" / "config.toml"


def test_sidebar_needs_python3(monkeypatch: pytest.MonkeyPatch) -> None:
    (registered, warning), calls, config = _sidebar_run(monkeypatch, python3=False)
    assert registered == ()
    assert calls == []
    assert not config.exists()
    assert warning is not None
    assert "needs python3" in warning


def test_user_plugin_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    (registered, warning), calls, config = _sidebar_run(monkeypatch, plugins=_PLUGIN_LISTED)
    assert registered == ()
    assert calls == []
    assert not config.exists()
    assert warning is not None
    assert "herdr-setup.markers" in warning
    assert "yours" in warning


def test_unreadable_plugin_list_sets_nothing_up(monkeypatch: pytest.MonkeyPatch) -> None:
    (registered, warning), calls, config = _sidebar_run(monkeypatch, plugins="not json")
    assert (registered, calls) == ((), [])
    assert not config.exists()
    assert warning is not None
    assert "plugin list" in warning


def test_failed_plugin_install_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    (registered, warning), _calls, config = _sidebar_run(monkeypatch, fail="plugin")
    assert registered == ()
    assert not config.exists()
    assert warning == "sidebar markers: plugin failed"


def test_user_rows_are_kept_and_the_tokens_named(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Path.home() / ".config" / "herdr" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[ui.sidebar.agents]\nrows = [["agent"]]\n', encoding="utf-8")
    (registered, warning), _calls, _config = _sidebar_run(monkeypatch)
    sidebar = tomllib.loads(config.read_text(encoding="utf-8"))["ui"]["sidebar"]
    assert registered == ("sidebar-markers",)
    assert sidebar["agents"]["rows"] == [["agent"]]
    assert sidebar["agents"]["row_gap"] == 1
    assert set(sidebar["spaces"]) == {"rows"}
    assert warning is not None
    assert '{ token = "$rule", dim = true }' in warning
    assert '{ token = "$here", bold = true }' in warning


def test_reload_failure_is_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    (registered, warning), calls, config = _sidebar_run(monkeypatch, fail="reload-config")
    assert registered == ("sidebar-markers",)
    assert calls[-1] == ["/b/herdr", "server", "reload-config"]
    assert "sidebar" in config.read_text(encoding="utf-8")
    assert warning is not None
    assert "reload-config failed" in warning
