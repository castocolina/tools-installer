import json
import os
from collections.abc import Callable
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from installer import receipts
from installer.download import link_name
from installer.enums import UninstallState
from installer.model import Method, Tool, load_tools
from installer.policy import Policy, daemon_policy, omz_plugins_policy, tweak_policy
from installer.receipts import Receipt, ReceiptMethod
from installer.run import CommandError
from installer.tweaks import BUNDLES, TweakBundle
from installer.uninstall import (
    SweepResult,
    active_tweak_ids,
    manager_name,
    plan_removal,
    plan_uninstall,
    remove_paths,
    remove_proven,
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


def test_classify_rows_use_the_receipt_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    (row,) = classify_tools([yq], bin_dir, installed={"yq": True}, platform=_LINUX)
    assert row.state == UninstallState.REMOVABLE
    assert row.paths == [bin_dir / "yq"]
    assert row.selectable is True
    (bin_dir / "yq").write_text("rewritten after install, a different size")
    (row,) = classify_tools([yq], bin_dir, installed={"yq": True}, platform=_LINUX)
    assert row.state == UninstallState.MANAGED
    assert row.selectable is False
    assert f"remove it yourself: {bin_dir / 'yq'}" in row.hint


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

    def wrapper(candidate: receipts.ReceiptArtifact, *, rehash: bool = False) -> bool:
        nonlocal swapped, occupied
        if (
            occupy_after_capture
            and candidate.path.name.endswith(_QUARANTINE_SUFFIX)
            and not occupied
        ):
            occupied = True
            opt.mkdir()
            (opt / "newest").write_text("third copy")
        verdict = real(candidate, rehash=rehash)
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

    def wrapper(candidate: receipts.ReceiptArtifact, *, rehash: bool = False) -> bool:
        nonlocal escaped
        result = real(candidate, rehash=rehash)
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
    import installer.uninstall as uninstall_module

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd, bin_dir, opt = _plant_fd(tmp_path)
    leftover = opt.parent / f".fd.k1ll3d{_QUARANTINE_SUFFIX}"
    opt.rename(leftover)

    plan = plan_removal([fd], bin_dir)
    assert plan.removable == ()
    assert leftover in plan.yourself
    rows = uninstall_module.classify_tools([fd], bin_dir, installed={"fd": False}, platform=_LINUX)
    assert rows[0].state.value == "managed"
    assert str(leftover) in rows[0].hint

    opt.mkdir()
    (opt / "fd").write_text("fd binary")
    plan = plan_removal([fd], bin_dir)
    assert plan.removable == (bin_dir / "fd", opt)
    assert leftover in plan.yourself
    removed, _refused = remove_proven([fd], [bin_dir / "fd", opt], bin_dir)
    assert set(removed) == {bin_dir / "fd", opt}
    assert leftover.is_dir()
    assert (leftover / "fd").read_text() == "fd binary"


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

        def interrupt_recheck(candidate: receipts.ReceiptArtifact, *, rehash: bool = False) -> bool:
            if candidate.path.name.endswith(_QUARANTINE_SUFFIX):
                raise KeyboardInterrupt
            return original_matches(candidate, rehash=rehash)

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

    def interrupt_and_occupy(candidate: receipts.ReceiptArtifact, *, rehash: bool = False) -> bool:
        if candidate.path.name.endswith(_QUARANTINE_SUFFIX):
            opt.mkdir()
            (opt / "newest").write_text("third copy")
            raise KeyboardInterrupt
        return original_matches(candidate, rehash=rehash)

    monkeypatch.setattr(uninstall_module.receipts, "matches", interrupt_and_occupy)
    with pytest.raises(OSError, match="changed during removal; it is kept at") as caught:
        remove_paths([artifact])

    kept = [p for p in opt.parent.iterdir() if p.name.endswith(_QUARANTINE_SUFFIX)]
    assert len(kept) == 1
    assert (kept[0] / "fd").read_text() == "fd binary"
    assert (opt / "newest").read_text() == "third copy"
    assert isinstance(caught.value.__context__, KeyboardInterrupt)
