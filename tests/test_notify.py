"""Hermetic desktop notification contracts."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from installer.notify import (
    no_notifier,
    notifier_for,
    notify_send,
    notify_send_argv,
    osascript,
    osascript_argv,
    reason_line,
)
from installer.run import CommandError, run_output


def test_notify_send_argv_is_exact() -> None:
    assert notify_send_argv("/x/notify-send", "2 tool updates available", "a, b") == [
        "/x/notify-send",
        "--app-name=tools-installer",
        "--urgency=normal",
        "--",
        "2 tool updates available",
        "a, b",
    ]
    assert notify_send_argv("/x/notify-send", "-x", "--urgency=critical")[-3:] == [
        "--",
        "-x",
        "--urgency=critical",
    ]


def test_osascript_argv_is_golden() -> None:
    source = [
        "/usr/bin/osascript",
        "-e",
        "on run argv",
        "-e",
        "display notification (item 2 of argv) with title (item 1 of argv)",
        "-e",
        "end run",
    ]
    assert osascript_argv("/usr/bin/osascript", "T", "B") == [*source, "T", "B"]
    for title, body in [('He said "hi"', "back\\slash"), ("ünïcode 通知", 'He said "hi"')]:
        argv = osascript_argv("/usr/bin/osascript", title, body)
        assert argv == [*source, title, body]
        assert all('"' not in part and "\\" not in part and part.isascii() for part in argv[:-2])
        assert "--" not in argv


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> str:
        self.calls.append((argv, kwargs))
        return ""


def test_notify_send_passes_the_bus_address_when_set() -> None:
    run = Recorder()
    env = {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus", "KEEP": "1"}
    assert (
        notify_send(
            "2 tool updates available",
            "a, b",
            which=lambda _: "/x/notify-send",
            run=run,
            environ=env,
            uid=1000,
            is_socket=lambda _: False,
        )
        is None
    )
    assert run.calls == [
        (
            [
                "/x/notify-send",
                "--app-name=tools-installer",
                "--urgency=normal",
                "--",
                "2 tool updates available",
                "a, b",
            ],
            {"timeout": 10, "new_session": False, "env": env},
        )
    ]


@pytest.mark.parametrize(
    ("runtime", "sockets", "errors", "expected"),
    [
        ("/r", ["/r/bus"], [], "unix:path=/r/bus"),
        ("/r,a;b", ["/r,a;b/bus"], [], "unix:path=/r%2Ca%3Bb/bus"),
        (None, ["/run/user/1234/bus"], [], "unix:path=/run/user/1234/bus"),
        ("/r", ["/run/user/1234/bus"], [], "unix:path=/run/user/1234/bus"),
        ("/r", ["/r/bus", "/run/user/1234/bus"], [], "unix:path=/r/bus"),
        ("/r", [], [], None),
        ("/r", ["/run/user/1234/bus"], ["/r/bus"], "unix:path=/run/user/1234/bus"),
        ("/r", [], ["/r/bus", "/run/user/1234/bus"], None),
    ],
)
def test_notify_send_derives_the_bus_from_the_runtime_dir(
    runtime: str | None, sockets: list[str], errors: list[str], expected: str | None
) -> None:
    env = {"XDG_RUNTIME_DIR": runtime} if runtime is not None else {}

    def probe(path: Path) -> bool:
        if str(path) in errors:
            raise PermissionError("unavailable")
        return str(path) in sockets

    run = Recorder()
    assert (
        notify_send(
            "s",
            "b",
            which=lambda _: "/x/notify-send",
            run=run,
            environ=env,
            uid=1234,
            is_socket=probe,
        )
        is None
    )
    assert run.calls[0][1]["env"].get("DBUS_SESSION_BUS_ADDRESS") == expected
    if expected is None:
        assert "DBUS_SESSION_BUS_ADDRESS" not in run.calls[0][1]["env"]


@pytest.mark.parametrize("env", [{}, {"DBUS_SESSION_BUS_ADDRESS": ""}])
def test_notify_send_leaves_the_bus_unset_never_empty(env: dict[str, str]) -> None:
    run = Recorder()
    assert (
        notify_send(
            "s",
            "b",
            which=lambda _: "/x/notify-send",
            run=run,
            environ=env,
            uid=1000,
            is_socket=lambda _: False,
        )
        is None
    )
    assert "DBUS_SESSION_BUS_ADDRESS" not in run.calls[0][1]["env"]


def test_notify_send_missing_binary_is_a_skip_reason() -> None:
    run = Recorder()
    assert (
        notify_send(
            "s", "b", which=lambda _: None, run=run, environ={}, uid=1, is_socket=lambda _: False
        )
        == "notify-send not found"
    )
    assert osascript("s", "b", which=lambda _: None, run=run) == "osascript not found"
    assert not run.calls


@pytest.mark.parametrize("body", ["a", ", ".join(f"id{i}" for i in range(12))])
def test_one_message_is_one_child_call(body: str) -> None:
    run = Recorder()
    assert (
        notify_send(
            "s",
            body,
            which=lambda _: "/x/notify-send",
            run=run,
            environ={},
            uid=1,
            is_socket=lambda _: False,
        )
        is None
    )
    assert len(run.calls) == 1


@pytest.mark.parametrize("platform,name", [("fedora", "notify-send"), ("macos", "osascript")])
@pytest.mark.parametrize(
    "detail",
    [
        "Failed to show notification: no bus\nsecond line",
        "",
        "\x1b[31msecret",
        "a\tb",
        "Authorization: Bearer ghp_planted_value",
        "a, b",
    ],
)
@pytest.mark.parametrize(
    "code,suffix", [(1, "exited 1"), (124, "timed out"), (127, "could not be started")]
)
def test_failures_map_to_fixed_reasons(
    platform: str, name: str, detail: str, code: int, suffix: str
) -> None:
    def fail(argv: list[str], **_kwargs: Any) -> str:
        raise CommandError(argv, code, detail=detail)

    result = notifier_for(
        platform,
        which=lambda _: "/x/" + name,
        run=fail,
        environ={},
        uid=1,
        is_socket=lambda _: False,
    )("s", "a, b")
    assert result == f"{name} {suffix}"
    assert result is not None
    assert all(
        part not in result
        for part in ("a, b", "-e ", "display notification", "/x/", "ghp_planted_value")
    )


def _script(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / "bin" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


def test_a_real_osascript_child_that_fails_silently_gives_a_fixed_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    for body in ("exit 1", "echo boom >&2\nexit 1"):
        binary = _script(tmp_path, "osascript", body)
        assert (
            osascript(
                "2 tool updates available",
                "a, b",
                which=lambda _, path=binary: str(path),
                run=run_output,
            )
            == "osascript exited 1"
        )


def test_the_default_runner_closes_the_notifier_childs_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert (
        notifier_for(
            "fedora",
            which=lambda _: "/x/notify-send",
            environ={},
            uid=1000,
            is_socket=lambda _: False,
        )("s", "b")
        is None
    )
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["start_new_session"] is False
    assert seen["timeout"] == 10


@pytest.mark.parametrize(
    "platform,name",
    [
        ("macos", "osascript"),
        ("fedora", "notify-send"),
        ("debian", "notify-send"),
        ("arch", "notify-send"),
    ],
)
def test_notifier_for_picks_the_tool_by_platform(platform: str, name: str) -> None:
    seen: list[str] = []

    def which(binary: str) -> str:
        seen.append(binary)
        return "/x/" + binary

    run = Recorder()
    notify = notifier_for(platform, which, run, environ={}, uid=1, is_socket=lambda _: False)
    assert seen == []
    assert notify("s", "b") is None
    assert seen == [name]
    assert Path(run.calls[0][0][0]).name == name

    def fail_lookup(_name: str) -> str:
        raise AssertionError("lookup at construction")

    assert callable(notifier_for(platform, fail_lookup, run, environ={}))


def test_a_real_child_gets_the_argv_and_the_bus(tmp_path: Path) -> None:
    argv, bus = tmp_path / "argv", tmp_path / "bus"
    binary = _script(
        tmp_path,
        "notify-send",
        f'printf "%s\\n" "$@" > "{argv}"\n'
        f'printf "%s" "${{DBUS_SESSION_BUS_ADDRESS-unset}}" > "{bus}"',
    )
    for env, expected in [
        ({"DBUS_SESSION_BUS_ADDRESS": "unix:path=/x"}, "unix:path=/x"),
        ({}, "unset"),
    ]:
        assert (
            notify_send(
                "s",
                "a, b",
                which=lambda _: str(binary),
                run=run_output,
                environ=env,
                uid=1,
                is_socket=lambda _: False,
            )
            is None
        )
        assert argv.read_text().splitlines() == [
            "--app-name=tools-installer",
            "--urgency=normal",
            "--",
            "s",
            "a, b",
        ]
        assert bus.read_text() == expected
    _script(tmp_path, "notify-send", "echo boom >&2\nexit 1")
    assert (
        notify_send(
            "s",
            "a, b",
            which=lambda _: str(binary),
            run=run_output,
            environ={},
            uid=1,
            is_socket=lambda _: False,
        )
        == "notify-send exited 1"
    )


def test_reason_line_is_one_sanitized_bounded_line() -> None:
    assert reason_line("\n  \n  a\x00\x1b\x7f\x85\x9bb\tc  \nsecond") == "ab\tc"
    assert reason_line("x" * 400) == "x" * 300
    assert reason_line("\n  \n") == ""


def test_the_default_notifier_sends_nothing() -> None:
    assert no_notifier("s", "b") == "no notifier is configured"
