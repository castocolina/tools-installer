import shlex
from pathlib import Path

import pytest

import installer.apps as apps_mod
from installer.apps import APP_KINDS, install_app
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
