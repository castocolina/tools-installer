from collections.abc import Callable
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from installer.download import link_name
from installer.enums import UninstallState
from installer.model import Method, Tool, load_tools
from installer.policy import Policy, daemon_policy, omz_plugins_policy, tweak_policy
from installer.run import CommandError
from installer.tweaks import BUNDLES, TweakBundle
from installer.uninstall import (
    SweepResult,
    active_tweak_ids,
    manager_name,
    plan_removal,
    plan_uninstall,
    remove_paths,
    sweep_tweaks,
)


def _tool(method: Method, *, tool_id: str = "t", cmd: str = "t") -> Tool:
    # methods is tuple[Method, ...]; priority/audience/desc use their defaults.
    return Tool(id=tool_id, name=tool_id, category="dev", cmd=cmd, methods=(method,))


def _dl_tool(tool_id: str, member: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(
            Method(
                kind="github_release",
                params={"repo": f"a/{tool_id}", "asset": "x", "member": member},
            ),
        ),
    )


def loop_tool(tool_id: str) -> Tool:
    """Public form of `_dl_tool`: tests/test_app.py imports it (pyright
    reportPrivateUsage keeps underscore names module-private)."""
    return _dl_tool(tool_id, tool_id)


def plant_removal_fixtures(home: Path) -> list[Tool]:
    """Plant the H3 hazard tree under ``home`` and return its tools.

    Public on purpose: tests/test_app.py imports it so the TUI rows and the
    `--yes` CLI comparison run on identical trees. The tree holds one
    proven-removable archive tool (fd) beside the foreign files the old
    name-match removal would have deleted: a uv-installed ruff symlink, a
    pip-installed yq plain file, and a drawio file shared by two registry
    tools. Everything lives under ``home``; callers monkeypatch Path.home.
    """
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    opt_fd = home / ".local" / "opt" / "fd"
    opt_fd.mkdir(parents=True, exist_ok=True)
    (opt_fd / "fd").write_text("archive binary")
    (bin_dir / "fd").symlink_to(opt_fd / "fd")
    uv_ruff = home / ".local" / "share" / "uv" / "tools" / "ruff" / "bin" / "ruff"
    uv_ruff.parent.mkdir(parents=True, exist_ok=True)
    uv_ruff.write_text("uv-installed ruff")
    (bin_dir / "ruff").symlink_to(uv_ruff)
    (bin_dir / "yq").write_text("pip-installed yq")
    (bin_dir / "drawio").write_text("shared drawio")
    return [
        _dl_tool("fd", "fd"),
        _dl_tool("ruff", "ruff"),
        _dl_tool("yq", "yq"),
        _dl_tool("drawio-desktop", "drawio"),
        _dl_tool("drawio-cli", "drawio"),
    ]


def test_link_name_prefers_bin_name() -> None:
    method = Method(
        kind="tarball",
        params={
            "url": "https://x.tgz",
            "member": "sublime_text/sublime_text",
            "bin_name": "subl",
        },
    )
    assert link_name(method, "sublime_text/sublime_text") == "subl"
    plain = Method(kind="tarball", params={"url": "https://x.tgz", "member": "a/b"})
    assert link_name(plain, "a/b") == "b"


def test_plan_uninstall_names_the_link_like_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sublime ships member sublime_text/sublime_text with bin_name subl;
    install names the link subl, so uninstall must look for bin/subl too."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "subl"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "subl").write_text("binary")
    (bin_dir / "subl").symlink_to(opt / "subl")
    tool = Tool(
        id="sublime",
        name="sublime",
        category="dev",
        cmd="subl",
        methods=(
            Method(
                kind="tarball",
                params={
                    "url": "https://x/sublime.tgz",
                    "member": "sublime_text/sublime_text",
                    "bin_name": "subl",
                },
            ),
        ),
    )
    assert plan_uninstall([tool], bin_dir) == [opt, bin_dir / "subl"]


def test_plan_removal_survives_looping_link_and_opt_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-01: a symlink loop is unproven, never a crash. A self-looping bin
    link (bin/foo -> foo) and a looping opt dir must leave plan_removal (and
    every caller: classify_tools, UninstallScreen, run_uninstall) standing,
    with the looping names still listed for manual removal."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt"
    bin_dir.mkdir(parents=True)
    opt.mkdir(parents=True)
    (bin_dir / "foo").symlink_to("foo")  # self-loop at a catalog link name
    (opt / "loop").symlink_to("loop")  # looping opt dir
    (bin_dir / "bar").symlink_to(opt / "loop" / "bar")
    tools = [_dl_tool("foo", "foo"), _dl_tool("bar", "bar")]
    plan = plan_removal(tools, bin_dir)
    assert plan.removable == ()
    assert bin_dir / "foo" in plan.yourself
    assert bin_dir / "bar" in plan.yourself
    rows = classify_tools(tools, bin_dir, installed={"foo": False, "bar": False}, platform=_LINUX)
    assert all(row.state != UninstallState.REMOVABLE for row in rows)


@pytest.mark.parametrize(
    ("tool_id", "removable_paths", "yourself_paths"),
    [
        pytest.param(
            "fd",
            ["{bin}/fd", "{opt}"],
            [],
            id="archive-layout",
        ),
        pytest.param("ruff", [], ["{bin}/ruff"], id="uv-ruff-symlink"),
        pytest.param("yq", [], ["{bin}/yq"], id="pip-yq-file"),
        pytest.param("drawio-desktop", [], ["{bin}/drawio"], id="shared-drawio"),
    ],
)
def test_plan_removal_proves_only_the_archive_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool_id: str,
    removable_paths: list[str],
    yourself_paths: list[str],
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    plan = plan_removal([next(t for t in tools if t.id == tool_id)], bin_dir)
    assert plan.removable == tuple(
        Path(str(p).format(bin=bin_dir, opt=opt_fd)) for p in removable_paths
    )
    assert plan.yourself == tuple(
        Path(str(p).format(bin=bin_dir, opt=opt_fd)) for p in yourself_paths
    )
    # A path is never in both lists.
    assert not set(plan.removable) & set(plan.yourself)


def test_plan_removal_lists_the_shared_drawio_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    plan = plan_removal([t for t in tools if t.id.startswith("drawio")], bin_dir)
    assert plan.yourself.count(bin_dir / "drawio") == 1
    assert plan.removable == ()


def test_plan_removal_rejects_a_link_into_another_tools_opt_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    foreign = tmp_path / ".local" / "opt" / "rg"
    foreign.mkdir(parents=True)
    (foreign / "rg").write_text("rg binary")
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").symlink_to(foreign / "rg")
    tool = _dl_tool("fd", "fd")
    plan = plan_removal([tool], bin_dir)
    assert plan.removable == ()
    assert bin_dir / "fd" in plan.yourself


def test_plan_removal_app_bundles_are_remove_it_yourself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bundle = tmp_path / "Applications" / "Demo App.app"
    bundle.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (bin_dir / "demo").symlink_to(bundle / "Contents/bin/demo")
    tool = Tool(
        id="demo",
        name="demo",
        category="dev",
        cmd="demo",
        methods=(
            Method(
                kind="app",
                params={
                    "url": "https://example.test/a.zip",
                    "app": "Demo App.app",
                    "cli": "Contents/bin/demo",
                },
            ),
        ),
    )
    plan = plan_removal([tool], bin_dir)
    assert plan.removable == ()
    assert set(plan.yourself) == {bundle, bin_dir / "demo"}


def test_plan_removal_with_no_matches_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    empty = plan_removal([], bin_dir)
    assert plan_removal([_dl_tool("fd", "fd")], bin_dir) == empty
    assert empty.removable == ()
    assert empty.yourself == ()


def test_classify_rows_follow_the_removal_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    rows = classify_tools(tools, bin_dir, installed={t.id: True for t in tools}, platform=_LINUX)
    by_id = {row.tool.id: row for row in rows}
    fd = by_id["fd"]
    assert fd.state == "removable"
    assert fd.paths == [bin_dir / "fd", tmp_path / ".local" / "opt" / "fd"]
    assert fd.selectable is True
    assert "removable" in fd.hint
    for tool_id in ("ruff", "yq", "drawio-desktop"):
        row = by_id[tool_id]
        assert row.state == "managed", tool_id
        assert row.selectable is False, tool_id
        assert row.paths == [], tool_id
        assert "remove it yourself:" in row.hint, tool_id
    assert str(bin_dir / "ruff") in by_id["ruff"].hint
    assert str(bin_dir / "drawio") in by_id["drawio-desktop"].hint


def test_manager_name_is_a_public_export() -> None:
    method = Method(kind="brew", params={"formula": "ripgrep"})
    assert manager_name(method, "formula", "rg") == "ripgrep"
    assert manager_name(Method(kind="brew"), "formula", "rg") == "rg"


def test_plan_collects_existing_opt_and_bin_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    paths = plan_uninstall([tool], bin_dir)
    assert set(paths) == {opt, bin_dir / "fd"}


def test_plan_skips_absent_paths_and_nondownload_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    brew_tool = _tool(Method(kind="brew", params={"formula": "x"}), tool_id="b", cmd="b")
    dl_tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    assert plan_uninstall([brew_tool, dl_tool], bin_dir) == []


def test_plan_uses_basename_of_nested_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "gh"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    tool = _tool(
        Method(kind="github_release", params={"repo": "cli/cli", "asset": "x", "member": "bin/gh"})
    )
    assert set(plan_uninstall([tool], bin_dir)) == {opt}  # opt exists, bin/gh symlink does not


def test_plan_includes_dangling_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").symlink_to(tmp_path / "gone")  # target missing -> dangling
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"})
    )
    assert plan_uninstall([tool], bin_dir) == [bin_dir / "fd"]


def test_plan_dedupes_repeated_binname(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    # Two download methods on one tool with the same member -> opt path must appear once.
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),
            Method(kind="tarball", params={"url": "https://x/fd.tgz", "member": "fd"}),
        ),
    )
    assert plan_uninstall([tool], bin_dir) == [opt]


def test_plan_honors_declared_bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    default_bin = tmp_path / ".local" / "bin"
    custom_bin = tmp_path / "custom"
    custom_bin.mkdir(parents=True)
    (custom_bin / "fd").write_text("bin")
    tool = _tool(
        Method(
            kind="github_release",
            params={"repo": "a/fd", "asset": "x", "member": "fd", "bin_dir": str(custom_bin)},
        )
    )
    assert plan_uninstall([tool], default_bin) == [custom_bin / "fd"]


def test_remove_paths_deletes_dirs_files_and_symlinks(tmp_path: Path):
    opt = tmp_path / "opt" / "fd"
    opt.mkdir(parents=True)
    (opt / "fd").write_text("bin")
    real = tmp_path / "real"
    real.write_text("x")
    link = tmp_path / "link"
    link.symlink_to(real)
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing")
    plain = tmp_path / "plain"
    plain.write_text("y")
    remove_paths([opt, link, dangling, plain])
    assert not opt.exists()
    assert not link.is_symlink()
    assert not dangling.is_symlink()
    assert not plain.exists()
    assert real.exists()  # the symlink target itself is preserved


def test_plan_skips_method_with_missing_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A download method with no 'member' param must be silently skipped."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/fd", "asset": "x"})  # no member
    )
    assert plan_uninstall([tool], bin_dir) == []


def test_plan_skips_method_with_non_str_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A download method whose 'member' param is not a string must be silently skipped."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = _tool(
        Method(kind="tarball", params={"url": "https://x/fd.tgz", "member": 42})  # int, not str
    )
    assert plan_uninstall([tool], bin_dir) == []


def test_remove_paths_silently_skips_nonexistent_path(tmp_path: Path):
    """remove_paths must not raise when a path neither exists nor is a symlink."""
    absent = tmp_path / "never_created"
    remove_paths([absent])  # must complete without error


def test_plan_skips_traversal_binname(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    # member ".." would make binname "..", resolving opt/bin paths up to ~/.local.
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/x", "asset": "x", "member": ".."})
    )
    assert plan_uninstall([tool], bin_dir) == []


def test_remove_paths_unlinks_symlink_to_dir_without_deleting_target(tmp_path: Path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "keep").write_text("important")
    link = tmp_path / "link"
    link.symlink_to(target_dir)  # symlink to a DIRECTORY
    remove_paths([link])
    assert not link.is_symlink()  # the link itself is gone
    assert target_dir.is_dir()  # the target dir survives
    assert (target_dir / "keep").read_text() == "important"  # contents preserved


def test_plan_app_uses_cli_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "draw.io.app"
    bundle.mkdir(parents=True)
    (bin_dir / "drawio").symlink_to(bundle / "Contents/MacOS/draw.io")
    tool = _tool(
        Method(
            kind="app",
            params={
                "url": "https://example.test/drawio.zip",
                "app": "draw.io.app",
                "cli": "Contents/MacOS/draw.io",
                "cli_name": "drawio",
            },
        )
    )
    planned = set(plan_uninstall([tool], bin_dir))
    assert bin_dir / "drawio" in planned
    assert bundle in planned
    assert bin_dir / "draw.io" not in planned


def test_plan_collects_app_bundle_and_cli_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "Demo App.app"
    bundle.mkdir(parents=True)
    (bin_dir / "demo").symlink_to(bundle / "Contents/bin/demo")  # dangling is fine
    tool = _tool(
        Method(
            kind="app",
            params={
                "url": "https://example.test/a.zip",
                "app": "Demo App.app",
                "cli": "Contents/bin/demo",
            },
        )
    )
    assert set(plan_uninstall([tool], bin_dir)) == {bundle, bin_dir / "demo"}


def test_plan_app_without_cli_plans_bundle_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bundle = tmp_path / "Applications" / "Demo.app"
    bundle.mkdir(parents=True)
    tool = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": "Demo.app"})
    )
    assert plan_uninstall([tool], bin_dir) == [bundle]


def test_plan_app_skips_absent_bundle_and_guards_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    absent = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": "Gone.app"})
    )
    traversal = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": ".."}),
        tool_id="t2",
        cmd="t2",
    )
    nested = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip", "app": "x/Demo.app"}),
        tool_id="t3",
        cmd="t3",
    )
    no_app = _tool(
        Method(kind="app", params={"url": "https://example.test/a.zip"}),
        tool_id="t4",
        cmd="t4",
    )
    assert plan_uninstall([absent, traversal, nested, no_app], bin_dir) == []


def test_plan_app_guards_cli_traversal_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "Demo.app"
    bundle.mkdir(parents=True)
    tool = _tool(
        Method(
            kind="app",
            params={"url": "https://example.test/a.zip", "app": "Demo.app", "cli": "Contents/.."},
        )
    )
    # the bundle is planned; the traversal cli name is not
    assert plan_uninstall([tool], bin_dir) == [bundle]


def test_plan_skips_cask_methods(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = _tool(Method(kind="cask", params={"cask": "sublime-text"}))
    assert plan_uninstall([tool], bin_dir) == []


def test_plan_app_skips_cli_install_would_have_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "demo").write_text("someone else's file")
    bundle = tmp_path / "Applications" / "Demo.app"
    bundle.mkdir(parents=True)
    for cli in ("../demo", "/abs/demo"):
        tool = _tool(
            Method(
                kind="app",
                params={"url": "https://example.test/a.zip", "app": "Demo.app", "cli": cli},
            )
        )
        # install_app rejects these clis, so no symlink was ever created -> plan
        # must not touch the unrelated bin_dir/demo file.
        assert plan_uninstall([tool], bin_dir) == [bundle]


# --- classify_tools: removability over ALL tools (Phase 3) -----------------

from installer.platform import Platform  # noqa: E402
from installer.uninstall import ToolRow, classify_tools, reverse_dependencies  # noqa: E402

_LINUX = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
_MAC = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _dl(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(
            Method(kind="github_release", params={"repo": "a/b", "asset": "x", "member": tool_id}),
        ),
    )


def _brew(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def _cask(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(Method(kind="cask", params={"cask": tool_id}),),
    )


def _apt(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(Method(kind="apt", params={"package": tool_id}),),
    )


def test_classify_removable_when_artifacts_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("x")
    (bin_dir / "fd").symlink_to(opt / "fd")
    rows = classify_tools([_dl("fd")], bin_dir, installed={"fd": True}, platform=_LINUX)
    row = rows[0]
    assert row.state == "removable"
    assert row.paths  # non-empty, real artifacts
    assert row.selectable is True
    assert "removable" in row.hint


def test_classify_managed_when_installed_without_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_brew("jq")],
        tmp_path / "bin",
        installed={"jq": True},
        platform=_MAC,
        which=lambda _c: None,
    )
    row = rows[0]
    assert row.state == "managed"
    assert row.selectable is False
    assert row.paths == []
    assert "brew uninstall jq" in row.hint


def test_classify_managed_cask_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_cask("rectangle")],
        tmp_path / "bin",
        installed={"rectangle": True},
        platform=_MAC,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "brew uninstall --cask rectangle" in rows[0].hint


def test_classify_managed_seam_fed_apt_hint_names_apt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rewritten (15.4-05/D-03/D-04): the seam-fed apt case names apt and no
    longer carries the generic phrase -- the happy-path improvement. The
    no-seam generic fallback keeps its own regression guard immediately
    below, so improving this path does not lose it."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_apt("ripgrep")],
        tmp_path / "bin",
        installed={"ripgrep": True},
        platform=_LINUX,
        which=lambda _c: None,
        owner_hint=lambda tool: f"managed by apt — `apt remove {tool.id}`",
    )
    assert rows[0].state == "managed"
    assert "apt" in rows[0].hint
    assert "package manager" not in rows[0].hint


def test_classify_managed_generic_hint_when_no_seam_and_no_brew_method(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-seam generic path, kept covered on its own (15.4-05/D-03/D-04):
    with no `owner_hint` at all, an apt-only tool still falls back to the
    platform-filtered registry guess."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_apt("ripgrep")],
        tmp_path / "bin",
        installed={"ripgrep": True},
        platform=_LINUX,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "package manager" in rows[0].hint


def test_classify_managed_seam_returning_none_falls_back_per_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A seam returning `None` for a tool falls back to the registry-derived
    hint for THAT tool -- per tool, not per call, so one unattributable tool
    does not degrade the rest."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_apt("ripgrep"), _brew("jq")],
        tmp_path / "bin",
        installed={"ripgrep": True, "jq": True},
        platform=_MAC,
        which=lambda _c: None,
        owner_hint=lambda tool: "managed by dnf — `dnf remove jq`" if tool.id == "jq" else None,
    )
    ripgrep_row = next(r for r in rows if r.tool.id == "ripgrep")
    jq_row = next(r for r in rows if r.tool.id == "jq")
    assert "package manager" in ripgrep_row.hint
    assert "dnf remove jq" in jq_row.hint


def test_classify_managed_seam_only_consulted_for_managed_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removable, absent and unavailable rows never consult the seam."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("x")
    (bin_dir / "fd").symlink_to(opt / "fd")
    called: list[str] = []

    def seam(tool: Tool) -> str | None:
        called.append(tool.id)
        return "managed by dnf — `dnf remove x`"

    rows = classify_tools(
        [_dl("fd"), _cask("rectangle")],
        bin_dir,
        installed={"fd": True, "rectangle": False},
        platform=_LINUX,
        owner_hint=seam,
    )
    assert rows[0].state == "removable"
    assert rows[1].state == "unavailable"
    assert called == []


def test_classify_managed_codex_gets_generic_hint_on_linux_not_homebrew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round-2 review HIGH, over the REAL registry entry: codex declares a
    `script` method and a `cask` method gated `os = ["macos"]`
    (`installer/registry.toml:1343-1350`). A Linux platform must get the
    generic phrase, never a Homebrew instruction it cannot run."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = {t.id: t for t in load_tools(_REGISTRY)}
    codex = tools["codex"]
    rows = classify_tools(
        [codex],
        tmp_path / "bin",
        installed={"codex": True},
        platform=_LINUX,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "package manager" in rows[0].hint
    assert "Homebrew" not in rows[0].hint


def test_classify_managed_codex_keeps_cask_hint_on_macos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paired with the Linux case above: on a macOS-with-brew platform the
    filter narrows nothing and codex keeps its cask sentence, byte-identical
    to today's."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = {t.id: t for t in load_tools(_REGISTRY)}
    codex = tools["codex"]
    rows = classify_tools(
        [codex],
        tmp_path / "bin",
        installed={"codex": True},
        platform=_MAC,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "brew uninstall --cask codex" in rows[0].hint


def test_classify_managed_brew_only_tool_gets_generic_hint_without_brew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberate narrowing (Round-2 review HIGH): a brew-only tool on a host
    with no brew now gets the generic phrase instead of an unrunnable
    `brew uninstall` line -- the fix, not a regression."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    no_brew_linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    rows = classify_tools(
        [_brew("jq")],
        tmp_path / "bin",
        installed={"jq": True},
        platform=no_brew_linux,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "package manager" in rows[0].hint
    assert "brew uninstall" not in rows[0].hint


def _linuxbrew_cask_tool() -> Tool:
    return Tool(
        id="jetbrains-toolbox",
        name="jetbrains-toolbox",
        category="c",
        cmd="jetbrains-toolbox",
        methods=(Method(kind="cask", params={"cask": "jetbrains-toolbox"}, os=("macos",)),),
    )


def test_classify_managed_linuxbrew_cask_tool_gets_generic_fallback_on_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linuxbrew-cask-owned tool gets the generic phrase from the FALLBACK
    on Linux and its specific cask attribution from the ownership seam
    instead -- 15.4-02's ownership-only widening lives in
    `installer/ownership.py` and is deliberately not reachable from here."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_linuxbrew_cask_tool()],
        tmp_path / "bin",
        installed={"jetbrains-toolbox": True},
        platform=_LINUX,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "package manager" in rows[0].hint


def test_classify_managed_seam_hint_gets_found_at_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_apt("ripgrep")],
        tmp_path / "bin",
        installed={"ripgrep": True},
        platform=_LINUX,
        which=lambda c: f"/usr/bin/{c}",
        owner_hint=lambda _tool: "managed by apt — `apt remove ripgrep`",
    )
    assert "apt remove ripgrep" in rows[0].hint
    assert "found at /usr/bin/ripgrep" in rows[0].hint


def _sdkman_tool() -> Tool:
    return Tool(
        id="java",
        name="Java",
        category="runtime",
        cmd="java",
        methods=(
            Method(
                kind="sdkman",
                params={"candidate": "java", "bin_dir": "~/.sdkman/candidates/java/current/bin"},
            ),
        ),
    )


@pytest.mark.parametrize("platform", [_LINUX, _MAC])
def test_classify_managed_sdkman_tool_names_sdkman_on_every_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: Platform
) -> None:
    """A tool whose only declared method is `kind = "sdkman"` gets a hint
    naming SDKMAN and its candidate, with no seam wired at all -- on every
    platform, because `_applies` accepts `sdkman` unconditionally."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_sdkman_tool()],
        tmp_path / "bin",
        installed={"java": True},
        platform=platform,
        which=lambda _c: None,
    )
    assert rows[0].state == "managed"
    assert "SDKMAN" in rows[0].hint
    assert "java" in rows[0].hint


def test_classify_managed_brew_hint_uses_formula_not_cmd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hint must name the brew FORMULA, not the runnable cmd: rg's formula
    is `ripgrep`, so `brew uninstall rg` would fail if a user copied it."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = Tool(
        id="rg",
        name="rg",
        category="c",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "ripgrep"}),),
    )
    rows = classify_tools(
        [tool], tmp_path / "bin", installed={"rg": True}, platform=_MAC, which=lambda _c: None
    )
    assert "brew uninstall ripgrep" in rows[0].hint
    assert "uninstall rg`" not in rows[0].hint


def test_classify_managed_cask_hint_uses_cask_name_not_cmd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same for casks: vscode's cmd is `code` but its cask is visual-studio-code."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = Tool(
        id="vscode",
        name="vscode",
        category="c",
        cmd="code",
        methods=(Method(kind="cask", params={"cask": "visual-studio-code"}),),
    )
    rows = classify_tools(
        [tool], tmp_path / "bin", installed={"vscode": True}, platform=_MAC, which=lambda _c: None
    )
    assert "brew uninstall --cask visual-studio-code" in rows[0].hint


def test_classify_managed_brew_hint_falls_back_to_cmd_without_formula(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defensive: a brew method missing its formula param falls back to cmd."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = Tool(id="jq", name="jq", category="c", cmd="jq", methods=(Method(kind="brew"),))
    rows = classify_tools(
        [tool], tmp_path / "bin", installed={"jq": True}, platform=_MAC, which=lambda _c: None
    )
    assert "brew uninstall jq" in rows[0].hint


def test_classify_managed_cask_hint_falls_back_to_cmd_without_cask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defensive: a cask method missing its cask param falls back to cmd."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = Tool(id="rect", name="rect", category="c", cmd="rect", methods=(Method(kind="cask"),))
    rows = classify_tools(
        [tool], tmp_path / "bin", installed={"rect": True}, platform=_MAC, which=lambda _c: None
    )
    assert "brew uninstall --cask rect" in rows[0].hint


def test_classify_managed_shows_resolved_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A managed tool's detail surfaces where it resolves on PATH (via `which`),
    making 'managed elsewhere' concrete."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools(
        [_brew("jq")],
        tmp_path / "bin",
        installed={"jq": True},
        platform=_MAC,
        which=lambda c: f"/opt/homebrew/bin/{c}",
    )
    assert "found at /opt/homebrew/bin/jq" in rows[0].hint


def test_classify_absent_when_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rows = classify_tools([_dl("fd")], tmp_path / "bin", installed={"fd": False}, platform=_LINUX)
    assert rows[0].state == "absent"
    assert rows[0].selectable is False
    assert "not installed" in rows[0].hint


def test_classify_unavailable_when_no_method_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # A cask-only tool cannot install on Linux: no method applies -> unavailable.
    rows = classify_tools(
        [_cask("rectangle")], tmp_path / "bin", installed={"rectangle": False}, platform=_LINUX
    )
    assert rows[0].state == "unavailable"
    assert rows[0].selectable is False
    assert "not available on debian" in rows[0].hint


def test_classify_returns_a_row_per_tool_in_order() -> None:
    assert isinstance(ToolRow(_dl("a"), "absent", [], "h", False).tool, Tool)


# --- reverse_dependencies + reverse_deps warn-but-allow (Task A8) -----------


def _dep_tool(tool_id: str, *requires: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(Method(kind="node", params={"npm_pkg": f"@x/{tool_id}"}),),
        requires=tuple(requires),
    )


def test_reverse_dependencies_maps_dep_to_its_dependents() -> None:
    rev = reverse_dependencies(
        [_dep_tool("mmdc", "pnpm"), _dep_tool("other", "pnpm"), _dep_tool("pnpm")]
    )
    assert sorted(rev["pnpm"]) == ["mmdc", "other"]
    assert "mmdc" not in rev


def test_reverse_dependencies_empty_when_no_requires() -> None:
    assert reverse_dependencies([_dep_tool("a"), _dep_tool("b")]) == {}


def test_classify_appends_required_by_note_to_hint() -> None:
    pnpm = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://x"}),),
    )
    mmdc = _dep_tool("mmdc", "pnpm")
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    rows = classify_tools(
        [pnpm, mmdc],
        Path("/tmp/bin"),
        installed={"pnpm": True, "mmdc": False},
        platform=platform,
        which=lambda _cmd: None,
        reverse_deps={"pnpm": ["mmdc"]},
    )
    pnpm_row = next(r for r in rows if r.tool.id == "pnpm")
    mmdc_row = next(r for r in rows if r.tool.id == "mmdc")
    assert "required by mmdc" in pnpm_row.hint
    assert "required by" not in mmdc_row.hint


def test_classify_without_reverse_deps_leaves_hint_unchanged() -> None:
    pnpm = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://x"}),),
    )
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    rows = classify_tools(
        [pnpm],
        Path("/tmp/bin"),
        installed={"pnpm": True},
        platform=platform,
        which=lambda _cmd: None,
    )
    assert "required by" not in rows[0].hint


def _enabled_countdown(tmp_path: Path) -> tuple[Path, Path]:
    rc_path = tmp_path / ".myshellrc"
    bin_dir = tmp_path / ".local" / "bin"
    countdown = next(bundle for bundle in BUNDLES if bundle.id == "countdown")
    tweak_policy(countdown, rc_path=rc_path, bin_dir=bin_dir).apply()
    return rc_path, bin_dir


def test_active_tweak_ids_reports_an_enabled_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    assert "tweak:countdown" in active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir)
    assert (
        active_tweak_ids(BUNDLES, rc_path=tmp_path / "clean-rc", bin_dir=tmp_path / "clean-bin")
        == ()
    )


def test_sweep_tweaks_disables_every_active_tweak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    helper = bin_dir / "tools-installer-wait-time"
    assert helper.exists()
    assert "wait_time()" in rc_path.read_text()
    assert sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir) == SweepResult(
        swept=("tweak:countdown",)
    )
    assert "wait_time()" not in rc_path.read_text()
    assert not helper.exists()
    assert sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir) == SweepResult()


def _enabled_omz(
    tmp_path: Path, zshrc_text: str = "plugins=(z)\nsource omz\n"
) -> tuple[Path, Path, Path]:
    """Enable the Oh-My-Zsh policy for real, so the sweep sees a genuine record."""
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(zshrc_text)
    rc_path = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    omz_plugins_policy(zshrc_path=zshrc, state_path=rc_path, present=True).apply()
    return zshrc, rc_path, bin_dir


class _FakeDaemonRun:
    """Records every argv; never touches real launchctl. Can be told to fail
    the bootout call, to exercise a real removal failure during a sweep."""

    def __init__(self, *, fail_bootout: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._fail_bootout = fail_bootout

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        if self._fail_bootout and cmd[:2] == ["launchctl", "bootout"]:
            raise CommandError(cmd, 5)


def _enabled_daemon(tmp_path: Path, *, run: Callable[[list[str]], None] | None = None) -> Policy:
    """Enable the daemon policy for real (a real wrapper file on disk, a real
    plist), so the sweep sees a genuine artifact, not a mock."""
    script_path = tmp_path / "scripts" / "prune-user-tmpdir.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    policy = daemon_policy(
        plist_path=tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist",
        log_path=tmp_path / "Logs" / "prune-daemon.log",
        wrapper_bin_dir=tmp_path / ".local" / "bin",
        script_path=script_path,
        state_path=tmp_path / ".myshellrc",
        installed_tools={"fd": True, "rg": True},
        path_value="/usr/bin:/bin",
        tmpdir_value=str(tmp_path / "tmp"),
        home_value=str(tmp_path),
        uv_path=tmp_path / "uv",
        uid=501,
        run=run if run is not None else _FakeDaemonRun(),
    )
    policy.apply()
    # active=True is a construction-time snapshot on this frozen Policy; the
    # sweep never relies on it for the daemon (it calls is_active() instead,
    # per 11-REVIEWS.md cycle 2 finding #13), so returning this SAME instance
    # -- now that .apply() has written the real plist -- is correct either way.
    return policy


def test_active_tweak_ids_includes_the_daemon_policy_id_when_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    daemon = _enabled_daemon(tmp_path)
    ids = active_tweak_ids(
        BUNDLES, rc_path=tmp_path / ".myshellrc", bin_dir=tmp_path / "bin", daemon_policy=daemon
    )
    assert "daemon:prune-tmpdir" in ids


def test_sweep_tweaks_includes_an_active_daemon_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    daemon = _enabled_daemon(tmp_path)
    assert plist_path.exists()
    result = sweep_tweaks(
        BUNDLES, rc_path=tmp_path / ".myshellrc", bin_dir=tmp_path / "bin", daemon_policy=daemon
    )
    assert "daemon:prune-tmpdir" in result.swept
    assert not plist_path.exists()


def test_a_failing_daemon_removal_does_not_abort_the_rest_of_the_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    daemon = _enabled_daemon(tmp_path, run=_FakeDaemonRun(fail_bootout=True))
    result = sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, daemon_policy=daemon)
    assert result.failed == ("daemon:prune-tmpdir",)
    assert result.swept == ("tweak:countdown",)


def test_sweep_tweaks_also_removes_the_daemon_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression pin for 11-REVIEWS.md cycle 2 finding #16, resolved by
    daemon_policy.remove()'s own remove_wrapper call (11-02) -- no additional
    production code needed here."""
    monkeypatch.setenv("HOME", str(tmp_path))
    daemon = _enabled_daemon(tmp_path)
    wrapper = tmp_path / ".local" / "bin" / "tools-installer-prune-daemon"
    assert wrapper.exists()
    sweep_tweaks(
        BUNDLES, rc_path=tmp_path / ".myshellrc", bin_dir=tmp_path / "bin", daemon_policy=daemon
    )
    assert not wrapper.exists()


def test_sweep_tweaks_includes_the_omz_plugins_tweak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, rc_path, bin_dir = _enabled_omz(tmp_path)
    assert zshrc.read_text().startswith("plugins=(z git docker)\n")
    assert "omz-plugins" in active_tweak_ids(
        BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc
    )
    assert (
        "omz-plugins"
        in sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc).swept
    )
    assert zshrc.read_text().startswith("plugins=(z)\n")
    # Idempotent: the record is gone, so a second sweep reports and does nothing.
    assert "omz-plugins" not in active_tweak_ids(
        BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc
    )
    assert (
        sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc) == SweepResult()
    )


def test_sweep_leaves_a_hand_authored_plugins_array_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CR-01: `git` ships in Oh-My-Zsh's default .zshrc and `docker` is its
    # commonest addition, so a full uninstall must not read that array as ours.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = tmp_path / ".zshrc"
    hand_written = "plugins=(git docker kubectl)\nsource $ZSH/oh-my-zsh.sh\n"
    zshrc.write_text(hand_written)
    rc_path = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    assert active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc) == ()
    assert (
        sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc) == SweepResult()
    )
    assert zshrc.read_text() == hand_written


def test_sweep_removes_only_the_plugin_names_the_installer_added(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # The user already had `git`; only `docker` was ever ours.
    zshrc, rc_path, bin_dir = _enabled_omz(tmp_path, "plugins=(git kubectl)\nsource omz\n")
    assert zshrc.read_text() == "plugins=(git kubectl docker)\nsource omz\n"
    assert (
        "omz-plugins"
        in sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc).swept
    )
    assert zshrc.read_text() == "plugins=(git kubectl)\nsource omz\n"


def test_orphaned_executable_is_swept_without_its_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    helper = bin_dir / "tools-installer-wait-time"
    rc_path.write_text("# leftover user content\n")
    assert helper.exists()
    assert "tweak:countdown" in active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir)
    assert sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir) == SweepResult(
        swept=("tweak:countdown",)
    )
    assert not helper.exists()


def test_block_without_its_executable_is_still_swept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    helper = bin_dir / "tools-installer-wait-time"
    helper.unlink()
    assert "tweak:countdown" in active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir)
    assert sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir) == SweepResult(
        swept=("tweak:countdown",)
    )
    assert "wait_time()" not in rc_path.read_text()


def test_sweep_never_deletes_a_file_it_does_not_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path = tmp_path / ".myshellrc"
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    impostor = bin_dir / "tools-installer-wait-time"
    impostor_text = "user-owned helper"
    impostor.write_text(impostor_text)
    stranger = bin_dir / "my-script"
    stranger_text = "#!/bin/sh\necho hello\n"
    stranger.write_text(stranger_text)
    assert "tweak:countdown" not in active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir)
    assert sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir) == SweepResult()
    assert impostor.exists() and impostor.read_text() == impostor_text
    assert stranger.exists() and stranger.read_text() == stranger_text


def test_preview_equals_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("plugins=(z)\nsource $ZSH/oh-my-zsh.sh\n")
    omz_plugins_policy(zshrc_path=zshrc, state_path=rc_path, present=True).apply()
    previewed = active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc)
    swept = sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc)
    assert previewed == swept.swept
    assert swept.failed == ()
    assert "tweak:countdown" in previewed
    assert "omz-plugins" in previewed


def test_reported_ids_are_namespaced_policy_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Policies view addresses a bundle as `tweak:<id>`; the preview, the
    Uninstall row and the sweep must name the same object the same way, and the
    namespace is what stops a future bundle id colliding with a Policy id."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    zshrc, _rc, _bin = _enabled_omz(tmp_path)
    ids = active_tweak_ids(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc)
    countdown = next(bundle for bundle in BUNDLES if bundle.id == "countdown")
    assert tweak_policy(countdown, rc_path=rc_path, bin_dir=bin_dir).id in ids
    assert "countdown" not in ids
    # The .zshrc policy is deliberately un-namespaced: it is not a TweakBundle.
    assert "omz-plugins" in ids


def test_a_failing_bundle_does_not_abort_the_rest_of_the_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only bin dir or an immutable rc file raises OSError. Letting the
    first one propagate abandoned every later bundle and the .zshrc arm after
    it, leaving a half-torn-down machine with no record of what had gone."""
    from installer import policy as policy_module

    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("plugins=(z)\nsource omz\n")
    omz_plugins_policy(zshrc_path=zshrc, state_path=rc_path, present=True).apply()
    real_remove = policy_module.remove_tweak

    def boom(bundle: TweakBundle, path: Path) -> None:
        if bundle.id == "countdown":
            raise OSError("read-only file system")
        real_remove(bundle, path)

    monkeypatch.setattr(policy_module, "remove_tweak", boom)
    result = sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc)
    assert result.failed == ("tweak:countdown",)
    # The .zshrc arm runs last, so it is the one a propagating error skipped —
    # and it is the only arm that touches a file the user owns.
    assert result.swept == ("omz-plugins",)
    assert zshrc.read_text() == "plugins=(z)\nsource omz\n"


def _extra(policy_id: str, *, active: bool) -> Policy:
    from installer.policy import PolicyResult

    state = {"active": active}

    def is_active() -> bool:
        return state["active"]

    def remove() -> PolicyResult:
        state["active"] = False
        return PolicyResult(layers=(), reload_hint=None, warning=None)

    return Policy(
        id=policy_id,
        label=policy_id,
        description="",
        active=active,
        apply=remove,
        remove=remove,
        is_active=is_active,
    )


def test_active_policies_appends_a_live_extra_and_skips_an_inactive_one(tmp_path: Path) -> None:
    from installer.uninstall import active_policies

    live = _extra("cache-redirect:bun", active=True)
    quiet = _extra("cache-redirect:other", active=False)
    policies = active_policies(
        (),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / "bin",
        extra_policies=(live, quiet),
    )
    assert policies == [live]


def test_active_tweak_ids_names_the_extra_policy(tmp_path: Path) -> None:
    ids = active_tweak_ids(
        (),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / "bin",
        extra_policies=(_extra("cache-redirect:bun", active=True),),
    )
    assert ids == ("cache-redirect:bun",)


def test_sweep_tweaks_disables_an_extra_policy_and_isolates_its_failure(tmp_path: Path) -> None:
    from installer.policy import PolicyResult
    from installer.run import CommandError

    live = _extra("cache-redirect:bun", active=True)

    def boom() -> PolicyResult:
        raise CommandError(["rm"], 1)

    failed = Policy(
        id="cache-redirect:broken",
        label="broken",
        description="",
        active=True,
        apply=boom,
        remove=boom,
        is_active=lambda: True,
    )
    result = sweep_tweaks(
        (),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / "bin",
        extra_policies=(failed, live),
    )
    assert result.failed == ("cache-redirect:broken",)
    assert result.swept == ("cache-redirect:bun",)
    assert live.is_active is not None
    assert live.is_active() is False


def test_empty_extra_policies_leaves_the_sweep_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path, bin_dir = _enabled_countdown(tmp_path)
    result = sweep_tweaks(BUNDLES, rc_path=rc_path, bin_dir=bin_dir, extra_policies=())
    assert result == SweepResult(swept=("tweak:countdown",))


def _uninstall_console() -> tuple[Console, StringIO]:
    """A rich Console writing to a StringIO, for the CLI-path tests."""
    buf = StringIO()
    return Console(file=buf, width=100, no_color=True), buf


def test_tui_and_cli_delete_the_same_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The prohibition: --yes must never delete what the TUI would refuse."""
    from installer.app import run_uninstall

    tui_home = tmp_path / "tui"
    cli_home = tmp_path / "cli"
    tui_home.mkdir()
    cli_home.mkdir()

    monkeypatch.setattr(Path, "home", lambda: tui_home)
    tui_tools = plant_removal_fixtures(tui_home)
    rows = classify_tools(
        tui_tools,
        tui_home / ".local" / "bin",
        installed={t.id: True for t in tui_tools},
        platform=_LINUX,
    )
    tui_set = {p for row in rows if row.state == "removable" for p in row.paths}
    assert tui_set

    monkeypatch.setattr(Path, "home", lambda: cli_home)
    cli_tools = plant_removal_fixtures(cli_home)
    cli_bin = cli_home / ".local" / "bin"
    console, _buf = _uninstall_console()
    removed = run_uninstall(
        cli_tools,
        console,
        default_bin_dir=cli_bin,
        myshellrc_path=cli_home / ".myshellrc",
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=cli_home / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert {p.relative_to(cli_home) for p in removed} == {p.relative_to(tui_home) for p in tui_set}


def test_failed_opt_dir_delete_leaves_the_remainder_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backstop: if deleting the opt dir fails after the link was removed,
    the remainder is still listed on the next plan."""
    import installer.uninstall as uninstall_module

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    tool = _dl_tool("fd", "fd")
    assert plan_removal([tool], bin_dir).removable == (bin_dir / "fd", opt)

    real_rmtree = uninstall_module.shutil.rmtree

    def failing_rmtree(path: object, **_kwargs: object) -> None:
        if path == opt:
            raise OSError("disk gremlins")
        real_rmtree(path)  # type: ignore[arg-type]

    monkeypatch.setattr(uninstall_module.shutil, "rmtree", failing_rmtree)
    with pytest.raises(OSError):
        remove_paths([bin_dir / "fd", opt])
    monkeypatch.setattr(uninstall_module.shutil, "rmtree", real_rmtree)

    plan = plan_removal([tool], bin_dir)
    assert plan.removable == ()
    assert opt in plan.yourself
    rows = classify_tools([tool], bin_dir, installed={"fd": True}, platform=_LINUX)
    assert rows[0].state == "managed"
    assert str(opt) in rows[0].hint


def test_plan_uninstall_lists_exactly_the_existing_artifact_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """plan_uninstall reads download.artifact_paths (D-07): a raw method
    creates a file, never an opt dir, so a stray ~/.local/opt/<name> beside
    a raw tool is no longer listed."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rg_opt = tmp_path / ".local" / "opt" / "rg"
    rg_opt.mkdir(parents=True)
    (rg_opt / "rg").write_text("binary")
    (bin_dir / "rg").symlink_to(rg_opt / "rg")
    (bin_dir / "yq").write_text("binary")
    # The stray opt dir a raw tool must NOT claim:
    (tmp_path / ".local" / "opt" / "yq").mkdir(parents=True)
    (bin_dir / "gone").symlink_to(tmp_path / "nowhere")  # dangling link
    (tmp_path / "Applications" / "Demo.app").mkdir(parents=True)
    archive = _tool(
        Method(kind="github_release", params={"repo": "a/rg", "asset": "x", "member": "rg"}),
        tool_id="rg",
    )
    raw = _tool(
        Method(
            kind="github_release",
            params={
                "repo": "a/yq",
                "asset": "yq",
                "member": "yq_linux",
                "bin_name": "yq",
                "raw": True,
            },
        ),
        tool_id="yq",
    )
    dangling = _dl_tool("gone", "gone")
    app = _tool(
        Method(kind="app", params={"url": "https://x/a.zip", "app": "Demo.app"}), tool_id="app"
    )
    assert plan_uninstall([archive, raw, dangling, app], bin_dir) == [
        rg_opt,
        bin_dir / "rg",
        bin_dir / "yq",
        bin_dir / "gone",
        tmp_path / "Applications" / "Demo.app",
    ]


def test_plan_removal_never_proves_a_raw_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The layout proof is for archive links only: a raw github_release file
    at ~/.local/bin/yq lands in `yourself`, never in `removable`."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "yq").write_text("binary")
    raw = _tool(
        Method(
            kind="github_release",
            params={
                "repo": "a/yq",
                "asset": "yq",
                "member": "yq_linux",
                "bin_name": "yq",
                "raw": True,
            },
        ),
        tool_id="yq",
    )
    plan = plan_removal([raw], bin_dir)
    assert plan.removable == ()
    assert plan.yourself == (bin_dir / "yq",)


def test_plan_removal_still_proves_an_archive_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "rg"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "rg").write_text("binary")
    (bin_dir / "rg").symlink_to(opt / "rg")
    archive = _tool(
        Method(kind="github_release", params={"repo": "a/rg", "asset": "x", "member": "rg"}),
        tool_id="rg",
    )
    plan = plan_removal([archive], bin_dir)
    assert plan.removable == (bin_dir / "rg", opt)
    assert plan.yourself == ()
