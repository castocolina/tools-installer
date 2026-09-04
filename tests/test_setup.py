import io

import pytest
from rich.console import Console

import setup
from installer.model import Tool
from installer.platform import Platform


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
        initial_view: str = "catalog",
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
