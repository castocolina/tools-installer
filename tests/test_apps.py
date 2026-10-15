import hashlib
import inspect
import os
from pathlib import Path

import pytest

import installer.apps as apps_mod
from installer import atomic
from installer.apps import APP_KINDS, cli_spec, install_app, update_app
from installer.atomic import NEW_SUFFIX, OLD_SUFFIX
from installer.checksums import ChecksumMismatch
from installer.executors import ExecutorError
from installer.model import Method, load_tools
from installer.run import Runner
from tests.test_download import fixture_runner

SHELLED_LINKERS = frozenset({"ln", "chmod"})
REGISTRY = Path("installer/registry.toml")


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def _method(**extra: object) -> Method:
    params: dict[str, object] = {"url": "https://example.test/app.zip", "app": "Demo App.app"}
    params.update(extra)
    return Method(kind="app", params=params)


def test_app_kinds_inventory():
    assert APP_KINDS == ("app",)


def test_shipped_app_cli_links_match_the_tool_cmd() -> None:
    for tool in load_tools(REGISTRY):
        for method in tool.methods:
            if method.kind != "app" or method.params.get("cli") is None:
                continue
            spec = cli_spec(method)
            assert spec is not None
            link_name = spec[1]
            assert link_name == tool.cmd, (
                f"{tool.id}: app CLI link {link_name!r} must match tool cmd {tool.cmd!r}"
            )


def test_install_app_uses_plain_curl_and_ditto_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = Path("Demo App.app/Contents/SharedSupport/bin/demo")
    calls, runner = fixture_runner(None, {"app.zip": b"zip"}, member=member)
    install_app(_method(), runner)
    apps = tmp_path / "Applications"
    assert apps.is_dir()
    assert (apps / "Demo App.app").exists()
    assert calls[0][0] == "curl"
    assert calls[0][calls[0].index("--") + 1] == "https://example.test/app.zip"
    assert calls[1][:3] == ["ditto", "-x", "-k"]
    assert not any(cmd and cmd[0] == "sh" for cmd in calls)


def test_install_app_links_the_cli_under_cli_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cli = "Contents/MacOS/draw.io"
    member = Path("draw.io.app") / cli
    calls, runner = fixture_runner(None, {"app.zip": b"zip"}, member=member)
    install_app(
        _method(app="draw.io.app", cli=cli, cli_name="drawio"),
        runner,
    )
    link = tmp_path / ".local" / "bin" / "drawio"
    assert link.is_symlink()
    assert os.readlink(link) == str(tmp_path / "Applications" / "draw.io.app" / cli)
    assert not (tmp_path / ".local" / "bin" / "draw.io").exists()
    assert not any(cmd and cmd[0] in SHELLED_LINKERS for cmd in calls)


def test_cli_spec_without_cli_name_keeps_the_basename() -> None:
    assert cli_spec(_method(cli="Contents/SharedSupport/bin/subl")) == (
        "Contents/SharedSupport/bin/subl",
        "subl",
    )


@pytest.mark.parametrize(
    "cli_name",
    ["", 1, "bin/drawio", ".", ".."],
)
def test_cli_spec_rejects_a_bad_cli_name(cli_name: object) -> None:
    with pytest.raises(ExecutorError, match="invalid cli_name"):
        cli_spec(_method(cli="Contents/MacOS/draw.io", cli_name=cli_name))


def test_install_app_rejects_bad_cli_name_before_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="invalid cli_name"):
        install_app(_method(cli="Contents/MacOS/draw.io", cli_name="bin/drawio"), runner)
    assert calls == []


def test_install_app_symlinks_declared_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cli = "Contents/SharedSupport/bin/demo"
    member = Path("Demo App.app") / cli
    calls, runner = fixture_runner(None, {"app.zip": b"zip"}, member=member)
    install_app(_method(cli=cli), runner)
    link = tmp_path / ".local" / "bin" / "demo"
    assert link.is_symlink()
    live_cli = tmp_path / "Applications" / "Demo App.app" / cli
    assert os.readlink(link) == str(live_cli)
    assert live_cli.stat().st_mode & 0o777 == 0o755  # staged CLI must be executable before link
    assert not any(cmd and cmd[0] in SHELLED_LINKERS for cmd in calls)
    assert (tmp_path / ".local" / "bin").is_dir()


def test_install_app_cli_that_is_a_directory_links_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bundle CLI path that is a directory is not linked."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cli = "Contents/SharedSupport/bin/demo"
    member = Path("Demo App.app") / cli
    calls, runner = fixture_runner(None, {"app.zip": b"zip"}, member=member)

    def plant_directory(cmd: list[str]) -> None:
        runner(cmd)
        if cmd and cmd[0] == "ditto":
            extract_root = Path(cmd[-1])
            live_cli = extract_root / member
            if live_cli.is_file():
                live_cli.unlink()
            live_cli.mkdir(parents=True)

    with pytest.raises(ExecutorError, match="regular file"):
        install_app(_method(cli=cli), plant_directory)
    link = tmp_path / ".local" / "bin" / "demo"
    assert not (tmp_path / "Applications" / "Demo App.app").exists()
    assert not link.exists()
    assert not link.is_symlink()
    assert not any(cmd and cmd[0] in SHELLED_LINKERS for cmd in calls)


def test_install_app_without_cli_runs_curl_and_ditto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = Path("Demo App.app/Contents/PkgInfo")
    calls, runner = fixture_runner(None, {"app.zip": b"zip"}, member=member)
    install_app(_method(), runner)
    assert len(calls) == 2
    assert calls[0][0] == "curl"
    assert calls[1][0] == "ditto"


def test_install_app_requires_url_and_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="url"):
        install_app(Method(kind="app", params={"app": "Demo.app"}), runner)
    with pytest.raises(ExecutorError, match="app"):
        install_app(Method(kind="app", params={"url": "https://example.test/a.zip"}), runner)
    assert calls == []


def test_install_app_rejects_nested_or_traversal_bundle_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="invalid app bundle name"):
        install_app(_method(app="x/Demo.app"), runner)
    with pytest.raises(ExecutorError, match="invalid app bundle name"):
        install_app(_method(app=".."), runner)
    assert calls == []


def test_install_app_rejects_bad_cli_param(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="cli"):
        install_app(_method(cli=""), runner)
    with pytest.raises(ExecutorError, match="cli"):
        install_app(_method(cli=42), runner)
    with pytest.raises(ExecutorError, match="invalid cli path"):
        install_app(_method(cli="/etc/passwd"), runner)
    with pytest.raises(ExecutorError, match="invalid cli path"):
        install_app(_method(cli="Contents/../../etc/evil"), runner)
    with pytest.raises(ExecutorError, match="cannot derive a CLI name"):
        install_app(_method(cli="."), runner)
    assert calls == []  # params are validated before any side effect


def test_install_app_wraps_applications_dir_oserror(monkeypatch: pytest.MonkeyPatch):
    def boom(directory: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(apps_mod, "ensure_dir", boom)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="Applications dir"):
        install_app(_method(), runner)
    assert calls == []


def test_install_app_wraps_bin_dir_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    real = apps_mod.ensure_dir

    def flaky(directory: Path) -> Path:
        if directory.name == "bin":
            raise OSError("denied")
        return real(directory)

    monkeypatch.setattr(apps_mod, "ensure_dir", flaky)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="bin dir"):
        install_app(_method(cli="Contents/bin/demo"), runner)
    assert calls == []  # bin dir is prepared before any network fetch


def _plant_bundle(tmp_path: Path, *, app: str = "Demo App.app", cli: str | None = None) -> Path:
    apps = tmp_path / "Applications"
    bundle = apps / app
    bundle.mkdir(parents=True)
    (bundle / "Contents").mkdir()
    (bundle / "marker").write_text("original")
    if cli is not None:
        cli_path = bundle / cli
        cli_path.parent.mkdir(parents=True, exist_ok=True)
        cli_path.write_bytes(b"old-cli")
        cli_path.chmod(0o755)
        dest = tmp_path / ".local" / "bin"
        dest.mkdir(parents=True, exist_ok=True)
        os.symlink(str(cli_path), dest / Path(cli).name)
    return bundle


def _app_update_runner(
    tmp_path: Path, *, app: str = "Demo App.app", extracted: bytes = b"new-cli"
) -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd[0] == "curl":
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"zip-bytes")
            return
        if cmd[0] == "ditto":
            extract_root = Path(cmd[-1])
            extract_root.mkdir(parents=True, exist_ok=True)
            staged = extract_root / app
            staged.mkdir(parents=True)
            (staged / "Contents").mkdir()
            (staged / "marker").write_text("updated")
            cli = staged / "Contents" / "SharedSupport" / "bin" / "demo"
            cli.parent.mkdir(parents=True, exist_ok=True)
            cli.write_bytes(extracted)
            cli.chmod(0o755)

    return calls, runner


def test_update_app_replaces_bundle_via_os_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, cli="Contents/SharedSupport/bin/demo")

    def boom_move(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("update_app must not call shutil.move")

    monkeypatch.setattr(apps_mod.shutil, "move", boom_move, raising=False)
    calls, runner = _app_update_runner(tmp_path)

    def reject_mv(cmd: list[str]) -> None:
        if cmd and cmd[0] == "mv":
            raise AssertionError("update_app must not shell mv")
        if cmd and cmd[0] == "sh" and " mv " in cmd[-1]:
            raise AssertionError("update_app must not shell mv")
        runner(cmd)

    result = update_app(_method(cli="Contents/SharedSupport/bin/demo"), reject_mv)
    assert result.warnings == ()
    assert (bundle / "marker").read_text() == "updated"
    link = tmp_path / ".local" / "bin" / "demo"
    assert link.is_symlink()
    assert Path(os.readlink(link)).exists()
    assert not any(cmd and cmd[0] == "ln" for cmd in calls)
    assert not Path(str(bundle) + ".tools-installer.old").exists()
    assert not Path(str(bundle) + ".tools-installer.new").exists()


def test_update_app_move_failure_restores_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, cli="Contents/SharedSupport/bin/demo")
    original = os.readlink(tmp_path / ".local" / "bin" / "demo")
    _, runner = _app_update_runner(tmp_path)
    real_replace = os.replace

    def fail_aside(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(src) == bundle and str(dst).endswith(".tools-installer.old"):
            raise OSError("aside failed")
        real_replace(src, dst)

    monkeypatch.setattr(apps_mod.os, "replace", fail_aside)
    with pytest.raises(ExecutorError):
        update_app(_method(cli="Contents/SharedSupport/bin/demo"), runner)
    assert (bundle / "marker").read_text() == "original"
    assert os.readlink(tmp_path / ".local" / "bin" / "demo") == original


def test_update_app_symlink_failure_restores_captured_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, cli="Contents/SharedSupport/bin/demo")
    captured = os.readlink(tmp_path / ".local" / "bin" / "demo")
    _, runner = _app_update_runner(tmp_path)
    real_symlink = os.symlink
    seen: list[str] = []

    def fail_first(target: str, path: str) -> None:
        seen.append(target)
        if len(seen) == 1:
            raise OSError("symlink failed")
        real_symlink(target, path)

    monkeypatch.setattr(atomic.os, "symlink", fail_first)
    with pytest.raises(ExecutorError):
        update_app(_method(cli="Contents/SharedSupport/bin/demo"), runner)
    assert (bundle / "marker").read_text() == "original"
    assert os.readlink(tmp_path / ".local" / "bin" / "demo") == captured
    assert seen[1] == captured


def test_update_app_recovers_interrupted_old_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, cli="Contents/SharedSupport/bin/demo")
    old = Path(str(bundle) + ".tools-installer.old")
    os.replace(bundle, old)
    _, runner = _app_update_runner(tmp_path)
    result = update_app(_method(cli="Contents/SharedSupport/bin/demo"), runner)
    assert result.warnings == ()
    assert (bundle / "marker").read_text() == "updated"
    assert not old.exists()


def test_update_app_validates_params_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path)
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="invalid app bundle name"):
        update_app(_method(app="x/Demo.app"), runner)
    with pytest.raises(ExecutorError, match="invalid cli path"):
        update_app(_method(cli="Contents/../../etc/evil"), runner)
    assert calls == []
    assert (bundle / "marker").read_text() == "original"


def test_update_app_source_uses_os_replace_not_mv() -> None:
    source = inspect.getsource(update_app)
    assert "os.replace" in source
    assert "shutil.move" not in source
    assert " mv " not in source
    install_source = inspect.getsource(install_app)
    assert "sh" not in install_source or '"sh"' not in install_source


def test_update_app_cleanup_failure_is_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, cli="Contents/SharedSupport/bin/demo")
    _, runner = _app_update_runner(tmp_path)
    real_rmtree = apps_mod.shutil.rmtree

    def fail_old(path: str | os.PathLike[str], ignore_errors: bool = False) -> None:
        if str(path).endswith(".tools-installer.old"):
            raise OSError("cleanup failed")
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(apps_mod.shutil, "rmtree", fail_old)
    result = update_app(_method(cli="Contents/SharedSupport/bin/demo"), runner)
    assert any("cleanup failed" in warning for warning in result.warnings)
    assert (bundle / "marker").read_text() == "updated"


def test_update_app_directory_cli_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-03: the app-update CLI check is the same predicate install uses --
    a directory at the cli path is a failure, and the swap rolls back."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, cli="Contents/SharedSupport/bin/demo")
    original = os.readlink(tmp_path / ".local" / "bin" / "demo")
    _, runner = _app_update_runner(tmp_path, extracted=b"new-cli")

    def dir_cli_runner(cmd: list[str]) -> None:
        if cmd[0] == "ditto":
            extract_root = Path(cmd[-1])
            extract_root.mkdir(parents=True, exist_ok=True)
            staged = extract_root / "Demo App.app"
            staged.mkdir(parents=True)
            (staged / "marker").write_text("updated")
            cli = staged / "Contents" / "SharedSupport" / "bin" / "demo"
            cli.parent.mkdir(parents=True, exist_ok=True)
            cli.mkdir()  # the cli path is a directory, not a file
        else:
            runner(cmd)

    with pytest.raises(ExecutorError, match="regular file"):
        update_app(_method(cli="Contents/SharedSupport/bin/demo"), dir_cli_runner)
    assert (bundle / "marker").read_text() == "original"
    assert os.readlink(tmp_path / ".local" / "bin" / "demo") == original


def _drawio_method(**extra: object) -> Method:
    params: dict[str, object] = {
        "url": (
            "https://github.com/jgraph/drawio-desktop/releases/download/v{ver}/"
            "draw.io-arm64-{ver}.zip"
        ),
        "version": "32.4.1",
        "app": "draw.io.app",
        "cli": "Contents/MacOS/draw.io",
        "cli_name": "drawio",
    }
    params.update(extra)
    return Method(kind="app", params=params)


def test_pinned_app_is_verified_and_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    payload = b"drawio-zip-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    member = Path("draw.io.app/Contents/MacOS/draw.io")
    calls, runner = fixture_runner(None, {"app.zip": payload}, member=member)
    reason = install_app(_drawio_method(sha256=digest), runner)
    assert reason is None
    assert (tmp_path / "Applications" / "draw.io.app").is_dir()
    link = tmp_path / ".local" / "bin" / "drawio"
    assert link.is_symlink()
    url = calls[0][calls[0].index("--") + 1]
    assert url == (
        "https://github.com/jgraph/drawio-desktop/releases/download/v32.4.1/"
        "draw.io-arm64-32.4.1.zip"
    )


def test_unpinned_app_installs_unverified_with_a_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    member = Path("Visual Studio Code.app/Contents/Resources/app/bin/code")
    _, runner = fixture_runner(None, {"app.zip": b"vscode"}, member=member)
    method = Method(
        kind="app",
        params={
            "url": "https://update.code.visualstudio.com/latest/darwin-arm64/stable",
            "app": "Visual Studio Code.app",
        },
    )
    reason = install_app(method, runner)
    assert reason == "unpinned url; no sha256 to verify against"
    assert (tmp_path / "Applications" / "Visual Studio Code.app").exists()


def test_non_executable_staged_cli_moves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bundle = _plant_bundle(tmp_path, app="draw.io.app", cli="Contents/MacOS/draw.io")
    link = tmp_path / ".local" / "bin" / "drawio"
    if link.exists() or link.is_symlink():
        link.unlink()
    os.symlink(str(bundle / "Contents/MacOS/draw.io"), link)
    original_bytes = (bundle / "Contents/MacOS/draw.io").read_bytes()
    original_target = os.readlink(link)
    payload = b"reinstall"
    digest = hashlib.sha256(payload).hexdigest()
    member = Path("draw.io.app/Contents/MacOS/draw.io")

    def non_exec_runner(cmd: list[str]) -> None:
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
        elif cmd and cmd[0] == "ditto":
            dest = Path(cmd[-1])
            target = dest / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"not-executable")
            target.chmod(0o644)
        else:
            raise AssertionError(cmd)

    with pytest.raises(ExecutorError, match="not executable"):
        install_app(_drawio_method(sha256=digest), non_exec_runner)
    assert (bundle / "Contents/MacOS/draw.io").read_bytes() == original_bytes
    assert os.readlink(link) == original_target
    assert not Path(str(bundle) + NEW_SUFFIX).exists()
    assert not Path(str(bundle) + OLD_SUFFIX).exists()


def test_staged_cli_symlink_outside_the_bundle_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    marker = tmp_path / "outside-ran.marker"
    outside = tmp_path / "outside-cli.sh"
    outside.write_text(f"#!/bin/sh\n: > {marker}\n", encoding="utf-8")
    outside.chmod(0o755)
    payload = b"zip"
    digest = hashlib.sha256(payload).hexdigest()
    member = Path("draw.io.app/Contents/MacOS/draw.io")

    def symlink_runner(cmd: list[str]) -> None:
        if cmd and cmd[0] == "curl" and "-o" in cmd:
            dest = Path(cmd[cmd.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
        elif cmd and cmd[0] == "ditto":
            dest = Path(cmd[-1])
            cli = dest / member
            cli.parent.mkdir(parents=True, exist_ok=True)
            cli.symlink_to(outside)
        else:
            raise AssertionError(cmd)

    with pytest.raises(ExecutorError, match="regular file"):
        install_app(_drawio_method(sha256=digest), symlink_runner)
    assert not marker.exists()
    assert not (tmp_path / "Applications" / "draw.io.app").exists()


def test_declared_sha256_is_checked_on_an_unpinned_app_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    payload = b"zip-bytes"
    member = Path("App.app/Contents/MacOS/app")
    calls, runner = fixture_runner(None, {"app.zip": payload}, member=member)
    method = Method(
        kind="app",
        params={
            "url": "https://example.test/latest/App.zip",
            "app": "App.app",
            "sha256": "0" * 64,
        },
    )
    with pytest.raises(ChecksumMismatch):
        install_app(method, runner)
    assert not (tmp_path / "Applications" / "App.app").exists()
    assert calls[0][0] == "curl"
    assert not any(cmd and cmd[0] == "ditto" for cmd in calls)


def test_fresh_app_install_failure_after_relink_leaves_no_cli_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    payload = b"zip"
    digest = hashlib.sha256(payload).hexdigest()
    member = Path("draw.io.app/Contents/MacOS/draw.io")
    _, runner = fixture_runner(None, {"app.zip": payload}, member=member)
    real_replace = atomic.replace_symlink

    def fail_after_relink(link: Path, target: str) -> None:
        real_replace(link, target)
        raise OSError("relink failed")

    monkeypatch.setattr(apps_mod, "replace_symlink", fail_after_relink)
    with pytest.raises(ExecutorError):
        install_app(_drawio_method(sha256=digest), runner)
    assert not (tmp_path / ".local" / "bin" / "drawio").exists()
    assert not (tmp_path / "Applications" / "draw.io.app").exists()
    apps = tmp_path / "Applications"
    bad_suffix = (NEW_SUFFIX, OLD_SUFFIX)
    assert not any(p.name.endswith(bad_suffix) for p in apps.iterdir())
