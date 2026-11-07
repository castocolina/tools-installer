import json
import os
from collections.abc import Callable, Sequence
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from installer import receipts
from installer.download import artifact_paths, link_name
from installer.enums import UninstallState
from installer.model import Method, Tool
from installer.policy import Policy, daemon_policy, omz_plugins_policy, tweak_policy
from installer.receipts import Receipt, ReceiptMethod
from installer.run import CommandError
from installer.tweaks import BUNDLES, TweakBundle
from installer.uninstall import (
    RemovalPlan,
    SweepResult,
    active_tweak_ids,
    manager_name,
    plan_removal,
    plan_uninstall,
    removal_plan,
    remove_paths,
    remove_proven,
    sweep_tweaks,
)
from installer.version_status import (
    LAYOUT_PROOF_NOTE,
    RECEIPT_PROOF_NOTE,
    ToolState,
    uninstall_detail,
    uninstall_group,
)
from tests.state_doubles import pass_state


def _no_removal_runner(cmd: list[str]) -> None:
    raise AssertionError(f"no removal command expected: {cmd}")


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
    every caller: UninstallScreen, run_uninstall) standing,
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


def _removal_state(tool: Tool, plan: RemovalPlan, *, receipt: Receipt | None = None) -> ToolState:
    """The published state of an installed `tool` whose removal proof is `plan`."""
    return pass_state(tool, platform=_LINUX, present=True, removable=plan, receipt=receipt)


def test_uninstall_group_follows_the_removal_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    by_id = {tool.id: tool for tool in tools}

    def state_of(tool_id: str) -> ToolState:
        tool = by_id[tool_id]
        return _removal_state(tool, plan_removal([tool], bin_dir))

    fd = state_of("fd")
    assert uninstall_group(fd) == UninstallState.REMOVABLE
    assert fd.removable.removable == (bin_dir / "fd", tmp_path / ".local" / "opt" / "fd")
    assert uninstall_detail(by_id["fd"], fd) == LAYOUT_PROOF_NOTE
    for tool_id in ("ruff", "yq", "drawio-desktop"):
        state = state_of(tool_id)
        detail = uninstall_detail(by_id[tool_id], state)
        assert uninstall_group(state) == UninstallState.MANAGED, tool_id
        assert state.removable.removable == (), tool_id
        assert "remove it yourself:" in detail, tool_id
    assert str(bin_dir / "ruff") in uninstall_detail(by_id["ruff"], state_of("ruff"))
    assert str(bin_dir / "drawio") in uninstall_detail(
        by_id["drawio-desktop"], state_of("drawio-desktop")
    )


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
    artifacts = [
        receipts.fingerprint(opt, "dir", key="fd"),
        receipts.fingerprint(link, "link"),
        receipts.fingerprint(dangling, "link"),
        receipts.fingerprint(plain, "file"),
    ]
    assert all(artifact is not None for artifact in artifacts)
    refused = remove_paths([artifact for artifact in artifacts if artifact is not None])
    assert refused == ()
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


def test_remove_paths_refuses_a_missing_artifact(tmp_path: Path):
    """An artifact whose path is gone is refused, never silently skipped.

    The authorized artifact is the only thing that may be deleted, and a path
    that no longer matches it (here: it is gone) is returned, not touched.
    """
    absent = tmp_path / "never_created"
    artifact = receipts.ReceiptArtifact(path=absent, type="file")
    assert remove_paths([artifact]) == (absent,)


def test_plan_skips_traversal_binname(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    # member ".." would make binname "..", resolving opt/bin paths up to ~/.local.
    tool = _tool(
        Method(kind="github_release", params={"repo": "a/x", "asset": "x", "member": ".."})
    )
    assert plan_uninstall([tool], bin_dir) == []


def test_remove_paths_unlinks_only_what_its_type_authorizes(tmp_path: Path) -> None:
    """The authorized type picks the operation, never what the path is now (G1).

    A file, a link and a dir that no longer match their artifact are refused
    with their contents intact; a still-matching file, link and dir are
    removed, and a link's target survives.
    """

    def swap_for_dir(path: Path) -> Path:
        sibling = path.with_name(path.name + ".new")
        sibling.mkdir()
        (sibling / "decoy").write_text("not ours")
        if path.is_dir() and not path.is_symlink():
            for child in path.iterdir():
                child.rename(sibling / child.name)
            path.rmdir()
        else:
            path.unlink()
        sibling.rename(path)
        decoy = path / "decoy"
        decoy.write_text("not ours")
        return decoy

    file_path = tmp_path / "file"
    file_path.write_text("plain")
    file_artifact = receipts.fingerprint(file_path, "file")
    file_decoy = swap_for_dir(file_path)

    link_path = tmp_path / "link"
    link_path.symlink_to(tmp_path / "nowhere")
    link_artifact = receipts.fingerprint(link_path, "link")
    link_decoy = swap_for_dir(link_path)

    dir_path = tmp_path / "dir"
    dir_path.mkdir()
    (dir_path / "member").write_text("inside")
    dir_artifact = receipts.fingerprint(dir_path, "dir", key="member")
    dir_decoy = swap_for_dir(dir_path)
    (dir_path / "member").write_text("rebuilt")

    assert file_artifact is not None
    assert link_artifact is not None
    assert dir_artifact is not None
    refused = remove_paths([file_artifact, link_artifact, dir_artifact])
    assert set(refused) == {file_path, link_path, dir_path}
    assert file_decoy.read_text() == "not ours"
    assert link_decoy.read_text() == "not ours"
    assert dir_decoy.read_text() == "not ours"

    kept_file = tmp_path / "kept-file"
    kept_file.write_text("keep me gone")
    target = tmp_path / "target"
    target.write_text("survives")
    kept_link = tmp_path / "kept-link"
    kept_link.symlink_to(target)
    kept_dir = tmp_path / "kept-dir"
    kept_dir.mkdir()
    (kept_dir / "gone").write_text("inside")
    kept = [
        receipts.fingerprint(kept_file, "file"),
        receipts.fingerprint(kept_link, "link"),
        receipts.fingerprint(kept_dir, "dir", key="gone"),
    ]
    assert all(artifact is not None for artifact in kept)
    assert remove_paths([artifact for artifact in kept if artifact is not None]) == ()
    assert not kept_file.exists()
    assert not kept_link.is_symlink()
    assert not kept_dir.exists()
    assert target.read_text() == "survives"


def test_remove_paths_unlinks_symlink_to_dir_without_deleting_target(tmp_path: Path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "keep").write_text("important")
    link = tmp_path / "link"
    link.symlink_to(target_dir)  # symlink to a DIRECTORY
    link_artifact = receipts.fingerprint(link, "link")
    assert link_artifact is not None
    assert remove_paths([link_artifact]) == ()
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


# --- reverse dependencies (Phase 3) ---------------------------------------

from installer.platform import Platform  # noqa: E402
from installer.uninstall import reverse_dependencies  # noqa: E402

_LINUX = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
_MAC = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


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
    tui_set = set(plan_removal(tui_tools, tui_home / ".local" / "bin").removable)
    assert tui_set

    monkeypatch.setattr(Path, "home", lambda: cli_home)
    cli_tools = plant_removal_fixtures(cli_home)
    cli_bin = cli_home / ".local" / "bin"
    console, _buf = _uninstall_console()
    removed, _failed = run_uninstall(
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
        runner=_no_removal_runner,
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
        # 19-33: the dir is deleted at its captured quarantine path, not at its
        # original name, so the injected failure fires there. The remover puts
        # the remainder back before re-raising, which is what the assertions
        # below pin.
        if Path(str(path)).name.endswith(".tools-installer.rm"):
            raise OSError("disk gremlins")
        real_rmtree(path)  # type: ignore[arg-type]

    monkeypatch.setattr(uninstall_module.shutil, "rmtree", failing_rmtree)
    link_artifact = receipts.fingerprint(bin_dir / "fd", "link")
    dir_artifact = receipts.fingerprint(opt, "dir", key="fd")
    assert link_artifact is not None and dir_artifact is not None
    with pytest.raises(OSError):
        remove_paths([link_artifact, dir_artifact])
    monkeypatch.setattr(uninstall_module.shutil, "rmtree", real_rmtree)

    plan = plan_removal([tool], bin_dir)
    assert plan.removable == ()
    assert opt in plan.yourself
    state = _removal_state(tool, plan)
    assert uninstall_group(state) == UninstallState.MANAGED
    assert str(opt) in uninstall_detail(tool, state)


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


# --- receipt proof: receipt ∩ artifact_paths (D-10, L-19-06) ----------------


def _raw_yq_tool() -> Tool:
    """A raw-download yq: the formula names `<bin>/yq` as a plain file, so no
    archive layout can ever prove it."""
    return _tool(
        Method(
            kind="github_release",
            params={"repo": "a/yq", "asset": "yq", "member": "yq", "raw": True},
        ),
        tool_id="yq",
        cmd="yq",
    )


def write_receipt(
    tool: Tool,
    artifacts: list[tuple[Path, str]],
    *,
    kind: str = "github_release",
    dir_key: str | None = None,
) -> None:
    """Write a receipt for `tool` fingerprinting each (path, type) as it is now.

    Public: tests/test_app.py builds its CLI receipts with it. The receipts
    dir is the conftest sandbox, never the real HOME. A dir is keyed by
    `dir_key` when given, else by Info.plist for an app, else by the member
    the first link in the list points to."""
    link = next((path for path, artifact_type in artifacts if artifact_type == "link"), None)
    recorded: list[receipts.ReceiptArtifact] = []
    for path, artifact_type in artifacts:
        assert artifact_type in ("dir", "link", "file")
        key: str | None = None
        if artifact_type == "dir":
            if dir_key is not None:
                key = dir_key
            elif kind == "app":
                key = receipts.APP_KEY_FILE
            elif link is not None:
                key = receipts.link_key(path, link)
        artifact = receipts.fingerprint(path, artifact_type, key=key)
        assert artifact is not None, path
        recorded.append(artifact)
    receipts.write(
        Receipt(
            tool=tool.id,
            at="2026-10-16T00:00:00Z",
            method=ReceiptMethod(kind=kind, key="k"),
            package=None,
            artifacts=tuple(recorded),
            smoke=None,
            hooks={},
        )
    )


def plant_raw_yq(home: Path, *, with_receipt: bool = True) -> tuple[Tool, Path]:
    """Plant yq as a raw file at HOME/.local/bin/yq, with a matching receipt.

    Public: tests/test_app.py drives the CLI over the same tree."""
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "yq").write_text("yq raw binary")
    tool = _raw_yq_tool()
    if with_receipt:
        write_receipt(tool, [(bin_dir / "yq", "file")])
    return tool, bin_dir


def _plant_rg(home: Path) -> tuple[Tool, Path, Path]:
    bin_dir = home / ".local" / "bin"
    opt = home / ".local" / "opt" / "rg"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    (opt / "rg").write_text("rg binary")
    (bin_dir / "rg").symlink_to(opt / "rg")
    return _dl_tool("rg", "rg"), bin_dir, opt


def _plant_fd(home: Path) -> tuple[Tool, Path, Path]:
    """A layout-proven archive fd: a bin link into its own opt dir, no receipt."""
    bin_dir = home / ".local" / "bin"
    opt = home / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    (opt / "fd").write_text("fd binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    return _dl_tool("fd", "fd"), bin_dir, opt


def test_receipt_proves_a_raw_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    plan = plan_removal([yq], bin_dir)
    assert plan.removable == (bin_dir / "yq",)
    assert plan.by_tool == {"yq": (bin_dir / "yq",)}
    assert plan.yourself == ()


def test_tampered_receipt_path_is_never_removable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """19-RESEARCH Pitfall 8: the receipt is user-writable JSON, so a path it
    names outside artifact_paths is never removable, even with a correct sha256."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = tmp_path / ".ssh" / "id_ed25519"
    key.parent.mkdir(parents=True)
    key.write_text("PRIVATE KEY")
    yq, bin_dir = plant_raw_yq(tmp_path, with_receipt=False)
    write_receipt(yq, [(bin_dir / "yq", "file"), (key, "file")])
    plan = plan_removal([yq], bin_dir, verify=True)
    assert key not in plan.removable
    assert all(key not in paths for paths in plan.by_tool.values())
    assert plan.removable == (bin_dir / "yq",)


def test_drifted_receipt_makes_the_tool_unremovable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    (bin_dir / "yq").write_text("rewritten after install, a different size")
    plan = plan_removal([yq], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert plan.yourself == (bin_dir / "yq",)


def test_changed_link_target_makes_the_tool_unremovable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP SC3: a relinked bin link drifts the receipt; a valid receipt
    beats the layout proof (L-19-14), which alone would accept the new target."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rg, bin_dir, opt = _plant_rg(tmp_path)
    write_receipt(rg, [(opt, "dir"), (bin_dir / "rg", "link")])
    assert plan_removal([rg], bin_dir).removable == (opt, bin_dir / "rg")
    (opt / "other").write_text("another binary in its own opt dir")
    (bin_dir / "rg").unlink()
    (bin_dir / "rg").symlink_to(opt / "other")
    plan = plan_removal([rg], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    (bin_dir / "rg").unlink()
    (bin_dir / "rg").symlink_to(opt / "rg")
    assert plan_removal([rg], bin_dir).by_tool == {"rg": (opt, bin_dir / "rg")}


def test_corrupt_receipt_is_unproven_without_layout_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rg, bin_dir, opt = _plant_rg(tmp_path)
    path = receipts.receipt_path("rg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{")
    plan = plan_removal([rg], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert set(plan.yourself) == {opt, bin_dir / "rg"}


def test_no_receipt_keeps_the_layout_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rg, bin_dir, opt = _plant_rg(tmp_path)
    plan = plan_removal([rg], bin_dir)
    assert plan.removable == (bin_dir / "rg", opt)
    assert plan.by_tool == {}


def test_plan_removal_keeps_each_proven_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The type that proved a path travels with it (G1): a receipt-proven raw
    file keeps its receipt artifact, and a layout-proven archive pair keeps
    the link and the dir fingerprinted at proof time."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    receipt = receipts.read("yq")
    assert receipt is not None
    plan = plan_removal([yq], bin_dir)
    assert plan.artifacts == {bin_dir / "yq": receipt.artifacts[0]}
    assert set(plan.artifacts) == set(plan.removable)

    rg, rg_bin, opt = _plant_rg(tmp_path)
    layout = plan_removal([rg], rg_bin)
    link = receipts.fingerprint(rg_bin / "rg", "link")
    directory = receipts.fingerprint(opt, "dir", key="rg")
    assert link is not None and directory is not None
    assert layout.artifacts == {rg_bin / "rg": link, opt: directory}
    assert set(layout.artifacts) == set(layout.removable)


def test_receiptless_raw_binary_is_not_removable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C2-M2: with its receipt gone (19-09 deletes it after a failed
    rewrite), a raw binary is unproven, since no archive layout proves it."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path, with_receipt=False)
    plan = plan_removal([yq], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert plan.yourself == (bin_dir / "yq",)


def test_receipt_of_another_kind_proves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path, with_receipt=False)
    write_receipt(yq, [(bin_dir / "yq", "file")], kind="tarball")
    plan = plan_removal([yq], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert plan.yourself == (bin_dir / "yq",)


def test_uninstall_group_uses_the_receipt_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    receipt = receipts.read(yq.id)
    state = _removal_state(yq, plan_removal([yq], bin_dir), receipt=receipt)
    assert uninstall_group(state) == UninstallState.REMOVABLE
    assert state.removable.removable == (bin_dir / "yq",)
    assert uninstall_detail(yq, state) == RECEIPT_PROOF_NOTE
    (bin_dir / "yq").write_text("rewritten after install, a different size")
    state = _removal_state(yq, plan_removal([yq], bin_dir), receipt=receipt)
    assert uninstall_group(state) == UninstallState.MANAGED
    assert f"remove it yourself: {bin_dir / 'yq'}" in uninstall_detail(yq, state)


def _plant_retyped_yq(home: Path) -> tuple[Tool, Path, Path]:
    """A directory where the raw yq file belongs, with a receipt typing it "dir".

    The remover test re-uses it. `matches` accepts the dir (it is a real
    directory), so only the (path, kind) pair check keeps it out of rmtree."""
    bin_dir = home / ".local" / "bin"
    (bin_dir / "yq").mkdir(parents=True)
    decoy = bin_dir / "yq" / "decoy"
    decoy.write_text("not ours")
    yq = _raw_yq_tool()
    write_receipt(yq, [(bin_dir / "yq", "dir")], dir_key="decoy")
    return yq, bin_dir, decoy


def test_receipt_type_cannot_turn_a_file_path_into_a_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir, decoy = _plant_retyped_yq(tmp_path)
    plan = plan_removal([yq], bin_dir, verify=True)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert decoy.read_text() == "not ours"


def test_drifted_receipt_artifact_outside_the_authorized_set_blocks_the_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review H7: drift is checked over every receipt artifact BEFORE the
    intersection, so drift outside artifact_paths still blocks the tool."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    extra = tmp_path / ".local" / "share" / "yq-extra"
    extra.parent.mkdir(parents=True)
    extra.write_text("recorded")
    yq, bin_dir = plant_raw_yq(tmp_path, with_receipt=False)
    write_receipt(yq, [(bin_dir / "yq", "file"), (extra, "file")])
    extra.write_text("changed since, a different size")
    plan = plan_removal([yq], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}


# --- remove_proven: one remover, re-proven with a re-hash (D-08) ------------


def test_remove_proven_removes_and_deletes_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    removed, refused = remove_proven([yq], [bin_dir / "yq"], bin_dir)
    assert removed == (bin_dir / "yq",)
    assert refused == ()
    assert not (bin_dir / "yq").exists()
    assert receipts.read("yq") is None
    assert not receipts.receipt_path("yq").exists()


def test_remove_proven_rehashes_before_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bytes swapped in place with size and mtime restored pass the stat
    shortcut; only the deletion-time re-hash catches them."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    target = bin_dir / "yq"
    st = target.stat()
    target.write_text("YQ RAW BINARY")  # same length as the recorded bytes
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert plan_removal([yq], bin_dir).removable == (target,)
    removed, refused = remove_proven([yq], [target], bin_dir)
    assert removed == ()
    assert refused == (f"changed since the preview; not removed: {target}",)
    assert target.read_text() == "YQ RAW BINARY"
    assert receipts.read("yq") is not None


def test_remove_proven_rehashes_a_file_swapped_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR-02/T-19-108: re-hash at deletion time, even after the fresh plan.

    Same-length bytes with the recorded mtime restored pass the stat shortcut.
    They must remain on disk and retain their receipt when substituted after
    `plan_removal(verify=True)` has already returned.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    target = bin_dir / "yq"
    st = target.stat()

    def mutate() -> None:
        target.write_text("YQ RAW BINARY")
        os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))

    _after_verified_plan(monkeypatch, mutate)
    removed, refused = remove_proven([yq], [target], bin_dir)

    assert removed == ()
    assert refused == (f"changed since the preview; not removed: {target}",)
    assert target.read_text() == "YQ RAW BINARY"
    assert receipts.read("yq") is not None


def test_remove_proven_keeps_the_receipt_when_a_delete_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)

    def boom(artifacts: list[receipts.ReceiptArtifact]) -> None:
        raise OSError(f"read-only: {artifacts[0].path}")

    monkeypatch.setattr("installer.uninstall.remove_paths", boom)
    with pytest.raises(OSError, match="read-only"):
        remove_proven([yq], [bin_dir / "yq"], bin_dir)
    assert (bin_dir / "yq").exists()
    assert receipts.read("yq") is not None


def test_remove_proven_layout_tool_has_no_receipt_to_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rg, bin_dir, opt = _plant_rg(tmp_path)
    removed, refused = remove_proven([rg], [bin_dir / "rg", opt], bin_dir)
    assert removed == (bin_dir / "rg", opt)
    assert refused == ()
    assert not (bin_dir / "rg").is_symlink()
    assert not opt.exists()


def _after_verified_plan(monkeypatch: pytest.MonkeyPatch, mutate: Callable[[], None]) -> None:
    """Wrap plan_removal so `mutate` runs once the deletion-time proof returns.

    Only the `verify=True` call is the deletion-time proof; a preview-time call
    passes through untouched, so the race is injected deterministically.
    """
    real = plan_removal

    def wrapped(tools: list[Tool], default_bin_dir: Path, *, verify: bool = False) -> object:
        plan = real(tools, default_bin_dir, verify=verify)
        if verify:
            mutate()
        return plan

    monkeypatch.setattr("installer.uninstall.plan_removal", wrapped)


def test_remove_proven_refuses_a_file_replaced_by_a_dir_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt-proven raw file swapped for a directory after the deletion-time
    proof is refused, never recursively deleted, and its receipt survives (G1)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    target = bin_dir / "yq"

    def replace_with_dir() -> None:
        target.unlink()
        target.mkdir()
        (target / "decoy").write_text("not ours")

    _after_verified_plan(monkeypatch, replace_with_dir)
    removed, refused = remove_proven([yq], [target], bin_dir)
    assert removed == ()
    assert refused == (f"changed since the preview; not removed: {target}",)
    assert (target / "decoy").read_text() == "not ours"
    assert receipts.receipt_path("yq").exists()


def test_remove_proven_refuses_a_dir_recreated_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A layout-proven opt dir re-created after the deletion-time proof is
    refused and its new contents survive; the still-matching link is removed."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    link = bin_dir / "fd"

    def recreate_opt() -> None:
        _recreate_over(opt)
        (opt / "fd").write_text("vendor reinstall build")
        (opt / "decoy").write_text("vendor reinstall")

    _after_verified_plan(monkeypatch, recreate_opt)
    removed, refused = remove_proven([fd], [link, opt], bin_dir)
    assert removed == (link,)
    assert refused == (f"changed since the preview; not removed: {opt}",)
    assert not link.is_symlink()
    assert (opt / "decoy").read_text() == "vendor reinstall"


def test_remove_proven_refuses_a_retyped_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir, decoy = _plant_retyped_yq(tmp_path)

    def no_rmtree(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("rmtree must not run on a retyped artifact")

    monkeypatch.setattr("shutil.rmtree", no_rmtree)
    removed, refused = remove_proven([yq], [bin_dir / "yq"], bin_dir)
    assert removed == ()
    assert refused == (f"changed since the preview; not removed: {bin_dir / 'yq'}",)
    assert (bin_dir / "yq").is_dir()
    assert decoy.read_text() == "not ours"


# --- 19-32 Task 1: a changed key file drops the proof; identical bytes keep it --


def _recreate_over(original: Path) -> None:
    """Put a new directory at the same path, keeping the original's contents."""
    sibling = original.with_name(original.name + ".new")
    sibling.mkdir()
    for child in original.iterdir():
        child.rename(sibling / child.name)
    original.rmdir()
    sibling.rename(original)


def _plant_receipt_dir(tmp_path: Path, shape: str) -> tuple[Tool, Path, Path, Path]:
    """An archive or app fixture with a receipt, and the directory its key file lives in."""
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    if shape == "archive":
        tool, _, directory = _plant_rg(tmp_path)
        link = bin_dir / "rg"
        kind = "github_release"
    else:
        directory = tmp_path / "Applications" / "Demo.app"
        (directory / "Contents" / "MacOS").mkdir(parents=True)
        (directory / "Contents" / "MacOS" / "demo").write_text("demo binary")
        (directory / "Contents" / "Info.plist").write_text("<plist>vendor</plist>")
        link = bin_dir / "demo"
        link.symlink_to(directory / "Contents" / "MacOS" / "demo")
        tool = _tool(
            Method(
                kind="app",
                params={
                    "url": "https://example.test/a.zip",
                    "app": "Demo.app",
                    "cli": "Contents/MacOS/demo",
                },
            ),
            tool_id="demo",
            cmd="demo",
        )
        kind = "app"
    write_receipt(tool, [(directory, "dir"), (link, "link")], kind=kind)
    return tool, bin_dir, directory, link


@pytest.mark.parametrize("shape", ["archive", "app"])
def test_replaced_dir_artifact_is_not_removable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """A vendor reinstall whose key file changed is not removable (L-19-31).

    The link's target string is unchanged; the rewritten key file drops the
    whole tool's proof, and the directory stays."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool, bin_dir, directory, _link = _plant_receipt_dir(tmp_path, shape)
    assert plan_removal([tool], bin_dir).removable

    _recreate_over(directory)
    if shape == "archive":
        (directory / "rg").write_text("rg hand-built")
    else:
        (directory / "Contents" / "Info.plist").write_text("<plist>vendor 2</plist>")
    plan = plan_removal([tool], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert directory.is_dir()


@pytest.mark.parametrize("shape", ["archive", "app"])
def test_dir_recreated_with_the_same_key_file_stays_removable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """Identical key-file bytes are the same software (L-19-31): a reboot or
    remount never drops the proof, so the directory and its link stay removable."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool, bin_dir, directory, link = _plant_receipt_dir(tmp_path, shape)
    _recreate_over(directory)
    assert set(plan_removal([tool], bin_dir).removable) == {directory, link}


# --- 19-22 Task 2: a NUL artifact path never aborts a removal (G5) ----------


def test_nul_receipt_path_never_aborts_plan_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt whose artifact path embeds a NUL reads as unproven, not a crash."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "yq").write_text("yq raw binary")
    path = receipts.receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "v": 1,
                "tool": "yq",
                "at": "2026-10-16T00:00:00Z",
                "method": {"kind": "github_release", "key": "k"},
                "package": None,
                "artifacts": [
                    {
                        "path": "/tmp/x\u0000y",
                        "type": "file",
                        "sha256": "b" * 64,
                        "size": 3,
                        "mtime_ns": 1,
                    }
                ],
                "smoke": None,
                "hooks": {},
            }
        ),
        encoding="utf-8",
    )
    plan = plan_removal([_raw_yq_tool()], bin_dir)
    assert plan.removable == ()
    assert plan.yourself == (bin_dir / "yq",)


# --- 19-29 Task 1: an unreadable receipts dir never aborts removal (G23) ---


def test_inaccessible_receipts_dir_never_aborts_plan_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A layout-provable archive with no receipt stays unproven when the
    receipts dir cannot be searched: no crash, and no layout fallback."""
    from tests.test_receipts import deny_receipts_dir

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rg, bin_dir, opt = _plant_rg(tmp_path)
    deny_receipts_dir(monkeypatch)
    plan = plan_removal([rg], bin_dir)
    assert plan.removable == ()
    assert plan.by_tool == {}
    assert set(plan.yourself) == {opt, bin_dir / "rg"}


# --- 19-33 Task 1: a proven dir is captured by rename, re-verified, deleted ---


_QUARANTINE_SUFFIX = ".tools-installer.rm"


def _swap_dir_after_final_check(
    monkeypatch: pytest.MonkeyPatch,
    opt: Path,
    aside: Path,
    *,
    occupy_after_capture: bool,
) -> None:
    """Plant a vendor build at `opt` the moment its final proof returns.

    The race is injected deterministically by wrapping `receipts.matches`:
    the swap runs on the first call whose artifact IS `opt`, after that call's
    real verdict, so the tree the remover believes it verified is already
    elsewhere. `opt` holds the vendor's reinstall (`fd`, `decoy`) and `aside`
    the tree that was proven. With `occupy_after_capture`, `opt` is re-created
    a second time — on the call that re-checks the captured quarantine — so
    the put-back cannot succeed.
    """
    real = receipts.matches
    swapped = False
    occupied = False

    def build_vendor_tree() -> None:
        opt.rename(aside)
        opt.mkdir()
        (opt / "fd").write_text("vendor build")
        (opt / "decoy").write_text("vendor reinstall")

    def wrapper(
        candidate: receipts.ReceiptArtifact, *, rehash: bool = False, trees: Sequence[Path] = ()
    ) -> bool:
        nonlocal swapped, occupied
        if (
            occupy_after_capture
            and candidate.path.name.endswith(_QUARANTINE_SUFFIX)
            and not occupied
        ):
            occupied = True
            opt.mkdir()
            (opt / "newest").write_text("third copy")
        verdict = real(candidate, rehash=rehash, trees=trees)
        if candidate.path == opt and not swapped:
            swapped = True
            build_vendor_tree()
        return verdict

    monkeypatch.setattr(receipts, "matches", wrapper)


def test_remove_paths_refuses_a_dir_replaced_after_its_final_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR-01/T-19-107: the tree deleted must be the tree that was verified.

    A vendor updater that swaps the opt dir between the last proof and the
    recursive delete gets its own new tree back: the remover captures the
    directory by an exclusive rename, re-verifies the key file inside the
    captured tree, and refuses without deleting anything."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    artifact = plan_removal([fd], bin_dir, verify=True).artifacts[opt]
    aside = tmp_path / "verified-fd"
    _swap_dir_after_final_check(monkeypatch, opt, aside, occupy_after_capture=False)

    refused = remove_paths([artifact])

    assert refused == (opt,)
    assert (opt / "decoy").read_text() == "vendor reinstall"
    assert (aside / "fd").read_text() == "fd binary"
    assert [p for p in opt.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)] == []


def _escape_after_final_check(
    monkeypatch: pytest.MonkeyPatch, directory: Path, aside: Path
) -> None:
    """Replace a verified app with a tree whose key escapes to the backup."""
    real = receipts.matches
    escaped = False

    def wrapper(
        candidate: receipts.ReceiptArtifact, *, rehash: bool = False, trees: Sequence[Path] = ()
    ) -> bool:
        nonlocal escaped
        result = real(candidate, rehash=rehash, trees=trees)
        if candidate.path == directory and not escaped:
            escaped = True
            directory.rename(aside)
            directory.mkdir()
            (directory / "Contents").symlink_to(aside / "Contents", target_is_directory=True)
            (directory / "unrelated").write_text("new data")
        return result

    monkeypatch.setattr(receipts, "matches", wrapper)


def test_remove_paths_refuses_a_replacement_keyed_through_an_escaping_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR3-01: the quarantine check must not delete a replacement tree."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool, bin_dir, directory, _link = _plant_receipt_dir(tmp_path, "app")
    artifact = plan_removal([tool], bin_dir, verify=True).artifacts[directory]
    aside = directory.with_name("Demo.backup.app")
    _escape_after_final_check(monkeypatch, directory, aside)

    refused = remove_paths([artifact])

    assert refused == (directory,)
    assert (directory / "unrelated").read_text() == "new data"
    assert (directory / "Contents").is_symlink()
    assert (aside / "Contents" / "Info.plist").read_text() == "<plist>vendor</plist>"
    assert [p for p in directory.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)] == []


def test_plan_removal_never_proves_a_dir_whose_key_escapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool, bin_dir, directory, _link = _plant_receipt_dir(tmp_path, "app")
    aside = directory.with_name("Demo.backup.app")
    directory.rename(aside)
    directory.mkdir()
    (directory / "Contents").symlink_to(aside / "Contents", target_is_directory=True)
    (directory / "unrelated").write_text("new data")

    plan = plan_removal([tool], bin_dir)

    assert plan.removable == ()
    assert plan.by_tool == {}
    assert directory in plan.yourself


def test_remove_paths_keeps_a_captured_dir_it_cannot_put_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-19-109: a captured tree that fails its re-check and cannot be renamed
    back is kept at its quarantine path and named, never deleted."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    artifact = plan_removal([fd], bin_dir, verify=True).artifacts[opt]
    aside = tmp_path / "verified-fd"
    _swap_dir_after_final_check(monkeypatch, opt, aside, occupy_after_capture=True)

    with pytest.raises(OSError, match="changed during removal; it is kept at"):
        remove_paths([artifact])

    kept = [p for p in opt.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)]
    assert len(kept) == 1
    assert (kept[0] / "decoy").read_text() == "vendor reinstall"
    assert (opt / "newest").read_text() == "third copy"
    assert (aside / "fd").read_text() == "fd binary"


def test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    leftover = opt.parent / f".fd.k1ll3d{_QUARANTINE_SUFFIX}"
    opt.rename(leftover)

    plan = plan_removal([fd], bin_dir)
    assert plan.removable == ()
    assert leftover in plan.yourself
    state = _removal_state(fd, plan)
    assert uninstall_group(state) == UninstallState.MANAGED
    assert str(leftover) in uninstall_detail(fd, state)

    opt.mkdir()
    (opt / "fd").write_text("fd binary")
    plan = plan_removal([fd], bin_dir)
    assert plan.removable == (bin_dir / "fd", opt)
    assert leftover in plan.yourself
    removed, _refused = remove_proven([fd], [bin_dir / "fd", opt], bin_dir)
    assert set(removed) == {bin_dir / "fd", opt}
    assert leftover.is_dir()
    assert (leftover / "fd").read_text() == "fd binary"


def test_remove_proven_rehashes_a_receiptless_dir_key_file_at_deletion_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    tool, bin_dir, opt = _plant_fd(tmp_path)
    preview = plan_removal([tool], bin_dir)
    assert set(preview.removable) == {bin_dir / "fd", opt}

    member = opt / "fd"
    st = member.stat()
    member.write_text("FD BINARY")
    os.utime(member, ns=(st.st_atime_ns, st.st_mtime_ns))

    removed, refused = remove_proven([tool], list(preview.removable), bin_dir)

    assert refused == ()
    assert set(removed) == {bin_dir / "fd", opt}
    assert not opt.exists()
    assert not (bin_dir / "fd").is_symlink()


def test_remove_proven_hashes_a_dir_key_file_twice_not_three_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(receipts, "_REHASH_MEMO", {})
    tool, bin_dir, opt = _plant_rg(tmp_path)
    write_receipt(tool, [(opt, "dir"), (bin_dir / "rg", "link")])
    real_sha256 = receipts.sha256_file
    names: list[str] = []

    def count_sha256(path: Path) -> str:
        names.append(path.name)
        return real_sha256(path)

    monkeypatch.setattr(receipts, "sha256_file", count_sha256)
    removed, refused = remove_proven([tool], [bin_dir / "rg", opt], bin_dir)
    assert refused == ()
    assert not opt.exists()
    assert names.count("rg") == 2
    assert set(removed) == {bin_dir / "rg", opt}


def test_dir_removal_leaves_no_quarantine_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success path: a proven dir is deleted and the capture is cleaned up.

    This test passes on the pre-quarantine tree too; it pins that the new
    sibling never survives a completed removal."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    artifact = plan_removal([fd], bin_dir, verify=True).artifacts[opt]

    assert remove_paths([artifact]) == ()
    assert not opt.exists()
    assert [p for p in opt.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)] == []


@pytest.mark.parametrize("where", ["after_capture", "at_delete"])
def test_remove_paths_puts_the_tree_back_when_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    import installer.uninstall as uninstall_module

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    artifact = plan_removal([fd], bin_dir, verify=True).artifacts[opt]
    if where == "after_capture":
        original_matches = uninstall_module.receipts.matches

        def interrupt_recheck(
            candidate: receipts.ReceiptArtifact, *, rehash: bool = False, trees: Sequence[Path] = ()
        ) -> bool:
            if candidate.path.name.endswith(_QUARANTINE_SUFFIX):
                raise KeyboardInterrupt
            return original_matches(candidate, rehash=rehash, trees=trees)

        monkeypatch.setattr(uninstall_module.receipts, "matches", interrupt_recheck)
    else:
        original_rmtree = uninstall_module.shutil.rmtree

        def interrupt_delete(
            path: str | os.PathLike[str],
            ignore_errors: bool = False,
            onerror: Callable[..., object] | None = None,
        ) -> None:
            if Path(path).name.endswith(_QUARANTINE_SUFFIX):
                raise KeyboardInterrupt
            original_rmtree(path, ignore_errors=ignore_errors, onerror=onerror)

        monkeypatch.setattr(uninstall_module.shutil, "rmtree", interrupt_delete)

    with pytest.raises(KeyboardInterrupt):
        remove_paths([artifact])

    assert (opt / "fd").read_text() == "fd binary"
    assert opt.is_dir()
    assert [p for p in opt.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)] == []


def test_an_interrupted_removal_that_cannot_put_back_names_the_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.uninstall as uninstall_module

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    artifact = plan_removal([fd], bin_dir, verify=True).artifacts[opt]
    original_matches = uninstall_module.receipts.matches

    def interrupt_and_occupy(
        candidate: receipts.ReceiptArtifact, *, rehash: bool = False, trees: Sequence[Path] = ()
    ) -> bool:
        if candidate.path.name.endswith(_QUARANTINE_SUFFIX):
            opt.mkdir()
            (opt / "newest").write_text("third copy")
            raise KeyboardInterrupt
        return original_matches(candidate, rehash=rehash, trees=trees)

    monkeypatch.setattr(uninstall_module.receipts, "matches", interrupt_and_occupy)
    with pytest.raises(OSError, match="changed during removal; it is kept at") as caught:
        remove_paths([artifact])

    kept = [p for p in opt.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)]
    assert len(kept) == 1
    assert (kept[0] / "fd").read_text() == "fd binary"
    assert (opt / "newest").read_text() == "third copy"
    assert isinstance(caught.value.__context__, KeyboardInterrupt)


def _script_tool(*paths: str) -> Tool:
    """A script tool whose declared `paths` are its only removal evidence."""
    return _tool(Method(kind="script", params={"paths": list(paths)}), tool_id="t", cmd="t")


def _plant_script_install(home: Path) -> tuple[Path, Path, Path]:
    """What a vendor script leaves: a versioned binary, a symlink to it, and the tree."""
    tree = home / ".local" / "share" / "t"
    version = tree / "versions" / "1" / "t"
    version.parent.mkdir(parents=True)
    version.write_text("t binary")
    link = home / ".local" / "bin" / "t"
    link.parent.mkdir(parents=True)
    link.symlink_to(version)
    return tree, version, link


def test_a_script_install_is_removed_by_its_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))  # `~` in a script path is expanduser's HOME
    bin_dir = tmp_path / ".local" / "bin"
    tool = _script_tool("~/.local/bin/t", "~/.local/share/t/")
    assert receipts.preexisting_paths(tool.methods[0]) == frozenset()
    tree, _version, link = _plant_script_install(tmp_path)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    plan = plan_removal([tool], bin_dir)
    assert set(plan.removable) == {link, tree}
    removed, refused = remove_proven([tool], list(plan.removable), bin_dir)
    assert set(removed) == {link, tree}
    assert refused == ()
    assert not os.path.lexists(link)
    assert not tree.exists()
    assert not receipts.receipt_path("t").exists()


def test_a_self_update_inside_the_tree_keeps_the_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _script_tool("~/.local/bin/t", "~/.local/share/t/")
    tree, version, link = _plant_script_install(tmp_path)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    version.write_text("t binary, rewritten by the vendor")
    newer = tree / "versions" / "2" / "t"
    newer.parent.mkdir(parents=True)
    newer.write_text("t binary v2")
    link.unlink()
    link.symlink_to(newer)
    plan = plan_removal([tool], tmp_path / ".local" / "bin")
    assert set(plan.removable) == {link, tree}


def test_a_foreign_file_at_a_declared_path_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    tool = _script_tool("~/.local/bin/t", "~/.local/bin/t-helper")
    (bin_dir / "t").write_text("t")
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    helper = bin_dir / "t-helper"
    helper.write_text("a foreign file")
    plan = plan_removal([tool], bin_dir)
    assert plan.removable == (bin_dir / "t",)
    assert helper in plan.yourself
    removed, refused = remove_proven([tool], list(plan.removable), bin_dir)
    assert removed == (bin_dir / "t",)
    assert refused == ()
    assert helper.read_text() == "a foreign file"


def test_a_tree_swapped_for_a_symlink_after_planning_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _script_tool("~/.local/bin/t", "~/.local/share/t/")
    tree, _version, _link = _plant_script_install(tmp_path)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    artifact = plan_removal([tool], tmp_path / ".local" / "bin").artifacts[tree]
    tree.rename(tmp_path / "verified-tree")
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "sentinel").write_text("not ours")
    tree.symlink_to(decoy, target_is_directory=True)
    assert remove_paths([artifact]) == (tree,)
    assert tree.is_symlink()
    assert (decoy / "sentinel").read_text() == "not ours"


def test_an_interrupted_tree_removal_puts_the_tree_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.uninstall as uninstall_module

    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _script_tool("~/.local/bin/t", "~/.local/share/t/")
    tree, _version, _link = _plant_script_install(tmp_path)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    artifact = plan_removal([tool], tmp_path / ".local" / "bin").artifacts[tree]

    def interrupted_rmtree(path: str | os.PathLike[str], **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(uninstall_module.shutil, "rmtree", interrupted_rmtree)
    with pytest.raises(KeyboardInterrupt):
        remove_paths([artifact])
    assert (tree / "versions" / "1" / "t").read_text() == "t binary"
    assert [p for p in tree.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)] == []


def test_a_tree_quarantine_sibling_is_listed_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _script_tool("~/.local/bin/t", "~/.local/share/t/")
    tree, _version, _link = _plant_script_install(tmp_path)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    leftover = tree.parent / f".{tree.name}.1a2b3c{_QUARANTINE_SUFFIX}"
    leftover.mkdir()
    (leftover / "sentinel").write_text("left by a killed run")
    plan = plan_removal([tool], tmp_path / ".local" / "bin")
    assert leftover in plan.yourself
    assert leftover not in plan.removable
    remove_proven([tool], list(plan.removable), tmp_path / ".local" / "bin")
    assert (leftover / "sentinel").read_text() == "left by a killed run"


def test_a_leaf_link_into_a_deleted_tree_is_still_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The link was retargeted inside the tree by a self-update, then a vendor
    `remove` deleted the tree; the lexical rule still proves the link."""
    import shutil

    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _script_tool("~/.local/bin/t", "~/.local/share/t/")
    tree, _version, link = _plant_script_install(tmp_path)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    link_artifact = plan_removal([tool], tmp_path / ".local" / "bin").artifacts[link]
    newer = tree / "versions" / "2" / "t"
    newer.parent.mkdir(parents=True)
    newer.write_text("t binary v2")
    link.unlink()
    link.symlink_to(newer)
    shutil.rmtree(tree)
    assert remove_paths([link_artifact], trees=(tree,)) == ()
    assert not os.path.lexists(link)


def test_a_config_path_under_a_symlinked_parent_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import delete_config_path

    home = tmp_path / "home"
    (home / ".claude" / "cfg" / "gh").mkdir(parents=True)
    (home / ".claude" / "cfg" / "gh" / "hosts.yml").write_text("token")
    monkeypatch.setenv("HOME", str(home))
    (home / ".config").symlink_to(home / ".claude" / "cfg")  # the parent is a harness dir
    with pytest.raises(OSError):
        delete_config_path(home / ".config" / "gh")
    assert (home / ".claude" / "cfg" / "gh" / "hosts.yml").exists()

    outside = tmp_path / "outside" / "gh"
    outside.mkdir(parents=True)
    (outside / "hosts.yml").write_text("token")
    (home / ".config").unlink()
    (home / ".config").symlink_to(tmp_path / "outside")  # the parent resolves outside HOME
    with pytest.raises(OSError):
        delete_config_path(home / ".config" / "gh")
    assert (outside / "hosts.yml").exists()

    dotfiles = home / "dotfiles" / "config" / "gh"
    dotfiles.mkdir(parents=True)
    (dotfiles / "hosts.yml").write_text("token")
    (home / ".config").unlink()
    (home / ".config").symlink_to(home / "dotfiles" / "config")  # a dotfiles layout inside HOME
    delete_config_path(home / ".config" / "gh")
    assert not dotfiles.exists()


def test_a_config_dir_a_harness_marker_points_to_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import delete_config_path

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    gh = home / ".config" / "gh"
    gh.mkdir(parents=True)
    (gh / "hosts.yml").write_text("token")
    (home / ".claude").symlink_to(gh)  # the harness marker resolves to the config dir
    with pytest.raises(OSError):
        delete_config_path(gh)
    assert (gh / "hosts.yml").exists()
    assert (home / ".claude").resolve() == gh.resolve()

    (home / ".claude").unlink()
    (gh / "sub").mkdir()
    (home / ".claude").symlink_to(gh / "sub")  # the marker lies inside the config dir
    with pytest.raises(OSError):
        delete_config_path(gh)
    assert (gh / "sub").is_dir()

    (home / ".claude").unlink()
    dotfiles = home / "dotfiles" / "claude"
    dotfiles.mkdir(parents=True)
    (dotfiles / "settings.json").write_text("{}")
    (home / ".claude").symlink_to(dotfiles)  # unrelated to the config dir
    delete_config_path(gh)
    assert not gh.exists()

    (home / ".config" / "gh").symlink_to(dotfiles)  # a config link to a harness dir: unlinked only
    delete_config_path(home / ".config" / "gh")
    assert not (home / ".config" / "gh").is_symlink()
    assert (dotfiles / "settings.json").exists()


def test_symlinked_config_is_unlinked_not_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import delete_config_path

    monkeypatch.setenv("HOME", str(tmp_path))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep").write_text("kept")
    link = tmp_path / ".config" / "gh"
    link.parent.mkdir()
    link.symlink_to(elsewhere)
    delete_config_path(link)
    assert not link.is_symlink()
    assert (elsewhere / "keep").exists()


def plant_receipted_tool(home: Path, tool_id: str, postinstall: str | None = None) -> Tool:
    """A github_release tool installed under ``home``: its opt tree, its proven bin link and
    its receipt. Public: the removal tests plant claude and codegraph through this one form."""
    method = Method(
        kind="github_release", params={"repo": f"a/{tool_id}", "asset": "x", "member": tool_id}
    )
    tool = Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(method,),
        postinstall=postinstall,
    )
    bin_dir = home / ".local" / "bin"
    paths = {artifact.kind: artifact.path for artifact in artifact_paths(method, bin_dir)}
    paths["dir"].mkdir(parents=True)
    (paths["dir"] / tool_id).write_text(f"{tool_id} binary")
    paths["link"].parent.mkdir(parents=True, exist_ok=True)
    paths["link"].symlink_to(paths["dir"] / tool_id)
    receipts.record(
        tool, method, package=None, smoke=None, default_bin_dir=bin_dir, preexisting=frozenset()
    )
    return tool


def plant_codegraph(home: Path, hosts: tuple[str, ...] = ()) -> Tool:
    """A github_release codegraph installed under ``home``: its opt tree, its proven bin link,
    its receipt, and the hook hosts that receipt records (``hosts`` may be empty).

    Public: tests/test_uninstall_e2e.py and tests/test_app.py plant the same install."""
    tool = plant_receipted_tool(home, "codegraph", postinstall="codegraph-mcp-register")
    if hosts:
        receipts.record_hooks("codegraph", "codegraph-mcp-register", hosts)
    return tool


def test_removal_plan_builds_unregister_from_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    plan = removal_plan(tool, bin_dir, verify=True)
    link = str(bin_dir / "codegraph")
    assert plan.unregister == (
        (
            link,
            "uninstall",
            "--target",
            "claude,codex",
            "--location",
            "global",
            "--yes",
            "--keep-cli",
        ),
    )
    assert plan.hook_hosts == ("claude", "codex")


def test_no_proven_executable_means_no_unregister(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("claude",))
    link = bin_dir / "codegraph"
    link.unlink()
    link.write_text("a foreign file replaced the proven link")
    plan = removal_plan(tool, bin_dir, verify=True)
    assert (plan.unregister, plan.hook_hosts) == ((), ())


def test_a_pre_phase_23_receipt_unregisters_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt written before hooks were recorded holds hooks={}: nothing is unregistered
    (review R1-39), and the removal itself still succeeds."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path)
    plan = removal_plan(tool, bin_dir, verify=True)
    assert (plan.unregister, plan.hook_hosts) == ((), ())
    removed, refused = remove_proven([tool], list(plan.removable), bin_dir)
    assert refused == ()
    assert not (bin_dir / "codegraph").is_symlink()
    assert not receipts.receipt_exists("codegraph")
    assert removed


@pytest.mark.parametrize(
    ("recorded", "hosts"),
    [
        pytest.param(("claude", "all", "../x", "pi"), ("claude",), id="filtered"),
        pytest.param(("all",), (), id="nothing-left"),
    ],
)
def test_a_tampered_receipt_host_list_is_filtered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recorded: tuple[str, ...],
    hosts: tuple[str, ...],
) -> None:
    """T-23-19: a hand-edited host list reaches an argv only through the closed target map."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, recorded)
    plan = removal_plan(tool, bin_dir, verify=True)
    undo = (
        str(bin_dir / "codegraph"),
        "uninstall",
        "--target",
        ",".join(hosts),
        "--location",
        "global",
        "--yes",
        "--keep-cli",
    )
    assert plan.unregister == ((undo,) if hosts else ())
    assert plan.hook_hosts == hosts


def _retired_tool(
    tool_id: str,
    artifacts: list[tuple[Path, str]],
    *,
    kind: str = "github_release",
    dir_key: str | None = None,
) -> Tool:
    """A receipt for `tool_id` as `receipts.scan_retired` hands it over (id outside the catalog)."""
    write_receipt(_dl_tool(tool_id, tool_id), artifacts, kind=kind, dir_key=dir_key)
    (tool,) = [t for t in receipts.scan_retired(set()).tools if t.id == tool_id]
    assert tool.retired
    return tool


def _run_uninstall_over(
    tools: list[Tool],
    home: Path,
    buf_console: tuple[Console, StringIO],
    runner: Callable[..., None],
) -> tuple[list[Path], tuple[str, ...]]:
    from installer.app import run_uninstall

    console, _buf = buf_console
    return run_uninstall(
        tools,
        console,
        default_bin_dir=home / ".local" / "bin",
        myshellrc_path=home / ".myshellrc",
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=home / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=runner,
    )


def test_a_retired_raw_download_is_removed_with_its_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tracer: a retired download's bin-dir file and its receipt go through the shared remover."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    tool = _retired_tool("rtk", [(rtk, "file")])

    plan = removal_plan(tool, bin_dir)
    assert plan.level == "artifacts"
    assert plan.removable == (rtk,)

    console, buf = _uninstall_console()
    removed, failed = _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)

    assert removed == [rtk]
    assert failed == ()
    assert not rtk.exists()
    assert not receipts.receipt_exists("rtk")
    out = buf.getvalue()
    assert "retired — no longer in the catalog" in out
    assert "rtk (retired)" in out


def test_a_catalog_tool_proof_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The retired shape rule never applies to a catalog tool: a bin file its methods do not name
    stays unproven, while the registry formula still proves its own (path, type) pair."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "other").write_text("not what the method names")
    other = _dl_tool("other", "other")
    write_receipt(other, [(bin_dir / "other", "file")])
    assert plan_removal([other], bin_dir).removable == ()

    yq, yq_bin = plant_raw_yq(tmp_path)
    assert plan_removal([yq], yq_bin).removable == (yq_bin / "yq",)


def _plant_opt_tool(home: Path, name: str) -> tuple[Path, Path, Path]:
    """`<bin>/name` linked into `opt_dir(name)/name`; returns (bin dir, link, opt dir)."""
    bin_dir = home / ".local" / "bin"
    opt = home / ".local" / "opt" / name
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    (opt / name).write_text(f"{name} binary")
    (bin_dir / name).symlink_to(opt / name)
    return bin_dir, bin_dir / name, opt


def test_a_drifted_retired_file_is_kept_and_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prohibition: a recorded file changed since the receipt proves nothing and is kept."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    tool = _retired_tool("rtk", [(rtk, "file")])
    rtk.write_text("rtk raw binary, edited by the user")

    plan = removal_plan(tool, bin_dir)
    assert plan.removable == ()
    assert plan.yourself == (rtk,)

    console, buf = _uninstall_console()
    removed, failed = _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert (removed, failed) == ([], ())
    assert rtk.read_text() == "rtk raw binary, edited by the user"
    assert receipts.receipt_exists("rtk")
    assert f"remove it yourself: {rtk}" in buf.getvalue()


def _outside_shape_artifact(
    case: str, home: Path
) -> tuple[str, Path, receipts.ReceiptArtifact | None]:
    """(receipt kind, the planted path, its matching fingerprint) for one out-of-shape case."""
    bin_dir = home / ".local" / "bin"
    (home / ".local" / "opt").mkdir(parents=True, exist_ok=True)
    if case == "ssh-file":
        target = home / ".ssh" / "id_test"
        target.parent.mkdir()
        target.write_text("private key stand-in")
        return "github_release", target, receipts.fingerprint(target, "file")
    if case == "opt-dotdot":
        target = home / ".local" / "opt" / ".."
        (home / ".local" / "key.txt").write_text("key")
        return "tarball", target, receipts.fingerprint(target, "dir", key="key.txt")
    if case == "nested-bin-file":
        target = bin_dir / "sub" / "x"
        target.parent.mkdir(parents=True)
        target.write_text("nested")
        return "github_release", target, receipts.fingerprint(target, "file")
    target = home / ".claude" / "skills"
    target.mkdir(parents=True)
    return "script", target, receipts.fingerprint(target, "tree")


@pytest.mark.parametrize("case", ["ssh-file", "opt-dotdot", "nested-bin-file", "script-tree"])
def test_a_retired_receipt_never_deletes_outside_its_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """T-23.1-30: a hand-edited receipt with a planted matching fingerprint cannot aim a delete."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    kind, target, artifact = _outside_shape_artifact(case, tmp_path)
    assert artifact is not None
    receipts.write(
        Receipt(
            tool="evil",
            at="2026-10-16T00:00:00Z",
            method=ReceiptMethod(kind=kind, key="k"),
            package=None,
            artifacts=(artifact,),
            smoke=None,
            hooks={},
        )
    )
    (tool,) = receipts.scan_retired(set()).tools

    plan = removal_plan(tool, bin_dir)
    assert plan.removable == ()
    assert plan.yourself == (target,)

    console, buf = _uninstall_console()
    removed, _failed = _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert removed == []
    assert target.exists()
    assert (tmp_path / ".local").is_dir()
    assert receipts.receipt_exists("evil")


@pytest.mark.parametrize("kind", ["tarball", "github_release"])
def test_a_retired_tarball_link_and_opt_dir_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir, link, opt = _plant_opt_tool(tmp_path, "tool")
    tool = _retired_tool("tool", [(link, "link"), (opt, "dir")], kind=kind)

    assert plan_removal([tool], bin_dir).removable == (link, opt)

    console, buf = _uninstall_console()
    removed, _failed = _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert set(removed) == {link, opt}
    assert not link.is_symlink()
    assert not opt.exists()
    assert not receipts.receipt_exists("tool")


@pytest.mark.parametrize("case", ["other-name", "no-link"])
def test_a_retired_opt_dir_needs_its_paired_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Review R1-04: an opt dir is proven only beside a recorded bin link of the same name."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir, link, tool_opt = _plant_opt_tool(tmp_path, "tool")
    if case == "other-name":
        other = tmp_path / ".local" / "opt" / "other"
        other.mkdir()
        (other / "other").write_text("someone else's tool")
        opt, artifacts = other, [(link, "link"), (other, "dir")]
    else:
        opt, artifacts = tool_opt, [(tool_opt, "dir")]
    tool = _retired_tool("tool", artifacts, kind="tarball", dir_key=opt.name)

    plan = removal_plan(tool, bin_dir)
    assert opt not in plan.removable
    assert opt in plan.yourself

    console, buf = _uninstall_console()
    _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert (opt / opt.name).is_file()


def test_a_partial_proof_removes_the_proven_file_and_lists_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review R1-50: the proven path goes, the receipt is retired, the out-of-shape path stays."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    ssh = tmp_path / ".ssh" / "id_test"
    ssh.parent.mkdir()
    ssh.write_text("private key stand-in")
    tool = _retired_tool("rtk", [(rtk, "file"), (ssh, "file")])

    console, buf = _uninstall_console()
    removed, _failed = _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert removed == [rtk]
    assert not rtk.exists()
    assert not receipts.receipt_exists("rtk")
    assert ssh.read_text() == "private key stand-in"
    assert f"remove it yourself: {ssh}" in buf.getvalue()


def test_a_retired_app_bundle_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "X.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    (bundle / receipts.APP_KEY_FILE).write_text("plist")
    (bundle / "Contents" / "MacOS" / "x").write_text("x")
    link = bin_dir / "x"
    link.symlink_to(bundle / "Contents" / "MacOS" / "x")
    tool = _retired_tool("x", [(bundle, "dir"), (link, "link")], kind="app")

    console, buf = _uninstall_console()
    removed, _failed = _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert set(removed) == {bundle, link}
    assert not bundle.exists()
    assert not link.is_symlink()
    assert not receipts.receipt_exists("x")


def test_a_retired_opt_dir_needs_its_link_to_resolve_inside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-02 (X-02): a recorded link of the same name that points elsewhere proves no opt dir."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir, link, opt = _plant_opt_tool(tmp_path, "tool")
    elsewhere = tmp_path / "elsewhere" / "tool"
    elsewhere.parent.mkdir()
    elsewhere.write_text("not in the opt dir")
    link.unlink()
    link.symlink_to(elsewhere)
    tool = _retired_tool("tool", [(link, "link"), (opt, "dir")], kind="tarball", dir_key="tool")

    plan = removal_plan(tool, bin_dir)
    assert opt not in plan.removable
    assert opt in plan.yourself

    console, buf = _uninstall_console()
    _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert (opt / "tool").read_text() == "tool binary"


@pytest.mark.parametrize("case", ["no-link", "link-outside"])
def test_a_retired_app_bundle_needs_its_link_to_resolve_inside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """C-02 (X-02): a bundle is proven only by its recorded bin link resolving into it."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bundle = tmp_path / "Applications" / "X.app"
    (bundle / "Contents").mkdir(parents=True)
    (bundle / receipts.APP_KEY_FILE).write_text("plist")
    artifacts = [(bundle, "dir")]
    if case == "link-outside":
        outside = tmp_path / "outside-x"
        outside.write_text("x")
        link = bin_dir / "x"
        link.symlink_to(outside)
        artifacts.append((link, "link"))
    tool = _retired_tool("x", artifacts, kind="app")

    plan = removal_plan(tool, bin_dir)
    assert bundle not in plan.removable
    assert bundle in plan.yourself

    console, buf = _uninstall_console()
    _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert (bundle / receipts.APP_KEY_FILE).read_text() == "plist"


def test_a_retired_receipt_never_removes_what_a_live_receipt_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-02 (WR-06): an id renamed in the catalog leaves an old receipt for the same link and
    opt dir; retiring it retires the receipt only, and the live tool's paths stay unmentioned."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir, link, opt = _plant_opt_tool(tmp_path, "foo")
    write_receipt(_dl_tool("foo-cli", "foo"), [(link, "link"), (opt, "dir")])
    tool = _retired_tool("foo", [(link, "link"), (opt, "dir")], kind="tarball", dir_key="foo")

    plan = removal_plan(tool, bin_dir)
    assert plan.removable == ()
    assert plan.yourself == ()
    assert plan.level == "receipt"

    console, buf = _uninstall_console()
    _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert link.is_symlink()
    assert (opt / "foo").read_text() == "foo binary"
    assert not receipts.receipt_exists("foo")
    live = receipts.read("foo-cli")
    assert live is not None
    assert not receipts.drifted(live, rehash=True)


def test_two_retired_receipts_never_remove_a_path_they_share(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-02: a path another retired receipt also records is never deleted by either removal."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    shared = bin_dir / "shared"
    shared.write_text("shared binary")
    alpha = _retired_tool("alpha", [(shared, "file")])
    bravo = _retired_tool("bravo", [(shared, "file")])

    for tool in (alpha, bravo):
        assert removal_plan(tool, bin_dir).removable == ()

    console, buf = _uninstall_console()
    _run_uninstall_over([alpha, bravo], tmp_path, (console, buf), _no_removal_runner)
    assert shared.read_text() == "shared binary"


def test_unrecorded_files_are_never_touched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    sibling = bin_dir / "other"
    sibling.write_text("not in the receipt")
    tool = _retired_tool("rtk", [(rtk, "file")])

    console, buf = _uninstall_console()
    _run_uninstall_over([tool], tmp_path, (console, buf), _no_removal_runner)
    assert not rtk.exists()
    assert sibling.read_text() == "not in the receipt"


def test_a_retired_file_changed_before_confirm_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC R3 concurrency: same size and mtime, other bytes; only the deletion re-hash sees it."""
    from installer.app import remove_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    tool = _retired_tool("rtk", [(rtk, "file")])
    plan = removal_plan(tool, bin_dir)
    assert plan.removable == (rtk,)

    stat = rtk.stat()
    rtk.write_text("RTK RAW BINARY")
    os.utime(rtk, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    outcome = remove_tool(
        tool, paths=plan.removable, argv=(), bin_dir=bin_dir, runner=_no_removal_runner
    )

    assert not outcome.removed
    assert "changed since the preview; not removed" in outcome.detail
    assert rtk.read_text() == "RTK RAW BINARY"
    assert receipts.receipt_exists("rtk")


def _write_bare_receipt(tool_id: str, kind: str, *, package: str | None = None) -> Tool:
    """A retired receipt that records no artifact (a manager package, or nothing at all)."""
    receipts.write(
        Receipt(
            tool=tool_id,
            at="2026-10-16T00:00:00Z",
            method=ReceiptMethod(kind=kind, key="k"),
            package=package,
            artifacts=(),
            smoke=None,
            hooks={},
        )
    )
    (tool,) = [t for t in receipts.scan_retired(set()).tools if t.id == tool_id]
    return tool


MANAGER_SENTENCE = "Retired the {id} receipt; brew {id} stays installed — remove it yourself."
EMPTY_SENTENCE = "Retired the {id} receipt; there was nothing to delete."


def test_a_retired_manager_receipt_retires_without_a_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-08, T-23.1-32: no manager command is built or run; the package stays installed."""
    from installer.app import remove_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = _write_bare_receipt("rtk", "brew", package="rtk")

    plan = removal_plan(tool, bin_dir)
    assert plan.level == "receipt"
    assert plan.argv == ()
    assert plan.hint == "remove it yourself: brew rtk"

    outcome = remove_tool(tool, paths=(), argv=(), bin_dir=bin_dir, runner=_no_removal_runner)
    assert outcome.removed
    assert outcome.detail == MANAGER_SENTENCE.format(id="rtk")
    assert not receipts.receipt_exists("rtk")


def test_an_empty_retired_receipt_retires_with_nothing_to_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import remove_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = _write_bare_receipt("rtk", "github_release")

    plan = removal_plan(tool, bin_dir)
    assert plan.level == "receipt"
    assert plan.hint is None

    outcome = remove_tool(tool, paths=(), argv=(), bin_dir=bin_dir, runner=_no_removal_runner)
    assert outcome.removed
    assert outcome.detail == EMPTY_SENTENCE.format(id="rtk")
    assert not receipts.receipt_exists("rtk")


def test_a_receipt_only_removal_is_refused_when_a_path_came_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorded file was gone at preview time (receipt-only row) and is back at confirm."""
    from installer.app import remove_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    tool = _retired_tool("rtk", [(rtk, "file")])
    rtk.unlink()
    assert removal_plan(tool, bin_dir).level == "receipt"

    rtk.write_text("something else now lives here")
    outcome = remove_tool(tool, paths=(), argv=(), bin_dir=bin_dir, runner=_no_removal_runner)

    assert not outcome.removed
    assert "changed since the preview; not removed" in outcome.detail
    assert receipts.receipt_exists("rtk")
    assert rtk.read_text() == "something else now lives here"


def _plant_four_retired(home: Path) -> tuple[list[Tool], Path, Path]:
    """alpha (proven, a path holding markup), bravo (drifted), charlie (brew), delta (empty)."""
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    proven = bin_dir / "[red]alpha"
    proven.write_text("alpha binary")
    drifted = bin_dir / "bravo"
    drifted.write_text("bravo binary")
    tools = [
        _retired_tool("alpha", [(proven, "file")]),
        _retired_tool("bravo", [(drifted, "file")]),
        _write_bare_receipt("charlie", "brew", package="charlie"),
        _write_bare_receipt("delta", "github_release"),
    ]
    drifted.write_text("bravo binary, edited by the user")
    return tools, proven, drifted


def _retired_block(output: str, count: int) -> list[str]:
    lines = output.splitlines()
    start = lines.index("retired — no longer in the catalog")
    return lines[start : start + count]


def test_retired_preview_lines_cover_every_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review R1-47: the exact retired block and the exact result lines."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools, proven, drifted = _plant_four_retired(tmp_path)

    console, buf = _uninstall_console()
    _run_uninstall_over(tools, tmp_path, (console, buf), _no_removal_runner)
    output = buf.getvalue()

    block = _retired_block(output, 9)
    assert block == [
        "retired — no longer in the catalog",
        "alpha (retired)",
        f"  {proven}",
        "bravo (retired)",
        f"  remove it yourself: {drifted}",
        "charlie (retired)",
        "  remove it yourself: brew charlie",
        "delta (retired)",
        "  nothing to delete; confirming retires the receipt",
    ]
    lines = output.splitlines()
    assert f"charlie: {MANAGER_SENTENCE.format(id='charlie')}" in lines
    assert f"delta: {EMPTY_SENTENCE.format(id='delta')}" in lines
    # Every fixed part fits 78 cells; only the lines carrying a path are longer.
    for line in block:
        if str(tmp_path) not in line:
            assert len(line) <= 78
    assert len("  remove it yourself: ") <= 78
    assert not proven.exists()
    assert drifted.exists()
    assert not receipts.receipt_exists("alpha")
    assert receipts.receipt_exists("bravo")


def test_retired_preview_offers_removal_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prohibition: no install, update or reinstall wording and no pnpm dlx in the retired text."""
    import re

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools, _proven, _drifted = _plant_four_retired(tmp_path)

    console, buf = _uninstall_console()
    _run_uninstall_over(tools, tmp_path, (console, buf), _no_removal_runner)
    output = buf.getvalue()

    scanned = [
        *_retired_block(output, 9),
        f"charlie: {MANAGER_SENTENCE.format(id='charlie')}",
        f"delta: {EMPTY_SENTENCE.format(id='delta')}",
    ]
    text = "\n".join(scanned)
    assert re.search(r"\b(install|update|reinstall)\b", text, re.IGNORECASE) is None
    assert "pnpm dlx" not in text


def test_a_lone_manager_receipt_is_not_nothing_to_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = _write_bare_receipt("charlie", "brew", package="charlie")
    asked: list[str] = []

    def confirm(message: str) -> bool:
        asked.append(message)
        return True

    console, buf = _uninstall_console()
    run_uninstall(
        [tool],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=confirm,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
    )

    assert "Nothing to uninstall" not in buf.getvalue()
    assert len(asked) == 1
    assert not receipts.receipt_exists("charlie")
