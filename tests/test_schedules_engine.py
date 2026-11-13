"""The Schedules engine: turning a schedule on and off against recording systemctl fakes.

Every systemctl call goes to a recording runner; `which`, `present` and `read_models` are fakes
and every file lands under `tmp_path`. Private names are read through `vars(schedules)`.
"""

import fcntl
import os
import plistlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from installer import daemon, receipts, runlock, schedules, systemd_daemon
from installer.cursor_shim import ShimReport, is_our_shim
from installer.daemon import DaemonScheduleError
from installer.run import CommandError
from installer.schedules import (
    INTERVAL_MESSAGE,
    MODEL_CHARSET_MESSAGE,
    MODEL_SHAPE_MESSAGE,
    SCHEDULES,
    START_MESSAGE,
    RowState,
    ScheduleContext,
    ScheduleRecord,
    ScheduleUnavailable,
    basename_for,
    calendar_dicts,
    clean_unit_path,
    context_for,
    label_for,
    load_state,
    retime,
    row_state,
    runner_argv,
    schedule_by_id,
    set_cursor_model,
    slots,
    state_lock_path,
    turn_off,
    turn_on,
)

CHECKOUT = Path(__file__).resolve().parent.parent
DEFAULT_GRID = ((0, 0), (6, 0), (12, 0), (18, 0))
CLAUDE_BASENAME = "tools-installer-schedule-update-claude"
SHARED_NAMES = (
    "runner.py",
    "prune-tmp-linux.sh",
    "prune-user-tmpdir.sh",
    "lib/prune-tmp-common.sh",
)


class Recorder:
    """Records every systemctl or launchctl argv; fails a given (verb, occurrence) pair.

    `enable` and `disable` keep the timer's wants link the way systemd would."""

    def __init__(
        self, unit_dir: Path, *, fail_on: frozenset[tuple[str, int]] = frozenset()
    ) -> None:
        self.unit_dir = unit_dir
        self.calls: list[list[str]] = []
        self.fail_on = fail_on
        self.hooks: dict[str, Callable[[list[str]], None]] = {}
        self.seen: dict[str, int] = {}

    def arm(self, fail_on: frozenset[tuple[str, int]]) -> None:
        """Fail these (verb, occurrence) pairs, counting from now."""
        self.fail_on = fail_on
        self.seen.clear()

    def verb(self, cmd: list[str]) -> str:
        return cmd[2] if cmd[0] == "systemctl" else cmd[1]

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        verb = self.verb(cmd)
        self.seen[verb] = self.seen.get(verb, 0) + 1
        if verb in self.hooks:
            self.hooks[verb](cmd)
        if (verb, self.seen[verb]) in self.fail_on:
            raise CommandError(cmd, 5)
        if cmd[0] != "systemctl" or not cmd[-1].endswith(".timer"):
            return
        link = self.unit_dir / "timers.target.wants" / cmd[-1]
        if verb == "enable" and not link.is_symlink():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(self.unit_dir / cmd[-1])
        elif verb == "disable":
            link.unlink(missing_ok=True)

    def text(self) -> list[str]:
        return [" ".join(cmd[2:] if cmd[0] == "systemctl" else cmd[1:]) for cmd in self.calls]


class Output:
    """The read-only systemctl answers: the manager state, every unit active, no competitor."""

    def __init__(self, manager: str = "running") -> None:
        self.manager = manager
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        if "is-system-running" in cmd:
            return self.manager
        return "active" if "is-active" in cmd else ""


@dataclass
class Models:
    answer: tuple[str, ...] | None = ("gpt-5.6-sol-xhigh", "gpt-5.5")
    calls: list[Path] = field(default_factory=list[Path])
    on_call: Callable[[], None] | None = None

    def __call__(self, agent: Path) -> tuple[str, ...] | None:
        self.calls.append(agent)
        if self.on_call is not None:
            self.on_call()
        return self.answer


@dataclass
class Env:
    ctx: ScheduleContext
    run: Recorder
    output: Output
    models: Models
    home: Path
    uv: Path


def make_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    os_key: str = "fedora",
    present: frozenset[str] = frozenset({"claude", "opencode", "cursor-agent", "copilot", "pi"}),
    manager: str = "running",
    systemctl: bool = True,
    fail_on: frozenset[tuple[str, int]] = frozenset(),
) -> Env:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(parents=True, exist_ok=True)
    uv.write_text("#!/bin/sh\n")
    uv.chmod(0o755)
    environ = {"TMPDIR": str(tmp_path / "tmp")}
    found = {"uv": str(uv), "launchctl": "/usr/bin/launchctl"}
    if systemctl:
        found["systemctl"] = "/usr/bin/systemctl"
    output = Output(manager)
    models = Models()
    ctx = context_for(
        os_key,
        checkout=CHECKOUT,
        read_models=models,
        run=Recorder(home / ".config/systemd/user", fail_on=fail_on),
        read_output=output,
        which=found.get,
        present=present.__contains__,
        environ=environ,
    )
    run = ctx.run
    assert isinstance(run, Recorder)
    return Env(ctx, run, output, models, home, uv)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return make_env(tmp_path, monkeypatch)


def tree(root: Path) -> dict[str, bytes | str]:
    """Every path under `root` with its bytes (a symlink with its target)."""
    out: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")) if root.exists() else []:
        key = str(path.relative_to(root))
        out[key] = (
            os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else ""
        )
    return out


def files_left(root: Path) -> list[str]:
    return [
        str(path.relative_to(root))
        for path in sorted(root.rglob("*"))
        if (path.is_file() or path.is_symlink())
        and path.name not in {"schedules.json", "schedules.json.lock"}
    ]


def test_turn_on_then_off_leaves_nothing_behind(env: Env) -> None:
    ctx = env.ctx
    report = turn_on(ctx, "update-claude")

    sources = {
        "runner.py": CHECKOUT / "installer/helper_assets/schedule_runner.py",
        **{name: CHECKOUT / "scripts" / name for name in SHARED_NAMES[1:]},
    }
    for name, source in sources.items():
        assert (ctx.data_dir / name).read_bytes() == source.read_bytes()
        assert os.access(ctx.data_dir / name, os.X_OK)
    state = load_state(ctx.state_path).state
    assert {Path(a.path) for a in state.shared} == {ctx.data_dir / n for n in SHARED_NAMES}

    unit_dir = ctx.unit_dir
    service = unit_dir / f"{CLAUDE_BASENAME}.service"
    timer = unit_dir / f"{CLAUDE_BASENAME}.timer"
    argv = [
        str(env.uv),
        "run",
        "--no-project",
        "--script",
        str(ctx.data_dir / "runner.py"),
        "update",
        "claude",
        "--installer",
        str(CHECKOUT),
        "--uv",
        str(env.uv),
        "--log",
        str(ctx.log_path),
        "--lock",
        str(ctx.lock_path),
        "--cap-bytes",
        "262144",
    ]
    lines = service.read_text().splitlines()
    assert "ExecStart=" + " ".join(f'"{token}"' for token in argv) in lines
    path = clean_unit_path(env.home, platform_os="fedora", environ=ctx.environ)
    assert f'Environment="PATH={path}"' in lines
    assert f'Environment="HOME={env.home}"' in lines
    assert f'Environment="TMPDIR={ctx.tmpdir}"' in lines
    timer_lines = timer.read_text().splitlines()
    assert "OnCalendar=*-*-* 00,06,12,18:00:00" in timer_lines
    assert "Persistent=true" in timer_lines
    assert env.run.text() == [
        "daemon-reload",
        f"enable {CLAUDE_BASENAME}.timer",
        f"restart {CLAUDE_BASENAME}.timer",
    ]

    record = state.records["update-claude"]
    link = unit_dir / "timers.target.wants" / f"{CLAUDE_BASENAME}.timer"
    assert record.decided is True
    assert {Path(a.path) for a in record.files} == {service, timer, link}
    assert all(receipts.matches(a, rehash=True) for a in record.files)
    assert report.changed is True
    assert report.next_run is not None
    assert (report.next_run.hour, report.next_run.minute) in DEFAULT_GRID

    env.run.calls.clear()
    off = turn_off(ctx, "update-claude")
    assert env.run.text() == [
        f"disable --now {CLAUDE_BASENAME}.timer",
        f"clean --what=state {CLAUDE_BASENAME}.timer",
        "daemon-reload",
    ]
    assert off.warnings == ()
    assert not ctx.data_dir.exists()
    after = load_state(ctx.state_path).state
    assert after.records["update-claude"].decided is False
    assert after.records["update-claude"].files == ()
    assert after.shared == ()
    assert files_left(env.home) == []


def test_paths_and_names() -> None:
    assert basename_for("update-claude") == "tools-installer-schedule-update-claude"
    assert basename_for("tmp-cleanup") == "tools-installer-prune-tmp"
    assert label_for("update-claude") == "com.tools-installer.schedule.update-claude"
    assert label_for("tmp-cleanup") == "com.tools-installer.prune-tmpdir"


def test_failed_first_registration_leaves_no_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, fail_on=frozenset({("enable", 1)}))
    with pytest.raises(CommandError):
        turn_on(env.ctx, "update-claude")
    assert files_left(env.home) == []
    assert not (env.ctx.unit_dir / f"{CLAUDE_BASENAME}.service").exists()
    assert load_state(env.ctx.state_path).state.records == {}
    assert "disable " + f"{CLAUDE_BASENAME}.timer" in env.run.text()


def test_existing_symlink_at_a_unit_path_is_refused(env: Env, tmp_path: Path) -> None:
    victim = tmp_path / "victim.service"
    victim.write_text("[Service]\nExecStart=/bin/true\n")
    service = env.ctx.unit_dir / f"{CLAUDE_BASENAME}.service"
    service.parent.mkdir(parents=True)
    service.symlink_to(victim)
    with pytest.raises(OSError, match=f"{CLAUDE_BASENAME}.service"):
        turn_on(env.ctx, "update-claude")
    assert victim.read_text() == "[Service]\nExecStart=/bin/true\n"
    assert env.run.calls == []
    assert files_left(env.home) == [str(service.relative_to(env.home))]


UNAVAILABLE = {
    "no-bus": "unavailable: no user timer manager",
    "no-systemctl": "unavailable: no user timer manager",
    "no-claude": "unavailable: claude not installed",
}


def unavailable_env(case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    if case == "no-bus":
        return make_env(tmp_path, monkeypatch, manager="")
    if case == "no-systemctl":
        return make_env(tmp_path, monkeypatch, systemctl=False)
    return make_env(tmp_path, monkeypatch, present=frozenset())


@pytest.mark.parametrize("case", sorted(UNAVAILABLE))
def test_turn_on_refuses_unavailable(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = unavailable_env(case, tmp_path, monkeypatch)
    with pytest.raises(ScheduleUnavailable) as raised:
        turn_on(env.ctx, "update-claude")
    assert str(raised.value) == UNAVAILABLE[case]
    assert isinstance(raised.value, OSError)


@pytest.mark.parametrize("case", sorted(UNAVAILABLE))
def test_no_manager_writes_nothing(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = unavailable_env(case, tmp_path, monkeypatch)
    before = tree(env.home)
    with pytest.raises(ScheduleUnavailable):
        turn_on(env.ctx, "update-claude")
    assert tree(env.home) == before
    assert env.run.calls == []


# --- Task 2: macOS agents, re-timing, the cursor-agent shim hook, shared-asset refcounting ---


def macos_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return make_env(tmp_path, monkeypatch, os_key="macos")


def test_macos_turn_on_writes_an_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = macos_env(tmp_path, monkeypatch)
    ctx = env.ctx
    log = ctx.launchd_log_path
    assert not log.parent.exists()
    seen: list[tuple[bool, bool]] = []
    env.run.hooks["bootstrap"] = lambda _cmd: seen.append(
        (log.parent.is_dir(), log.is_file() and log.read_bytes() == b"")
    )

    turn_on(ctx, "update-claude")

    assert seen == [(True, True)]  # R1-06: the log exists when launchd registers
    label = "com.tools-installer.schedule.update-claude"
    plist_path = env.home / "Library/LaunchAgents" / f"{label}.plist"
    plist = plistlib.loads(plist_path.read_bytes())
    schedule = schedule_by_id("update-claude")
    assert plist["Label"] == label
    assert plist["ProgramArguments"] == runner_argv(ctx, schedule, env.uv)
    assert plist["StartCalendarInterval"] == calendar_dicts(slots(6, "00:00"))
    assert plist["StandardOutPath"] == plist["StandardErrorPath"] == str(log)
    assert str(log) != str(ctx.log_path)
    assert env.run.text() == [
        f"bootout gui/{ctx.uid}/{label}",
        f"bootstrap gui/{ctx.uid} {plist_path}",
    ]
    record = load_state(ctx.state_path).state.records["update-claude"]
    assert [Path(a.path) for a in record.files] == [plist_path]

    env.run.calls.clear()
    turn_off(ctx, "update-claude")
    assert env.run.text() == [f"bootout gui/{ctx.uid}/{label}"]
    assert not plist_path.exists()
    assert not ctx.data_dir.exists()


def test_retime(env: Env) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    timer = ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"
    before = timer.read_bytes()
    with pytest.raises(DaemonScheduleError, match=INTERVAL_MESSAGE):
        retime(ctx, "update-claude", 5, "00:00")
    with pytest.raises(DaemonScheduleError, match=START_MESSAGE):
        retime(ctx, "update-claude", 6, "24:00")
    assert timer.read_bytes() == before

    env.run.calls.clear()
    assert retime(ctx, "update-claude", 6, "00:00").changed is False
    assert env.run.calls == []

    report = retime(ctx, "update-claude", 8, "01:30")
    assert report.changed is True
    assert report.next_run is not None
    assert (report.next_run.hour, report.next_run.minute) in ((1, 30), (9, 30), (17, 30))
    assert "OnCalendar=*-*-* 01,09,17:30:00" in timer.read_text().splitlines()
    timer_name = f"{CLAUDE_BASENAME}.timer"
    assert env.run.text() == [
        f"clean --what=state {timer_name}",
        "daemon-reload",
        f"enable {timer_name}",
        f"restart {timer_name}",
    ]
    record = load_state(ctx.state_path).state.records["update-claude"]
    assert (record.interval, record.start) == (8, "01:30")
    assert all(receipts.matches(a, rehash=True) for a in record.files)

    # an off row only saves the values and writes nothing
    env.run.calls.clear()
    off_report = retime(ctx, "update-opencode", 8, "01:30")
    assert off_report.changed is True
    assert off_report.next_run is None
    assert env.run.calls == []
    assert not (ctx.unit_dir / "tools-installer-schedule-update-opencode.timer").exists()
    saved = load_state(ctx.state_path).state.records["update-opencode"]
    assert (saved.interval, saved.start, saved.decided, saved.files) == (8, "01:30", None, ())


def test_retime_failure_restores_the_old_timer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, fail_on=frozenset({("restart", 2)}))
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    timer = ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"
    before = timer.read_bytes()
    with pytest.raises(CommandError):
        retime(ctx, "update-claude", 8, "01:30")
    assert timer.read_bytes() == before
    record = load_state(ctx.state_path).state.records["update-claude"]
    assert (record.interval, record.start) == (6, "00:00")
    assert all(receipts.matches(a, rehash=True) for a in record.files)


def test_retime_during_a_run_spares_the_service(env: Env) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    service = ctx.unit_dir / f"{CLAUDE_BASENAME}.service"
    service_before = service.read_bytes()
    held = runlock.try_acquire(ctx.lock_path, "update-claude")
    assert held is not None
    env.run.calls.clear()
    try:
        retime(ctx, "update-claude", 8, "01:30")
        assert runlock.holder(ctx.lock_path) is not None  # the lock is untouched
    finally:
        held.release()
    assert service.read_bytes() == service_before
    assert f"restart {CLAUDE_BASENAME}.timer" in env.run.text()
    assert not any(f"{CLAUDE_BASENAME}.service" in line for line in env.run.text())


def test_retime_tmp_cleanup(env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(
        DaemonScheduleError,
        match=re.escape("Cannot edit tmp cleanup: on Linux it runs every 10 min, a fixed cadence."),
    ):
        retime(env.ctx, "tmp-cleanup", 24, "04:30")

    mac = make_env(tmp_path / "mac", monkeypatch, os_key="macos")
    turn_on(mac.ctx, "tmp-cleanup")
    assert retime(mac.ctx, "tmp-cleanup", 24, "03:00").changed is False
    assert retime(mac.ctx, "tmp-cleanup", 6, "04:30").changed is True  # the interval stays 24
    plist_path = mac.home / "Library/LaunchAgents/com.tools-installer.prune-tmpdir.plist"
    assert plistlib.loads(plist_path.read_bytes())["StartCalendarInterval"] == [
        {"Hour": 4, "Minute": 30}
    ]
    record = load_state(mac.ctx.state_path).state.records["tmp-cleanup"]
    assert (record.interval, record.start) == (24, "04:30")


class Install:
    """A scratch cursor-agent install: a fake launcher plus the `agent` and `cursor-agent` links."""

    def __init__(self, home: Path, *, foreign: bool = False) -> None:
        bin_dir = home / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        self.launcher = home / ".local/share/cursor-agent/versions/v1/cursor-agent"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("#!/bin/sh\n")
        self.launcher.chmod(0o755)
        self.agent = bin_dir / "agent"
        self.link = bin_dir / "cursor-agent"
        self.agent.symlink_to(self.launcher)
        if foreign:
            self.link.write_text("#!/bin/sh\necho mine\n")
        else:
            self.link.symlink_to(self.launcher)


def test_cursor_row_writes_and_restores_the_shim(env: Env) -> None:
    install = Install(env.home)
    report = turn_on(env.ctx, "update-cursor-agent")
    assert report.shim == ShimReport("written", "listed", "gpt-5.6-sol-xhigh")
    assert env.models.calls == [install.agent]
    assert not install.link.is_symlink()
    assert is_our_shim(install.link)
    assert load_state(env.ctx.state_path).state.cursor_shim == "listed"

    turn_off(env.ctx, "update-cursor-agent")
    assert install.link.is_symlink()
    assert os.readlink(install.link) == os.readlink(install.agent)
    assert load_state(env.ctx.state_path).state.cursor_shim is None


def test_cursor_row_keeps_a_foreign_cursor_agent(env: Env) -> None:
    install = Install(env.home, foreign=True)
    report = turn_on(env.ctx, "update-cursor-agent")
    assert report.shim is not None
    assert report.shim.write == "kept-foreign"
    assert report.warnings == (
        "your own ~/.local/bin/cursor-agent is kept: it has no installer sentinel.",
    )
    state = load_state(env.ctx.state_path).state
    assert state.records["update-cursor-agent"].decided is True  # the timer is still on
    assert state.cursor_shim == "kept-foreign"
    assert install.link.read_text() == "#!/bin/sh\necho mine\n"


def test_cursor_row_with_a_dangling_agent_warns_and_stays_on(env: Env) -> None:
    install = Install(env.home)
    install.launcher.unlink()
    report = turn_on(env.ctx, "update-cursor-agent")
    assert report.shim is None
    assert [w.split(":")[0] for w in report.warnings] == ["Could not write the cursor-agent shim"]
    assert load_state(env.ctx.state_path).state.records["update-cursor-agent"].decided is True


def test_set_cursor_model(env: Env) -> None:
    install = Install(env.home)
    with pytest.raises(DaemonScheduleError, match=re.escape(MODEL_SHAPE_MESSAGE)):
        set_cursor_model(env.ctx, "--model")
    with pytest.raises(DaemonScheduleError, match=re.escape(MODEL_CHARSET_MESSAGE)):
        set_cursor_model(env.ctx, "a b")
    assert not env.ctx.state_path.exists()

    off = set_cursor_model(env.ctx, "gpt-5.5")  # the row is off: only the model is saved
    assert off.shim is None
    state = load_state(env.ctx.state_path).state
    assert (state.cursor_default_model, state.cursor_shim) == ("gpt-5.5", None)
    assert install.link.is_symlink()

    turn_on(env.ctx, "update-cursor-agent")
    assert "--model 'gpt-5.5'" in install.link.read_text()
    env.models.answer = ("gpt-5.5",)
    missing = set_cursor_model(env.ctx, "gpt-9-unlisted")
    assert missing.shim is not None
    assert missing.shim.check == "not-listed"
    assert "--model '" not in install.link.read_text()  # the pass-through shim injects nothing
    assert load_state(env.ctx.state_path).state.cursor_shim == "not-listed"

    env.models.answer = None
    set_cursor_model(env.ctx, "gpt-5.5")
    assert load_state(env.ctx.state_path).state.cursor_shim == "unverified"
    assert "--model 'gpt-5.5'" in install.link.read_text()


def test_set_cursor_model_spawns_nothing_for_an_off_row(env: Env) -> None:
    set_cursor_model(env.ctx, "gpt-5.5")
    assert env.models.calls == []
    assert load_state(env.ctx.state_path).state.cursor_default_model == "gpt-5.5"


def test_model_list_read_outside_the_state_lock(env: Env) -> None:
    Install(env.home)
    lock_path = state_lock_path(env.ctx.state_path)
    free: list[bool] = []

    def assert_state_lock_is_free() -> None:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises when it is held
            free.append(True)
        finally:
            os.close(descriptor)

    env.models.on_call = assert_state_lock_is_free
    turn_on(env.ctx, "update-cursor-agent")
    set_cursor_model(env.ctx, "gpt-5.5")
    assert free == [True, True]


def test_shared_assets_are_refcounted(env: Env) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    turn_on(ctx, "update-opencode")
    turn_off(ctx, "update-claude")
    assert all((ctx.data_dir / name).is_file() for name in SHARED_NAMES)
    assert (ctx.unit_dir / "tools-installer-schedule-update-opencode.timer").is_file()
    assert len(load_state(ctx.state_path).state.shared) == len(SHARED_NAMES)
    turn_off(ctx, "update-opencode")
    assert not ctx.data_dir.exists()
    assert load_state(ctx.state_path).state.shared == ()


def test_shared_assets_fail_atomically(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = env.ctx
    foreign = ctx.data_dir / "prune-tmp-linux.sh"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("mine\n")
    with pytest.raises(OSError, match="prune-tmp-linux.sh"):
        turn_on(ctx, "update-claude")
    assert tree(ctx.data_dir) == {"prune-tmp-linux.sh": b"mine\n"}
    assert env.run.calls == []

    foreign.unlink()
    real = vars(schedules)["atomic_write_bytes"]
    writes: list[Path] = []

    def failing_third(path: Path, data: bytes, *, mode: int | None = None) -> None:
        if len(writes) == 2:
            raise OSError("disk full")
        writes.append(path)
        real(path, data, mode=mode)

    monkeypatch.setattr(schedules, "atomic_write_bytes", failing_third)
    with pytest.raises(OSError, match="disk full"):
        turn_on(ctx, "update-claude")
    assert len(writes) == 2
    assert files_left(ctx.data_dir) == []  # the two already written are gone
    assert env.run.calls == []


def test_shared_asset_ownership(env: Env) -> None:
    ctx = env.ctx
    runner = ctx.data_dir / "runner.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("# someone else's runner\n")
    with pytest.raises(OSError, match="runner.py"):
        turn_on(ctx, "update-claude")
    assert runner.read_text() == "# someone else's runner\n"
    assert not (ctx.unit_dir / f"{CLAUDE_BASENAME}.service").exists()

    runner.write_bytes((CHECKOUT / "installer/helper_assets/schedule_runner.py").read_bytes())
    turn_on(ctx, "update-claude")  # identical bytes are adopted
    assert runner in {Path(a.path) for a in load_state(ctx.state_path).state.shared}

    script = ctx.data_dir / "prune-tmp-linux.sh"
    script.write_text("#!/bin/sh\n# edited after it was recorded\n")
    with pytest.raises(OSError, match="prune-tmp-linux.sh"):
        turn_on(ctx, "update-opencode")
    assert script.read_text() == "#!/bin/sh\n# edited after it was recorded\n"

    off = turn_off(ctx, "update-claude")  # the last schedule: the edited script is kept
    assert script.is_file()
    assert any("prune-tmp-linux.sh" in warning for warning in off.warnings)
    shared = load_state(ctx.state_path).state.shared
    assert [Path(a.path) for a in shared] == [script]
    assert not runner.exists()


def test_require_available_uses_manager_reachable(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never_reachable(_ctx: ScheduleContext) -> bool:
        return False

    monkeypatch.setattr(schedules, "manager_reachable", never_reachable)
    with pytest.raises(ScheduleUnavailable, match="unavailable: no user timer manager"):
        turn_on(env.ctx, "update-claude")
    assert env.output.calls == []


# --- Task 3: tmp cleanup adopted by name, rollback on every verb, takeover, row states ---

TMP_BASENAME = "tools-installer-prune-tmp"
COMPETING_TIMER, COMPETING_SERVICE = systemd_daemon.COMPETING_UNITS


def seed_legacy_tmp(env: Env, *, marker: bool = True) -> dict[Path, bytes]:
    """Today's tmp cleanup: old wrapper-driven units, wants link, wrapper and decided marker."""
    ctx = env.ctx
    wrapper = daemon.install_wrapper(ctx.legacy_bin_dir)
    service = systemd_daemon.render_service(
        uv_path=env.uv,
        wrapper_path=wrapper,
        script_path=CHECKOUT / "scripts" / "prune-tmp-linux.sh",
        log_path=ctx.home / ".local/state/prune.log",
        tmpdir=ctx.tmpdir,
        home=str(ctx.home),
        path_value="/usr/bin",
    )
    service_path, timer_path = systemd_daemon.write_unit_pair(
        ctx.unit_dir,
        basename=TMP_BASENAME,
        service_text=service,
        timer_text=systemd_daemon.render_timer(),
    )
    link = systemd_daemon.wants_link_path(ctx.unit_dir, basename=TMP_BASENAME)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(timer_path)
    if marker:
        systemd_daemon.record_decided(ctx.myshellrc_path)
    return {service_path: service_path.read_bytes(), timer_path: timer_path.read_bytes()}


def test_tmp_cleanup_is_adopted_in_place(env: Env) -> None:
    ctx = env.ctx
    old = seed_legacy_tmp(env)
    tmp = schedule_by_id("tmp-cleanup")
    before = load_state(ctx.state_path).state
    assert row_state(ctx, before, tmp, manager=True, present=None) == RowState("on")

    report = turn_on(ctx, "tmp-cleanup")

    assert env.run.text() == [
        "daemon-reload",
        f"enable {TMP_BASENAME}.timer",
        f"restart {TMP_BASENAME}.timer",
    ]
    service_path, timer_path = systemd_daemon.unit_paths(ctx.unit_dir, basename=TMP_BASENAME)
    argv = [
        str(env.uv),
        "run",
        "--no-project",
        "--script",
        str(ctx.data_dir / "runner.py"),
        "tmp-cleanup",
        "--script",
        str(ctx.data_dir / "prune-tmp-linux.sh"),
        "--log",
        str(ctx.log_path),
        "--lock",
        str(ctx.lock_path),
        "--cap-bytes",
        "262144",
        "--",
        "--apply",
        "--minutes",
        "10",
    ]
    assert (
        "ExecStart=" + " ".join(f'"{token}"' for token in argv)
        in service_path.read_text().splitlines()
    )
    assert service_path.read_bytes() != old[service_path]
    timer_lines = timer_path.read_text().splitlines()
    assert "OnBootSec=2min" in timer_lines
    assert "OnUnitActiveSec=10min" in timer_lines
    assert not any(line.startswith(("OnCalendar", "Persistent")) for line in timer_lines)
    assert sorted(path.name for path in ctx.unit_dir.iterdir()) == [
        "timers.target.wants",
        f"{TMP_BASENAME}.service",
        f"{TMP_BASENAME}.timer",
    ]
    assert not (ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).exists()
    assert systemd_daemon.decided(ctx.myshellrc_path)
    assert report.next_run is None  # a fixed monotonic cadence has no calendar slot
    record = load_state(ctx.state_path).state.records["tmp-cleanup"]
    assert record.decided is True
    assert {Path(a.path) for a in record.files} == {
        service_path,
        timer_path,
        systemd_daemon.wants_link_path(ctx.unit_dir, basename=TMP_BASENAME),
    }


def test_failed_adoption_keeps_the_old_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, fail_on=frozenset({("restart", 1)}))
    old = seed_legacy_tmp(env)
    with pytest.raises(CommandError):
        turn_on(env.ctx, "tmp-cleanup")
    assert {path: path.read_bytes() for path in old} == old
    assert (env.ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).is_file()
    assert systemd_daemon.decided(env.ctx.myshellrc_path)
    assert load_state(env.ctx.state_path).state.records == {}
    assert not env.ctx.data_dir.exists()


@pytest.mark.parametrize("adopted", [True, False])
def test_tmp_off_records_the_decision(env: Env, adopted: bool) -> None:
    ctx = env.ctx
    seed_legacy_tmp(env, marker=adopted)
    if adopted:
        turn_on(ctx, "tmp-cleanup")
    turn_off(ctx, "tmp-cleanup")
    service_path, timer_path = systemd_daemon.unit_paths(ctx.unit_dir, basename=TMP_BASENAME)
    assert not service_path.exists()
    assert not timer_path.exists()
    assert not systemd_daemon.wants_link_path(ctx.unit_dir, basename=TMP_BASENAME).is_symlink()
    assert not (ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).exists()
    assert systemd_daemon.decided(ctx.myshellrc_path)  # kept, so the reconcile never re-enables it
    tmp = schedule_by_id("tmp-cleanup")
    assert row_state(ctx, load_state(ctx.state_path).state, tmp, manager=True, present=None) == (
        RowState("off")
    )


class CompetingOutput(Output):
    def __init__(self) -> None:
        super().__init__()
        listing = f"{COMPETING_TIMER}        enabled        -\n"
        self.user_listing = listing
        self.system_listing = listing

    def __call__(self, cmd: list[str]) -> str:
        if "list-unit-files" in cmd:
            self.calls.append(cmd)
            return self.user_listing if "--user" in cmd else self.system_listing
        return super().__call__(cmd)


def test_competing_takeover_runs_after_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch)
    ctx = replace(env.ctx, read_output=CompetingOutput())
    report = turn_on(ctx, "tmp-cleanup")
    verbs = env.run.text()
    assert verbs.index(f"restart {TMP_BASENAME}.timer") < verbs.index(
        f"disable --now {COMPETING_TIMER}"
    )
    system = systemd_daemon.CompetingUnit(COMPETING_TIMER, "system", "enabled")
    assert report.warnings == (
        systemd_daemon.takeover_disclosure([COMPETING_TIMER]),
        systemd_daemon.system_scope_warning([system]),
    )
    assert load_state(ctx.state_path).state.records["tmp-cleanup"].decided is True


def test_competing_takeover_failure_never_undoes_the_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, fail_on=frozenset({("disable", 1)}))
    ctx = replace(env.ctx, read_output=CompetingOutput())
    report = turn_on(ctx, "tmp-cleanup")
    assert systemd_daemon.user_scope_failure_warning([COMPETING_TIMER]) in report.warnings
    record = load_state(ctx.state_path).state.records["tmp-cleanup"]
    assert record.decided is True
    assert all(receipts.matches(a, rehash=True) for a in record.files)


def unit_paths_on_disk(ctx: ScheduleContext) -> set[Path]:
    basename = CLAUDE_BASENAME
    service, timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=basename)
    link = systemd_daemon.wants_link_path(ctx.unit_dir, basename=basename)
    return {p for p in (service, timer, link) if p.exists() or p.is_symlink()}


EMPTY_RECORD = ScheduleRecord(None, 6, "00:00", ())
ROLLBACK_CASES: list[tuple[str, frozenset[tuple[str, int]], bool]] = [
    # (action, failing verbs, whether the verb ends in an error; clean and reload are best effort)
    ("on", frozenset({("daemon-reload", 1)}), True),
    ("on", frozenset({("enable", 1)}), True),
    ("on", frozenset({("restart", 1)}), True),
    ("on", frozenset({("restart", 1), ("disable", 1)}), True),
    ("on", frozenset({("enable", 1), ("daemon-reload", 2)}), True),
    ("retime", frozenset({("clean", 1)}), False),
    ("retime", frozenset({("daemon-reload", 1)}), True),
    ("retime", frozenset({("enable", 1)}), True),
    ("retime", frozenset({("restart", 1)}), True),
    ("retime", frozenset({("restart", 1), ("daemon-reload", 2)}), True),
    ("off", frozenset({("disable", 1)}), True),
    ("off", frozenset({("clean", 1)}), False),
    ("off", frozenset({("daemon-reload", 1)}), False),
]


@pytest.mark.parametrize(("action", "fail_on", "raises"), ROLLBACK_CASES)
def test_rollback_on_every_verb(
    action: str,
    fail_on: frozenset[tuple[str, int]],
    raises: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = make_env(tmp_path, monkeypatch)
    ctx = env.ctx
    if action != "on":
        turn_on(ctx, "update-claude")
    env.run.arm(fail_on)  # counted from here on, after the setup's own verbs
    outcomes: list[BaseException | None] = []
    try:
        if action == "on":
            turn_on(ctx, "update-claude")
        elif action == "retime":
            retime(ctx, "update-claude", 8, "01:30")
        else:
            turn_off(ctx, "update-claude")
        outcomes.append(None)
    except (CommandError, OSError) as exc:
        outcomes.append(exc)
    assert (outcomes[0] is not None) is raises
    files = load_state(ctx.state_path).state.records.get("update-claude", EMPTY_RECORD).files
    # the state never names a file that is not on disk, and names every file that is
    assert {Path(a.path) for a in files} == unit_paths_on_disk(ctx)
    assert all(receipts.matches(a, rehash=True) for a in files)
    if action == "on" and outcomes[0] is not None:
        # no unit and no shared asset survives a failed first apply
        assert files_left(env.home) == []


def no_process_ctx(ctx: ScheduleContext) -> ScheduleContext:
    """A context whose every process seam fails the test when called."""

    def boom(cmd: list[str]) -> None:
        raise AssertionError(f"row_state started a process: {cmd}")

    def boom_output(cmd: list[str]) -> str:
        raise AssertionError(f"row_state started a process: {cmd}")

    def boom_models(agent: Path) -> tuple[str, ...] | None:
        raise AssertionError(f"row_state read the model list: {agent}")

    def boom_which(name: str) -> str | None:
        raise AssertionError(f"row_state resolved a program: {name}")

    return replace(
        ctx, run=boom, read_output=boom_output, read_models=boom_models, which=boom_which
    )


def test_row_state_matrix(env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = no_process_ctx(env.ctx)
    claude = schedule_by_id("update-claude")
    cache = schedule_by_id("cache-cleanup")
    tmp = schedule_by_id("tmp-cleanup")
    empty = load_state(ctx.state_path).state

    for schedule in SCHEDULES:  # the manager probe or the tool state is still pending
        assert row_state(ctx, empty, schedule, manager=None, present=None) == RowState("unknown")
        assert row_state(ctx, empty, schedule, manager=False, present=None) == RowState(
            "n/a", "unavailable: no user timer manager"
        )
    assert row_state(ctx, empty, claude, manager=True, present=None) == RowState("unknown")
    assert row_state(ctx, empty, claude, manager=True, present=lambda _tool: False) == RowState(
        "n/a", "unavailable: claude not installed"
    )
    assert row_state(ctx, empty, claude, manager=True, present=lambda _tool: True) == RowState(
        "off"
    )
    # cache cleanup has no target, so a missing tool never makes it n/a
    assert row_state(ctx, empty, cache, manager=True, present=lambda _tool: False) == RowState(
        "off"
    )
    assert row_state(ctx, empty, tmp, manager=True, present=None) == RowState("off")

    turn_on(env.ctx, "update-claude")
    state = load_state(ctx.state_path).state
    assert row_state(ctx, state, claude, manager=True, present=lambda _tool: True) == RowState("on")
    timer = ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"
    original = timer.read_bytes()
    timer.write_bytes(original + b"# edited by hand\n")
    assert row_state(ctx, state, claude, manager=True, present=lambda _tool: True) == RowState(
        "drift"
    )
    timer.write_bytes(original)
    service = ctx.unit_dir / f"{CLAUDE_BASENAME}.service"
    service.unlink()
    assert row_state(ctx, state, claude, manager=True, present=lambda _tool: True) == RowState(
        "drift"
    )

    # tmp cleanup reads on from its units by name, on macOS from its plist
    seed_legacy_tmp(env)
    assert row_state(ctx, state, tmp, manager=True, present=None) == RowState("on")
    mac = make_env(tmp_path / "mac", monkeypatch, os_key="macos")
    assert row_state(no_process_ctx(mac.ctx), empty, tmp, manager=True, present=None) == RowState(
        "off"
    )
    plist = mac.ctx.launch_agents_dir / "com.tools-installer.prune-tmpdir.plist"
    plist.parent.mkdir(parents=True)
    plist.write_bytes(b"<plist/>")
    assert row_state(no_process_ctx(mac.ctx), empty, tmp, manager=True, present=None) == RowState(
        "on"
    )


def test_toggle_during_a_run_leaves_the_run_alone(env: Env) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    held = runlock.try_acquire(ctx.lock_path, "update-claude")
    assert held is not None
    content = ctx.lock_path.read_bytes()
    try:
        turn_off(ctx, "update-claude")
        assert ctx.lock_path.read_bytes() == content
        holder = runlock.holder(ctx.lock_path)
        assert holder is not None
        assert holder.job == "update-claude"
        assert runlock.try_acquire(ctx.lock_path, "probe") is None  # still held
    finally:
        held.release()
    assert files_left(env.home) == [".local/state/tools-installer/run.lock"]  # only the run lock


ESCALATION = re.compile(r"\b(sudo|pkexec|doas)\b")


def test_new_modules_name_no_privilege_escalation() -> None:
    package = Path(schedules.__file__).parent
    names = ["schedules.py", "runlock.py", "cursor_shim.py", "helper_assets/schedule_runner.py"]
    if (package / "schedule_run.py").exists():
        names.append("schedule_run.py")
    for name in names:
        assert ESCALATION.search((package / name).read_text()) is None, name
