import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from typing import TypedDict, Unpack

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
    unbuffered_argv,
)


class _PopenKwargs(TypedDict):
    """The exact keyword set `StreamingRunner.__call__` hands `subprocess.Popen`.

    Naming it lets every `Popen` double below declare its `**kwargs` precisely
    and forward them to the real class, instead of the untyped `**kwargs` that
    a bare `# type: ignore` used to paper over -- the hidden typing gap
    `.claude/python-tooling.md` names in its own "Avoid" example. Every field is
    required because production passes all seven on every launch, so a double
    that drops one stops compiling rather than silently diverging.
    """

    stdin: int
    stdout: int
    stderr: int
    text: bool
    bufsize: int
    env: Mapping[str, str]
    start_new_session: bool


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

    def fake_run(
        cmd: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        seen.update(
            {"check": check, "capture_output": capture_output, "text": text, "timeout": timeout}
        )
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


def test_streaming_runner_child_runs_in_its_own_session() -> None:
    # A vendor script that prompts on /dev/tty must not hang the TUI: the
    # child gets its own session, so it has no controlling terminal to read
    # from (D-10). getsid(0) == getpid() only when the child is its own
    # session leader.
    runner = StreamingRunner(lambda _tool_id, _line: None)
    runner.set_tool("rg")
    runner(
        [sys.executable, "-c", "import os, sys; sys.exit(0 if os.getsid(0) == os.getpid() else 3)"]
    )


def test_streaming_runner_tty_reader_fails_fast() -> None:
    # The alarm is a hang guard only: in its own session the child fails at
    # once (no controlling terminal); a regression that blocks on a real
    # terminal would be killed after 5 s and still fail the elapsed check.
    runner = StreamingRunner(lambda _tool_id, _line: None)
    runner.set_tool("rg")
    start = time.monotonic()
    with pytest.raises(CommandError):
        runner([sys.executable, "-c", "import signal; signal.alarm(5); open('/dev/tty').read(1)"])
    assert time.monotonic() - start < 5


def test_streaming_runner_missing_binary_is_127(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_popen(_argv: list[str], **_kwargs: Unpack[_PopenKwargs]) -> subprocess.Popen[str]:
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
        start_new_session: bool = False,
    ) -> subprocess.Popen[str]:
        proc = original_popen(
            args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            text=text,
            bufsize=bufsize,
            env=env,
            start_new_session=start_new_session,
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
    #
    # Asserted on the `env` mapping subprocess.Popen RECEIVED, not only on what
    # the child reports. Reading it back out of the child cannot tell an env
    # production set from one this process already exported, so on a host or CI
    # job with PYTHONUNBUFFERED=1 already in the environment the child-output
    # assertion passes whether or not installer/run.py sets anything. Deleting
    # the variable first removes the ambiguity for the child-side half too.
    monkeypatch.delenv("PYTHONUNBUFFERED", raising=False)

    recorded_env: list[Mapping[str, str]] = []
    original_popen = subprocess.Popen

    def recording_popen(argv: list[str], **kwargs: Unpack[_PopenKwargs]) -> subprocess.Popen[str]:
        recorded_env.append(kwargs["env"])
        return original_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording_popen)

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

    assert len(recorded_env) == 1
    env = recorded_env[0]
    assert env["PYTHONUNBUFFERED"] == "1", "the env rung did not reach Popen"
    assert env["PATH"], "env replaced os.environ instead of overriding it"
    assert env["HOME"], "env replaced os.environ instead of overriding it"

    lines = [line for _tool, line in seen]
    assert lines[0] == "1", f"PYTHONUNBUFFERED not set: {lines[0]}"
    assert lines[1] == "True", f"PATH not present: {lines[1]}"
    assert lines[2] == "True", f"HOME not present: {lines[2]}"


def test_unbuffered_argv_wraps_when_available() -> None:
    # Wrapped when available: a runner with stdbuf path hands Popen the wrapped argv.
    result = unbuffered_argv(["brew", "install", "rg"], "/usr/bin/stdbuf")
    assert result == ["/usr/bin/stdbuf", "-oL", "brew", "install", "rg"]


def test_unbuffered_argv_skips_when_absent() -> None:
    # Skipped when absent: stdbuf=None returns caller's argv unchanged.
    result = unbuffered_argv(["brew", "install", "rg"], None)
    assert result == ["brew", "install", "rg"]


def test_unbuffered_argv_not_double_wrapped_on_python_child() -> None:
    # Not double-wrapped: Python child with available stdbuf returns unwrapped.
    result = unbuffered_argv([sys.executable, "-c", "pass"], "/usr/bin/stdbuf")
    assert result == [sys.executable, "-c", "pass"]


@pytest.mark.parametrize("name", ["python", "python3", "python3.12"])
def test_unbuffered_argv_skips_a_bare_interpreter_name(name: str) -> None:
    # The shapes PYTHONUNBUFFERED really does cover are skipped by NAME too,
    # not only when argv[0] happens to be this process's sys.executable.
    assert unbuffered_argv([f"/usr/bin/{name}", "-c", "pass"], "/usr/bin/stdbuf") == [
        f"/usr/bin/{name}",
        "-c",
        "pass",
    ]


@pytest.mark.parametrize("name", ["pythonpy", "python-lsp-server", "python-tool"])
def test_unbuffered_argv_wraps_a_python_prefixed_non_interpreter(name: str) -> None:
    # A prefix test excluded these from rung 2 while PYTHONUNBUFFERED does
    # nothing for them -- i.e. the exact tool this phase exists to unblock
    # would silently keep bursting. They are real binaries, so they get wrapped.
    assert unbuffered_argv([name, "install"], "/usr/bin/stdbuf") == [
        "/usr/bin/stdbuf",
        "-oL",
        name,
        "install",
    ]


def test_unbuffered_argv_on_an_empty_cmd_is_not_a_python_child() -> None:
    # The empty-cmd guard: `_is_python_child([])` must answer False rather than
    # raise IndexError on `cmd[0]`. Reached through the public function, which
    # then has nothing to skip and wraps the (empty) argv.
    assert unbuffered_argv([], "/usr/bin/stdbuf") == ["/usr/bin/stdbuf", "-oL"]
    assert unbuffered_argv([], None) == []


def test_streaming_runner_unwrapped_retry_on_popen_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A stdbuf that vanishes after resolution does not fail the install.
    popen_attempts: list[list[str]] = []
    original_popen = subprocess.Popen

    def tracking_popen(argv: list[str], **kwargs: Unpack[_PopenKwargs]) -> subprocess.Popen[str]:
        popen_attempts.append(argv)
        # Raise for stdbuf argv, succeed for unwrapped
        if argv[0] == "/usr/bin/stdbuf":
            raise FileNotFoundError("stdbuf disappeared")
        # For the unwrapped retry
        return original_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", tracking_popen)

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


def test_streaming_runner_both_attempts_failing_is_still_127_with_caller_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Plan 01 Task 2's "both-attempts-fail-is-still-127-with-the-caller's-argv"
    # criterion. When the unwrapped retry ALSO raises, the caller still sees a
    # 127 naming the command they typed, exactly two launches were attempted
    # (no retry loop), and the detail names BOTH failures -- the traceback is
    # not on screen, and "127" alone cannot say which launch is the problem.
    attempts: list[list[str]] = []

    def always_raises(argv: list[str], **_kwargs: Unpack[_PopenKwargs]) -> subprocess.Popen[str]:
        attempts.append(argv)
        raise FileNotFoundError(f"vanished: {argv[0]}")

    monkeypatch.setattr(subprocess, "Popen", always_raises)
    runner = StreamingRunner(
        lambda _tool, _line: None, unbuffer=True, which=lambda _: "/usr/bin/stdbuf"
    )
    runner.set_tool("rg")

    cmd = ["brew", "install", "rg"]
    with pytest.raises(CommandError) as exc:
        runner(cmd)

    assert exc.value.returncode == 127
    assert exc.value.cmd == cmd
    assert attempts == [["/usr/bin/stdbuf", "-oL", "brew", "install", "rg"], cmd]
    assert "vanished: /usr/bin/stdbuf" in exc.value.detail
    assert "vanished: brew" in exc.value.detail
    # The first OSError survives as the chained context, not only in the text.
    cause = exc.value.__cause__
    assert isinstance(cause, OSError)
    assert isinstance(cause.__context__, OSError)
    assert "/usr/bin/stdbuf" in str(cause.__context__)


def test_streaming_runner_knob_off_makes_exactly_one_popen_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pins the `launch_argv is not cmd` IDENTITY branch at installer/run.py:235.
    # A runner that never opted in must keep today's single-attempt 127
    # behaviour byte for byte. Rewriting `unbuffered_argv`'s skip branches to
    # `return list(cmd)` -- a natural defensive tidy-up -- would make every
    # default-constructed runner silently launch twice on OSError, and
    # test_streaming_runner_missing_binary_is_127 would not notice, because its
    # double raises unconditionally and it asserts only on the final error.
    attempts: list[list[str]] = []

    def always_raises(argv: list[str], **_kwargs: Unpack[_PopenKwargs]) -> subprocess.Popen[str]:
        attempts.append(argv)
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(subprocess, "Popen", always_raises)
    runner = StreamingRunner(lambda _tool, _line: None)
    runner.set_tool("rg")

    with pytest.raises(CommandError) as exc:
        runner(["nope"])

    assert exc.value.returncode == 127
    assert attempts == [["nope"]]


def test_streaming_runner_knob_off_never_calls_which() -> None:
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


def test_streaming_runner_which_called_exactly_once_across_multiple_calls() -> None:
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
    # Failure text stays paste-able: a WRAPPED command that exits non-zero
    # reports the caller's argv, not the stdbuf-wrapped argv.
    #
    # The argv must be non-Python, or the ladder refuses to wrap it
    # (_is_python_child short-circuits) and this test silently degrades into a
    # second copy of test_streaming_runner_nonzero_exit_raises_command_error...,
    # leaving the wrapped non-zero-exit path uncovered. `seen_argv` is asserted
    # first so a future change that stops wrapping fails HERE rather than
    # quietly turning the rest of the test vacuous.
    seen_argv: list[list[str]] = []
    original_popen = subprocess.Popen

    def fake_popen(argv: list[str], **kwargs: Unpack[_PopenKwargs]) -> subprocess.Popen[str]:
        seen_argv.append(argv)
        # Child exits 3 whatever it was asked to launch: `brew` need not exist.
        return original_popen([sys.executable, "-c", "import sys; sys.exit(3)"], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = StreamingRunner(
        lambda _tool, _line: None, unbuffer=True, which=lambda _: "/usr/bin/stdbuf"
    )
    runner.set_tool("rg")

    cmd = ["brew", "install", "rg"]
    with pytest.raises(CommandError) as exc:
        runner(cmd)

    # It really WAS wrapped: Popen saw the stdbuf prefix.
    assert seen_argv == [["/usr/bin/stdbuf", "-oL", "brew", "install", "rg"]]
    # CommandError must carry the caller's argv, not the wrapped one.
    assert exc.value.cmd == cmd
    assert "stdbuf" not in " ".join(exc.value.cmd)
    assert "stdbuf" not in str(exc.value)


@pytest.mark.skipif(shutil.which("stdbuf") is None, reason="coreutils stdbuf not on PATH")
def test_stdbuf_wrapper_is_applied_end_to_end() -> None:
    # Against the real binary: a real stdbuf was execed by the production argv
    # and configured the child's environment. The child reports _STDBUF_O=L.
    seen: list[tuple[str, str]] = []
    runner = StreamingRunner(
        lambda tool_id, line: seen.append((tool_id, line)),
        unbuffer=True,
        which=shutil.which,
    )
    runner.set_tool("test")
    # Shell command that prints the _STDBUF_O env var set by stdbuf
    runner(["sh", "-c", "printf '%s\\n' \"$_STDBUF_O\""])

    lines = [line for _tool, line in seen]
    assert "L" in lines, f"stdbuf wrapper did not set _STDBUF_O=L. Lines: {lines}"
