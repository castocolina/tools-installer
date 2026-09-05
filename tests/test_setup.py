import io
from pathlib import Path

import pytest
from rich.console import Console

import setup
from installer.model import Tool
from installer.platform import Platform
from installer.session import Summary


class _DummyApp:
    def run(self) -> None:
        return None


class _FakeStdin:
    def isatty(self) -> bool:
        return True


def _platform() -> Platform:
    return Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


def test_main_fix_interactive_without_link_mode_opens_doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_calls: list[dict[str, str]] = []

    def fake_load_tools(_registry: object) -> list[Tool]:
        return []

    def fake_detect() -> Platform:
        return _platform()

    def fake_resolve_link_mode(_option: str | None) -> str:
        return "single"

    def fake_build_app(
        tools: list[Tool],
        platform: Platform,
        *,
        initial_view: str = "system",
        link_mode: str = "centralized",
    ) -> _DummyApp:
        build_calls.append(
            {
                "initial_view": initial_view,
                "link_mode": link_mode,
            }
        )
        return _DummyApp()

    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", fake_detect)
    monkeypatch.setattr(setup, "_resolve_link_mode", fake_resolve_link_mode)
    monkeypatch.setattr(setup, "_build_app", fake_build_app)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())

    console = Console(file=io.StringIO(), width=100, no_color=True)
    monkeypatch.setattr(setup, "Console", lambda: console)

    assert setup.main(["--fix"]) == 0
    assert build_calls == [{"initial_view": "doctor", "link_mode": "single"}]


def test_build_app_includes_the_omz_policy_after_the_tweaks() -> None:
    """Assert wiring by reading setup.py source.

    `_build_app` closes over import-time Path.home() constants and is a private
    composition-root helper, so calling it from tests trips pyright (private
    usage) and would be unsafe against the real home. The wire is the
    `omz_plugins_policy(` call after the tweak_policy generator.
    """
    src = (Path(__file__).resolve().parent.parent / "setup.py").read_text()
    body = src[src.index("def _build_app") :]
    ban = body.index("ban_policy(")
    tweak = body.index("tweak_policy(")
    omz = body.index("omz_plugins_policy(")
    assert ban < tweak < omz


def test_run_uninstall_is_wired_with_bundles_and_zshrc() -> None:
    """Assert wiring by reading setup.py source.

    `_run_uninstall` closes over import-time Path.home() constants and is a
    private composition-root helper, so calling it from tests trips pyright
    (private usage) and would be unsafe against the real home. The wire is
    the `bundles=applicable_bundles(platform)` and `zshrc_path=_ZSHRC` kwargs
    on the non-TTY `run_uninstall(` call.
    """
    src = (Path(__file__).resolve().parent.parent / "setup.py").read_text()
    body = src[src.index("def _run_uninstall") :]
    body = body[: body.index("def _run_guard")]
    assert "platform = detect()" in body
    assert "bundles=applicable_bundles(platform)" in body
    assert "zshrc_path=_ZSHRC" in body


def _stub_install_run(monkeypatch: pytest.MonkeyPatch, summary: Summary) -> list[str]:
    """Drive setup.main through a full (stubbed) install run and record whether
    the troubleshooting pointer was rendered."""
    rendered: list[str] = []

    def fake_load_tools(_registry: object) -> list[Tool]:
        return []

    def fake_load_categories(_registry: object) -> dict[str, str]:
        return {}

    def fake_run_wizard(*_args: object, **_kwargs: object) -> Summary:
        return summary

    def fake_resolve_link_mode(_option: str | None) -> str:
        return "centralized"

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    def fake_render_troubleshooting(_console: object) -> None:
        rendered.append("shown")

    console = Console(file=io.StringIO(), width=100, no_color=True)
    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup, "load_categories", fake_load_categories)
    monkeypatch.setattr(setup, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(setup, "_resolve_link_mode", fake_resolve_link_mode)
    monkeypatch.setattr(setup, "configure_path", noop)
    monkeypatch.setattr(setup, "_verify_and_clean", noop)
    monkeypatch.setattr(setup, "render_troubleshooting", fake_render_troubleshooting)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())
    monkeypatch.setattr(setup, "Console", lambda: console)
    return rendered


def test_a_dependency_failed_run_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    # A blocked dependent is a run that wanted to install something, could have,
    # and did not — a wrapper checking $? must not read that as a clean install.
    summary = Summary(
        installed=(),
        already=(),
        failed=(),
        no_method=("mmdc",),
        dependency_failed=("a", "b", "c"),
    )
    rendered = _stub_install_run(monkeypatch, summary)
    assert setup.main(["--all"]) == 1
    assert rendered == ["shown"]


def test_a_no_method_only_run_still_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unchanged, and deliberately so: a tool with no method on this platform was
    # never installable here, which is not a failure.
    summary = Summary(installed=("fd",), already=(), failed=(), no_method=("apt-upgrade",))
    rendered = _stub_install_run(monkeypatch, summary)
    assert setup.main(["--all"]) == 0
    assert rendered == []
