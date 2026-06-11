from pathlib import Path

import pytest

from installer.model import Method, Tool
from installer.uninstall import plan_uninstall, remove_paths


def _tool(method: Method, *, tool_id: str = "t", cmd: str = "t") -> Tool:
    # methods is tuple[Method, ...]; priority/audience/desc use their defaults.
    return Tool(id=tool_id, name=tool_id, category="dev", cmd=cmd, methods=(method,))


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
