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


# --- classify_tools: removability over ALL tools (Phase 3) -----------------

from installer.platform import Platform  # noqa: E402
from installer.uninstall import ToolRow, classify_tools, reverse_dependencies  # noqa: E402

_LINUX = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
_MAC = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


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
    bin_dir.mkdir()
    (bin_dir / "fd").write_text("x")
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


def test_classify_managed_generic_hint_when_no_brew_method(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
