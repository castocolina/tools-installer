import subprocess
import sys
import threading
import time
from collections.abc import Mapping

import pytest

from installer.run import (
    STREAM_DETAIL_LINES,
    TIMEOUT_CODE,
    CommandError,
    MethodAwareRunner,
    StreamingRunner,
    run_captured,
    run_command,
    run_output,
    run_query,
)


def test_run_command_success(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], check: bool):
        seen["cmd"] = cmd
        seen["check"] = check

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_command(["echo", "hi"])
    assert seen["cmd"] == ["echo", "hi"]
    assert seen["check"] is True


def test_run_command_raises_on_nonzero(monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd: list[str], check: bool):
        raise subprocess.CalledProcessError(returncode=2, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandError) as exc:
        run_command(["false"])
    assert exc.value.cmd == ["false"]
    assert exc.value.returncode == 2


def test_run_command_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd: list[str], check: bool):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandError) as exc:
        run_command(["nope"])
    assert exc.value.returncode == 127


def test_run_output_returns_stdout() -> None:
    assert run_output([sys.executable, "-c", "print('hello')"]) == "hello\n"


def test_run_captured_keeps_child_output_out_of_the_terminal(
    capfd: pytest.CaptureFixture[str],
) -> None:
    # Textual owns the terminal while the Doctor screen runs, so an
    # inherited-stdio child writes straight into the rendered frame.
    capfd.readouterr()
    run_captured(
        [sys.executable, "-c", "import sys; print('noise'); print('warn', file=sys.stderr)"]
    )
    captured = capfd.readouterr()
    assert "noise" not in captured.out
    assert "warn" not in captured.err


def test_run_output_folds_child_stderr_into_the_error() -> None:
    script = "import sys; print('boom', file=sys.stderr); sys.exit(3)"
    with pytest.raises(CommandError) as exc:
        run_output([sys.executable, "-c", script])
    assert exc.value.returncode == 3
    assert exc.value.detail == "boom"
    assert "boom" in str(exc.value)


def test_run_output_raises_when_binary_missing() -> None:
    with pytest.raises(CommandError) as exc:
        run_output(["definitely-not-a-real-binary-xyz"])
    assert exc.value.returncode == 127


def test_run_output_unbounded_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # A side-effecting child (`pnpm add -g` of a Puppeteer-carrying package)
    # legitimately takes minutes; killing it half-way is worse than waiting.
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object):  # type: ignore
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_output(["anything"])
    assert seen["timeout"] is None


def test_run_output_timeout_fails_fast_instead_of_hanging() -> None:
    # A query run while a TUI owns the terminal has no recoverable input path
    # if the child wedges, so the bound has to be on the call.
    with pytest.raises(CommandError) as exc:
        run_output([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2)
    assert exc.value.returncode == TIMEOUT_CODE
    assert "timed out" in str(exc.value)


def test_run_query_merges_env_over_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TI_PREEXISTING", "keep-me")
    script = (
        "import os;"
        " print(os.environ.get('TI_PREEXISTING', ''),"
        " os.environ.get('TI_OVERRIDE', ''),"
        " bool(os.environ.get('PATH')))"
    )
    out = run_query([sys.executable, "-c", script], env={"TI_OVERRIDE": "new"})
    assert "keep-me" in out
    assert "new" in out
    assert "True" in out


def test_run_query_accepts_nonzero_in_accept_codes() -> None:
    script = "import sys; print('payload'); print('err', file=sys.stderr); sys.exit(1)"
    out = run_query([sys.executable, "-c", script], accept_codes=(0, 1))
    assert "payload" in out


def test_run_query_rejected_code_carries_stdout_and_stderr() -> None:
    script = "import sys; print('payload'); print('err', file=sys.stderr); sys.exit(3)"
    with pytest.raises(CommandError) as exc:
        run_query([sys.executable, "-c", script], accept_codes=(0, 1))
    assert exc.value.returncode == 3
    assert exc.value.detail == "err"
    assert "payload" in exc.value.stdout


def test_run_query_timeout_uses_timeout_code() -> None:
    with pytest.raises(CommandError) as exc:
        run_query([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2)
    assert exc.value.returncode == TIMEOUT_CODE


def test_run_query_missing_binary_is_127() -> None:
    with pytest.raises(CommandError) as exc:
        run_query(["definitely-not-a-real-binary-xyz"])
    assert exc.value.returncode == 127


def test_streaming_runner_is_method_aware() -> None:
    assert isinstance(StreamingRunner(lambda _tool, _line: None), MethodAwareRunner)


def test_streaming_runner_emits_attributed_lines_without_newlines() -> None:
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(lambda tool_id, line: seen.append((tool_id, line)))
    runner.set_tool("rg")
    runner([sys.executable, "-c", "print('a'); print('b')"])
    assert seen == [("rg", "a"), ("rg", "b")]


def test_streaming_runner_emits_incrementally_before_child_exits() -> None:
    timestamps: list[float] = []

    def emit(_tool_id: str, _line: str) -> None:
        timestamps.append(time.monotonic())

    runner = StreamingRunner(emit)
    runner.set_tool("rg")
    script = "print('first', flush=True); import time; time.sleep(0.3); print('second', flush=True)"
    runner([sys.executable, "-u", "-c", script])
    assert len(timestamps) == 2
    assert timestamps[1] - timestamps[0] >= 0.3


def test_streaming_runner_method_started_emits_header_under_current_tool() -> None:
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(lambda tool_id, line: seen.append((tool_id, line)))
    runner.set_tool("rg")
    runner.method_started("brew")
    assert seen == [("rg", "-- trying brew --")]


def test_streaming_runner_requires_set_tool_before_call() -> None:
    runner = StreamingRunner(lambda _tool, _line: None)
    with pytest.raises(RuntimeError, match="set_tool"):
        runner([sys.executable, "-c", "print('x')"])


def test_streaming_runner_requires_set_tool_before_method_started() -> None:
    runner = StreamingRunner(lambda _tool, _line: None)
    with pytest.raises(RuntimeError, match="set_tool"):
        runner.method_started("brew")


def test_streaming_runner_nonzero_exit_raises_command_error_after_emitting() -> None:
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(lambda tool_id, line: seen.append((tool_id, line)))
    runner.set_tool("rg")
    script = "print('line1'); print('line2'); raise SystemExit(3)"
    cmd = [sys.executable, "-c", script]
    with pytest.raises(CommandError) as exc:
        runner(cmd)
    assert exc.value.cmd == cmd
    assert exc.value.returncode == 3
    assert "line2" in exc.value.detail
    assert seen == [("rg", "line1"), ("rg", "line2")]


def test_streaming_runner_missing_binary_is_127(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_popen(*_args: object, **_kwargs: object) -> subprocess.Popen[str]:  # type: ignore
        raise FileNotFoundError("nope")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    runner = StreamingRunner(lambda _tool, _line: None)
    runner.set_tool("rg")
    with pytest.raises(CommandError) as exc:
        runner(["nope"])
    assert exc.value.returncode == 127
    assert exc.value.cmd == ["nope"]


def test_streaming_runner_folds_stderr_into_the_same_stream() -> None:
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(lambda tool_id, line: seen.append((tool_id, line)))
    runner.set_tool("rg")
    script = "import sys; print('out', flush=True); print('err', file=sys.stderr, flush=True)"
    runner([sys.executable, "-c", script])
    assert seen == [("rg", "out"), ("rg", "err")]


def test_streaming_runner_bounds_detail_while_emitting_every_line() -> None:
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(lambda tool_id, line: seen.append((tool_id, line)))
    runner.set_tool("rg")
    script = "import sys\nfor i in range(500):\n    print(i)\nsys.exit(1)\n"
    with pytest.raises(CommandError) as exc:
        runner([sys.executable, "-c", script])
    assert [line for _tool, line in seen] == [str(i) for i in range(500)]
    detail_lines = exc.value.detail.split("\n") if exc.value.detail else []
    assert len(detail_lines) <= STREAM_DETAIL_LINES
    assert len(detail_lines) == STREAM_DETAIL_LINES
    assert detail_lines[-1] == "499"


def test_streaming_runner_reaps_child_when_emit_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, subprocess.Popen[str]] = {}
    original_popen = subprocess.Popen

    def wrapping_popen(
        args: list[str],
        stdin: int | None = None,
        stdout: int | None = None,
        stderr: int | None = None,
        text: bool = False,
        bufsize: int = 0,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.Popen[str]:
        proc = original_popen(
            args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            text=text,
            bufsize=bufsize,
            env=env,
        )
        captured["proc"] = proc
        return proc

    monkeypatch.setattr(subprocess, "Popen", wrapping_popen)

    def emit(_tool_id: str, line: str) -> None:
        if line == "first":
            raise RuntimeError("callback exploded")

    runner = StreamingRunner(emit)
    runner.set_tool("rg")
    script = (
        "import sys\n"
        "print('first', flush=True)\n"
        "chunk = 'x' * 1024\n"
        "for _ in range(300):\n"
        "    sys.stdout.write(chunk)\n"
        "sys.stdout.flush()\n"
    )
    cmd = [sys.executable, "-u", "-c", script]
    caught: list[BaseException] = []

    def target() -> None:
        try:
            runner(cmd)
        except BaseException as exc:
            caught.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(30)
    assert not thread.is_alive()
    assert caught
    assert isinstance(caught[0], RuntimeError)
    assert "callback exploded" in str(caught[0])
    assert captured["proc"].returncode is not None


def test_streaming_runner_block_buffering_child_streams_live_when_unbuffered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A child that block-buffers by default (no -u, no flush=True) streams
    # live AT THE RUNNER when PYTHONUNBUFFERED is set in its environment.
    # Delete PYTHONUNBUFFERED first so the property is proved by production
    # code setting it rather than an inherited variable.
    monkeypatch.delenv("PYTHONUNBUFFERED", raising=False)

    timestamps: list[float] = []

    def emit(_tool_id: str, _line: str) -> None:
        timestamps.append(time.monotonic())

    runner = StreamingRunner(emit)
    runner.set_tool("test")
    # Script: block-buffered (no -u, no flush), 1.0s delay between prints
    script = "print('first'); import time; time.sleep(1.0); print('second')"
    runner([sys.executable, "-c", script])

    assert len(timestamps) == 2
    gap = timestamps[1] - timestamps[0]
    # Real separation is a full second, 0.5s floor leaves 0.5s scheduling slack
    # so this test discriminates on buffering not on scheduler luck.
    assert gap >= 0.5, (
        f"Lines arrived {gap:.3f}s apart, expected >= 0.5s (buffering still happening)"
    )


def test_streaming_runner_env_rung_is_unconditional_even_with_unbuffer_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The PYTHONUNBUFFERED env rung is unconditional: a runner built with
    # the default unbuffer=False still launches its child with
    # PYTHONUNBUFFERED set to "1", and PATH/HOME survive.
    # Verify env vars are passed to the child using real execution
    script = (
        "import os; "
        "print(os.environ.get('PYTHONUNBUFFERED')); "
        "print(bool(os.environ.get('PATH'))); "
        "print(bool(os.environ.get('HOME')))"
    )

    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(lambda tool_id, line: seen.append((tool_id, line)))
    runner.set_tool("test")
    runner([sys.executable, "-c", script])

    lines = [line for _tool, line in seen]
    assert lines[0] == "1", f"PYTHONUNBUFFERED not set: {lines[0]}"
    assert lines[1] == "True", f"PATH not present: {lines[1]}"
    assert lines[2] == "True", f"HOME not present: {lines[2]}"


def test_unbuffered_argv_wraps_when_available() -> None:
    # Wrapped when available: a runner with stdbuf path hands Popen the wrapped argv.
    from installer.run import unbuffered_argv

    result = unbuffered_argv(["brew", "install", "rg"], "/usr/bin/stdbuf")
    assert result == ["/usr/bin/stdbuf", "-oL", "brew", "install", "rg"]


def test_unbuffered_argv_skips_when_absent() -> None:
    # Skipped when absent: stdbuf=None returns caller's argv unchanged.
    from installer.run import unbuffered_argv

    result = unbuffered_argv(["brew", "install", "rg"], None)
    assert result == ["brew", "install", "rg"]


def test_unbuffered_argv_not_double_wrapped_on_python_child() -> None:
    # Not double-wrapped: Python child with available stdbuf returns unwrapped.
    from installer.run import unbuffered_argv

    result = unbuffered_argv([sys.executable, "-c", "pass"], "/usr/bin/stdbuf")
    assert result == [sys.executable, "-c", "pass"]


def test_streaming_runner_unwrapped_retry_on_popen_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A stdbuf that vanishes after resolution does not fail the install.
    popen_attempts: list[list[str]] = []
    original_popen = subprocess.Popen

    def tracking_popen(argv: list[str], **kwargs):  # type: ignore
        popen_attempts.append(argv)
        # Raise for stdbuf argv, succeed for unwrapped
        if argv[0] == "/usr/bin/stdbuf":
            raise FileNotFoundError("stdbuf disappeared")
        # For the unwrapped retry
        return original_popen(argv, **kwargs)  # type: ignore

    monkeypatch.setattr(subprocess, "Popen", tracking_popen)  # type: ignore

    runner = StreamingRunner(
        lambda _tool, _line: None, unbuffer=True, which=lambda _: "/usr/bin/stdbuf"
    )
    runner.set_tool("test")
    # Use a non-Python command so it's wrapped
    runner(["sh", "-c", "echo ok"])

    # Should have tried twice: wrapped, then unwrapped
    assert len(popen_attempts) == 2
    assert popen_attempts[0][0] == "/usr/bin/stdbuf"
    assert popen_attempts[1][0] == "sh"


def test_streaming_runner_knob_off_never_calls_which(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Not wrapped when the knob is off: which is never called.
    which_calls: list[str] = []

    def fake_which(name: str) -> str | None:
        which_calls.append(name)
        return "/usr/bin/stdbuf"

    runner = StreamingRunner(lambda _tool, _line: None, unbuffer=False, which=fake_which)
    runner.set_tool("test")
    runner([sys.executable, "-c", "print('ok')"])

    # which should never have been called
    assert which_calls == []


def test_streaming_runner_which_called_exactly_once_across_multiple_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Resolved once: which is called once in constructor, not per __call__.
    which_calls: list[str] = []

    def fake_which(name: str) -> str | None:
        which_calls.append(name)
        return "/usr/bin/stdbuf"

    runner = StreamingRunner(lambda _tool, _line: None, unbuffer=True, which=fake_which)
    # which already called once in constructor
    assert which_calls == ["stdbuf"]

    runner.set_tool("test")
    runner([sys.executable, "-c", "print('1')"])
    runner([sys.executable, "-c", "print('2')"])

    # Should still be exactly one call from constructor
    assert which_calls == ["stdbuf"]


def test_streaming_runner_caller_argv_in_error_when_wrapped_command_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Failure text stays paste-able: wrapped command that exits non-zero
    # reports the caller's argv, not the stdbuf-wrapped argv.
    original_popen = subprocess.Popen

    def fake_popen(argv: list[str], **kwargs):  # type: ignore
        # Child exits 3
        return original_popen([sys.executable, "-c", "import sys; sys.exit(3)"], **kwargs)  # type: ignore

    monkeypatch.setattr(subprocess, "Popen", fake_popen)  # type: ignore

    runner = StreamingRunner(
        lambda _tool, _line: None, unbuffer=True, which=lambda _: "/usr/bin/stdbuf"
    )
    runner.set_tool("test")

    cmd = [sys.executable, "-c", "print('fail')"]
    with pytest.raises(CommandError) as exc:
        runner(cmd)

    # CommandError must carry the caller's argv, not the wrapped one
    assert exc.value.cmd == cmd
    assert "/usr/bin/stdbuf" not in exc.value.cmd


@pytest.mark.skipif(
    __import__("shutil").which("stdbuf") is None, reason="coreutils stdbuf not on PATH"
)
def test_stdbuf_wrapper_is_applied_end_to_end() -> None:
    # Against the real binary: a real stdbuf was execed by the production argv
    # and configured the child's environment. The child reports _STDBUF_O=L.
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(
        lambda tool_id, line: seen.append((tool_id, line)),
        unbuffer=True,
        which=__import__("shutil").which,
    )
    runner.set_tool("test")
    # Shell command that prints the _STDBUF_O env var set by stdbuf
    runner(["sh", "-c", "printf '%s\\n' \"$_STDBUF_O\""])

    lines = [line for _tool, line in seen]
    assert "L" in lines, f"stdbuf wrapper did not set _STDBUF_O=L. Lines: {lines}"
