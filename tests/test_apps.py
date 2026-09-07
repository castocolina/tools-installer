import inspect
import os
import shlex
from pathlib import Path

import pytest

import installer.apps as apps_mod
from installer import atomic
from installer.apps import APP_KINDS, install_app, update_app
from installer.executors import ExecutorError
from installer.model import Method
from installer.run import Runner


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


def test_install_app_builds_curl_ditto_mv_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    install_app(_method(), runner)
    apps = tmp_path / "Applications"
    assert apps.is_dir()  # created before the pipeline runs
    expected = (
        "tmp=$(mktemp -d) && trap 'rm -rf \"$tmp\"' EXIT"
        ' && curl -fsSL -o "$tmp/app.zip" -- https://example.test/app.zip'
        ' && ditto -x -k "$tmp/app.zip" "$tmp/x"'
        f" && mv \"$tmp/x/\"'Demo App.app' {shlex.quote(str(apps))}/"
    )
    assert calls == [["sh", "-c", expected]]


def test_install_app_symlinks_declared_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    install_app(_method(cli="Contents/SharedSupport/bin/demo"), runner)
    assert len(calls) == 2
    bundle = tmp_path / "Applications" / "Demo App.app"
    assert calls[1] == [
        "ln",
        "-sf",
        str(bundle / "Contents/SharedSupport/bin/demo"),
        str(tmp_path / ".local" / "bin" / "demo"),
    ]
    assert (tmp_path / ".local" / "bin").is_dir()


def test_install_app_without_cli_runs_only_the_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    install_app(_method(), runner)
    assert len(calls) == 1


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
    assert len(calls) == 1  # the pipeline ran; only the symlink step failed


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
    assert " mv " in install_source


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
