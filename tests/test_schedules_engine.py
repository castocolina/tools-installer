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
        "--no-cache",
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
    assert 'Environment="TMPDIR=/tmp"' in lines
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


def test_a_symlink_replacing_a_recorded_unit_is_refused_on_repair(env: Env, tmp_path: Path) -> None:
    turn_on(env.ctx, "update-claude")
    victim = tmp_path / "victim.service"
    victim.write_text("[Service]\nExecStart=/bin/true\n")
    service = env.ctx.unit_dir / f"{CLAUDE_BASENAME}.service"
    service.unlink()
    service.symlink_to(victim)  # a recorded file, replaced by a link
    with pytest.raises(OSError, match=f"{CLAUDE_BASENAME}.service"):
        turn_on(env.ctx, "update-claude")
    assert victim.read_text() == "[Service]\nExecStart=/bin/true\n"


def test_units_carry_the_platform_tmpdir_never_the_callers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = make_env(tmp_path, monkeypatch).ctx

    def context(tmpdir: str) -> ScheduleContext:
        return context_for(
            "fedora",
            checkout=CHECKOUT,
            read_models=base.read_models,
            run=base.run,
            read_output=base.read_output,
            which=base.which,
            present=base.present,
            environ={"TMPDIR": tmpdir},
        )

    ctx = context("/somewhere/else")
    assert ctx.tmpdir == "/tmp"
    turn_on(ctx, "update-claude")
    service = (ctx.unit_dir / f"{CLAUDE_BASENAME}.service").read_text()
    assert 'Environment="TMPDIR=/tmp"' in service.splitlines()
    assert "/somewhere/else" not in service
    # a different TMPDIR in the writing shell does not make the unit read as stale
    again = context("/another/shell")
    stale = vars(schedules)["_is_stale"]
    assert (
        stale(again, load_state(again.state_path).state, schedule_by_id("update-claude")) is False
    )


def test_the_macos_tmpdir_is_the_per_user_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    def per_user(_name: str) -> str:
        return "/var/folders/ab/cd/T/"

    def empty(_name: str) -> str:
        return ""

    monkeypatch.setattr(os, "confstr", per_user, raising=False)
    assert schedules.default_tmpdir("macos") == "/var/folders/ab/cd/T"
    monkeypatch.setattr(os, "confstr", empty, raising=False)
    assert schedules.default_tmpdir("macos") == "/tmp"
    assert schedules.default_tmpdir("fedora") == "/tmp"


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


WRAPPER_SENTINEL: str = vars(daemon)["_WRAPPER_SENTINEL"]


def legacy_wrapper(ctx: ScheduleContext) -> Path:
    """The old wrapper command, as the previous installer wrote it (sentinel included)."""
    wrapper = ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(f"#!/bin/sh\n# {WRAPPER_SENTINEL}\nexit 0\n")
    wrapper.chmod(0o755)
    return wrapper


def seed_legacy_tmp(env: Env, *, marker: bool = True) -> dict[Path, bytes]:
    """Today's tmp cleanup: old wrapper-driven units, wants link, wrapper and decided marker."""
    ctx = env.ctx
    wrapper = legacy_wrapper(ctx)
    script = CHECKOUT / "scripts" / "prune-tmp-linux.sh"
    service = (
        "[Unit]\nDescription=tools-installer tmpdir prune\n\n[Service]\nType=oneshot\n"
        f'ExecStart="{env.uv}" run --script "{wrapper}" "{script}" --apply\n'
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
        "--no-cache",
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


# --- Migrated from the deleted daemon policies: transactional apply, takeover, marker, wrapper ---


def timer_verbs(env: Env) -> list[str]:
    """The systemctl verbs issued so far (argv index 2)."""
    return [cmd[2] for cmd in env.run.calls if cmd[0] == "systemctl"]


def detection_listing(*entries: tuple[str, str]) -> str:
    lines = [f"{name}        {state}        -" for name, state in entries]
    lines.append(f"{len(entries)} unit files listed.")
    return "\n".join(lines) + "\n"


class Detection(Output):
    """The read-only answers with an independent unit listing per scope."""

    def __init__(self, *, user: str = "", system: str = "") -> None:
        super().__init__()
        self.user = user
        self.system = system

    def __call__(self, cmd: list[str]) -> str:
        if "list-unit-files" in cmd:
            self.calls.append(cmd)
            return self.user if "--user" in cmd else self.system
        return super().__call__(cmd)


def with_competitors(env: Env, *, user: str = "", system: str = "") -> ScheduleContext:
    return replace(env.ctx, read_output=Detection(user=user, system=system))


def tmp_marker_fails(
    monkeypatch: pytest.MonkeyPatch, ctx: ScheduleContext, *, first_only: bool
) -> list[int]:
    """Make every replace of the rc file fail (or only the first one); returns the attempts."""
    attempts: list[int] = []
    real = os.replace

    def flaky(src: object, dst: object) -> None:
        if Path(str(dst)) == ctx.myshellrc_path:
            attempts.append(1)
            if not first_only or len(attempts) == 1:
                raise OSError("simulated disk full")
        real(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", flaky)
    return attempts


def test_a_failed_unit_write_runs_no_systemctl_and_keeps_no_asset(env: Env) -> None:
    ctx = env.ctx
    ctx.unit_dir.parent.mkdir(parents=True, exist_ok=True)
    ctx.unit_dir.write_text("not a directory")  # the write half collides with a plain file
    with pytest.raises(OSError):
        turn_on(ctx, "tmp-cleanup")
    assert not {"enable", "restart"} & set(timer_verbs(env))  # registration was never reached
    assert files_left(ctx.data_dir) == []
    assert not systemd_daemon.decided(ctx.myshellrc_path)


def test_a_failed_apply_keeps_the_assets_another_schedule_owns(env: Env) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-opencode")
    before = tree(ctx.data_dir)
    env.run.arm(frozenset({("enable", 1)}))
    with pytest.raises(CommandError):
        turn_on(ctx, "update-claude")
    assert tree(ctx.data_dir) == before  # recorded shared assets survive another row's failure
    assert (ctx.unit_dir / "tools-installer-schedule-update-opencode.timer").is_file()


def test_the_first_apply_rolls_back_in_the_order_disable_then_reload(env: Env) -> None:
    env.run.arm(frozenset({("enable", 1)}))
    with pytest.raises(CommandError):
        turn_on(env.ctx, "update-claude")
    # reload before enable, enable fails, disable undoes any wants link, then the reload that
    # runs AFTER the unit files are gone
    assert timer_verbs(env) == ["daemon-reload", "enable", "disable", "daemon-reload"]


def test_a_first_apply_over_a_half_removed_install_keeps_the_lone_unit_file(env: Env) -> None:
    ctx = env.ctx
    service, timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=CLAUDE_BASENAME)
    service.parent.mkdir(parents=True)
    service.write_bytes(b"hand-edited service\n")
    env.run.arm(frozenset({("enable", 1)}))
    with pytest.raises(CommandError):
        turn_on(ctx, "update-claude")
    assert service.read_bytes() == b"hand-edited service\n"  # not a prior registration: kept
    assert not timer.exists()


def test_a_failed_retime_restores_the_bytes_and_reregisters_after_the_reload(
    env: Env,
) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    service, timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=CLAUDE_BASENAME)
    service_before, timer_before = service.read_bytes(), timer.read_bytes()
    env.run.calls.clear()
    env.run.arm(frozenset({("restart", 1)}))
    with pytest.raises(CommandError):
        retime(ctx, "update-claude", 8, "01:30")
    assert service.read_bytes() == service_before
    assert timer.read_bytes() == timer_before  # not the 8 h attempt
    assert timer_verbs(env) == [
        "clean",
        "daemon-reload",
        "enable",
        "restart",  # fails
        "daemon-reload",  # the compensating reload, BEFORE the re-registration below
        "daemon-reload",  # bootstrap's own pre-enable reload
        "enable",
        "restart",  # the best-effort re-registration of the restored timer
    ]
    assert row_state(
        ctx,
        load_state(ctx.state_path).state,
        schedule_by_id("update-claude"),
        manager=True,
        present=lambda _tool: True,
    ) == RowState("on")  # the restored files still match the record: not left as a false drift


def test_a_failing_compensating_reload_never_masks_the_original_failure(env: Env) -> None:
    env.run.arm(frozenset({("enable", 1), ("daemon-reload", 2)}))
    with pytest.raises(CommandError) as excinfo:
        turn_on(env.ctx, "update-claude")
    assert excinfo.value.cmd[2] == "enable"


def test_a_failing_disable_leaves_the_unit_files_and_reraises(env: Env) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    service, timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=CLAUDE_BASENAME)
    env.run.arm(frozenset({("disable", 1)}))
    with pytest.raises(CommandError):
        turn_off(ctx, "update-claude")
    assert service.exists()
    assert timer.exists()
    assert load_state(ctx.state_path).state.records["update-claude"].decided is True


@pytest.mark.parametrize("victim", ["service", "timer"])
def test_a_failed_unit_unlink_raises_and_keeps_the_record(
    env: Env, monkeypatch: pytest.MonkeyPatch, victim: str
) -> None:
    ctx = env.ctx
    turn_on(ctx, "update-claude")
    service, timer = systemd_daemon.unit_paths(ctx.unit_dir, basename=CLAUDE_BASENAME)
    target = service if victim == "service" else timer
    real = Path.unlink

    def failing(self: Path, missing_ok: bool = False) -> None:
        if self == target:
            raise OSError("simulated unlink failure")
        real(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing)
    with pytest.raises(OSError, match="simulated unlink failure"):
        turn_off(ctx, "update-claude")
    assert target.exists()
    # the unit stays recorded, so a later sweep or toggle still finds it
    assert target in {
        Path(a.path) for a in load_state(ctx.state_path).state.records["update-claude"].files
    }


def test_the_decided_marker_is_linux_only_on_linux(env: Env) -> None:
    turn_on(env.ctx, "tmp-cleanup")
    assert systemd_daemon.decided(env.ctx.myshellrc_path) is True
    assert daemon.decided(env.ctx.myshellrc_path) is False  # the macOS marker is a different key


def test_a_marker_write_failure_on_turn_on_degrades_to_a_warning(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = tmp_marker_fails(monkeypatch, env.ctx, first_only=False)
    report = turn_on(env.ctx, "tmp-cleanup")
    assert any("decision not recorded" in warning for warning in report.warnings)
    assert len(attempts) == 2  # one retry
    service, timer = systemd_daemon.unit_paths(env.ctx.unit_dir, basename=TMP_BASENAME)
    assert service.exists()
    assert timer.exists()
    assert "enable" in timer_verbs(env)
    assert systemd_daemon.decided(env.ctx.myshellrc_path) is False
    assert load_state(env.ctx.state_path).state.records["tmp-cleanup"].decided is True


def test_a_transient_marker_failure_recovers_on_turn_on_and_turn_off(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = tmp_marker_fails(monkeypatch, env.ctx, first_only=True)
    assert turn_on(env.ctx, "tmp-cleanup").warnings == ()
    assert systemd_daemon.decided(env.ctx.myshellrc_path) is True
    assert len(attempts) == 2
    monkeypatch.undo()
    attempts = tmp_marker_fails(monkeypatch, env.ctx, first_only=True)
    assert turn_off(env.ctx, "tmp-cleanup").warnings == ()
    assert systemd_daemon.decided(env.ctx.myshellrc_path) is True  # an explicit off is decided
    assert len(attempts) == 2


def test_a_marker_write_failure_on_turn_off_warns_and_leaves_it_undecided(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = env.ctx
    turn_on(ctx, "tmp-cleanup")
    ctx.myshellrc_path.unlink()  # no decision was ever durably recorded
    tmp_marker_fails(monkeypatch, ctx, first_only=False)
    report = turn_off(ctx, "tmp-cleanup")
    assert any("decision not recorded" in warning for warning in report.warnings)
    assert systemd_daemon.units_present(ctx.unit_dir, basename=TMP_BASENAME) is False
    assert systemd_daemon.decided(ctx.myshellrc_path) is False


def test_a_wrapper_unlink_failure_degrades_to_a_warning_and_the_marker_failure_is_added(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = env.ctx
    turn_on(ctx, "tmp-cleanup")
    wrapper = legacy_wrapper(ctx)
    real = Path.unlink

    def failing(self: Path, missing_ok: bool = False) -> None:
        if self == wrapper:
            raise OSError("simulated wrapper removal failure")
        real(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing)
    report = turn_off(ctx, "tmp-cleanup")
    assert any("wrapper removal failed" in warning for warning in report.warnings)
    assert systemd_daemon.units_present(ctx.unit_dir, basename=TMP_BASENAME) is False
    assert any(cmd[2] == "disable" for cmd in env.run.calls)

    ctx.myshellrc_path.unlink()
    tmp_marker_fails(monkeypatch, ctx, first_only=False)
    both = turn_off(ctx, "tmp-cleanup")
    assert any("wrapper removal failed" in warning for warning in both.warnings)
    assert any("decision not recorded" in warning for warning in both.warnings)


def test_turn_on_removes_a_wrapper_it_did_not_write_only_when_it_is_ours(env: Env) -> None:
    ctx = env.ctx
    foreign = ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND
    foreign.parent.mkdir(parents=True)
    foreign.write_text("#!/bin/sh\necho someone else's command\n")
    turn_on(ctx, "tmp-cleanup")
    assert foreign.read_text() == "#!/bin/sh\necho someone else's command\n"  # no sentinel: kept
    foreign.unlink()
    legacy_wrapper(ctx)
    turn_off(ctx, "tmp-cleanup")
    assert not (ctx.legacy_bin_dir / daemon.WRAPPER_COMMAND).exists()


def test_a_user_scope_competitor_is_disabled_after_registration_and_disclosed(
    env: Env,
) -> None:
    ctx = with_competitors(env, user=detection_listing((COMPETING_TIMER, "enabled")))
    report = turn_on(ctx, "tmp-cleanup")
    assert timer_verbs(env) == ["daemon-reload", "enable", "restart", "disable"]
    assert env.run.calls[-1] == ["systemctl", "--user", "disable", "--now", COMPETING_TIMER]
    [warning] = report.warnings
    assert f"Stopped and disabled {COMPETING_TIMER}" in warning
    assert f"systemctl --user enable --now {COMPETING_TIMER}" in warning
    assert "sudo" not in warning


def no_tool(_tool: str) -> bool:
    return False


def test_the_reconcile_forwards_the_takeover_disclosure(env: Env) -> None:
    ctx = replace(
        with_competitors(env, user=detection_listing((COMPETING_TIMER, "enabled"))),
        present=no_tool,
    )
    report = schedules.ensure_schedule_defaults(ctx)
    assert "tmp-cleanup" in report.turned_on
    assert any(
        COMPETING_TIMER in warning and f"systemctl --user enable --now {COMPETING_TIMER}" in warning
        for warning in report.warnings
    )


def test_a_system_scope_competitor_is_never_disabled_and_is_disclosed(env: Env) -> None:
    ctx = with_competitors(env, system=detection_listing((COMPETING_TIMER, "enabled")))
    report = turn_on(ctx, "tmp-cleanup")
    assert not any(COMPETING_TIMER in cmd for cmd in env.run.calls)
    assert timer_verbs(env) == ["daemon-reload", "enable", "restart"]
    [warning] = report.warnings
    assert f"sudo systemctl disable --now {COMPETING_TIMER}" in warning


def test_with_both_scopes_only_the_user_scope_one_is_disabled(env: Env) -> None:
    ctx = with_competitors(
        env,
        user=detection_listing((COMPETING_TIMER, "enabled")),
        system=detection_listing((COMPETING_SERVICE, "enabled")),
    )
    report = turn_on(ctx, "tmp-cleanup")
    disables = [cmd for cmd in env.run.calls if cmd[2] == "disable"]
    assert disables == [["systemctl", "--user", "disable", "--now", COMPETING_TIMER]]
    text = " ".join(report.warnings)
    assert COMPETING_SERVICE in text
    assert f"sudo systemctl disable --now {COMPETING_SERVICE}" not in text  # not a timer
    assert f"sudo systemctl stop {COMPETING_SERVICE}" in text


def test_a_failed_user_scope_disable_keeps_the_registration_and_names_the_survivor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, fail_on=frozenset({("disable", 1)}))
    ctx = with_competitors(env, user=detection_listing((COMPETING_TIMER, "enabled")))
    report = turn_on(ctx, "tmp-cleanup")  # must not raise: proceed and disclose
    assert systemd_daemon.units_present(ctx.unit_dir, basename=TMP_BASENAME)
    text = " ".join(report.warnings)
    assert COMPETING_TIMER in text
    assert "still running" in text
    assert f"systemctl --user disable --now {COMPETING_TIMER}" in text
    assert "sudo" not in text  # a user-scope competitor never gets a sudo command


def test_a_partial_takeover_of_two_user_scope_units_is_never_reported_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, fail_on=frozenset({("disable", 2)}))
    ctx = with_competitors(
        env,
        user=detection_listing((COMPETING_TIMER, "enabled"), (COMPETING_SERVICE, "enabled")),
    )
    report = turn_on(ctx, "tmp-cleanup")
    disables = [cmd for cmd in env.run.calls if cmd[2] == "disable"]
    assert [cmd[-1] for cmd in disables] == sorted([COMPETING_SERVICE, COMPETING_TIMER])
    text = " ".join(report.warnings)
    assert f"Stopped and disabled {COMPETING_SERVICE}" in text
    assert f"systemctl --user enable --now {COMPETING_SERVICE}" in text
    assert f"{COMPETING_TIMER} could not be stopped and disabled" in text
    assert f"systemctl --user disable --now {COMPETING_TIMER}" in text


def test_the_system_scope_disclosure_survives_an_oserror_from_the_user_scope_disable(
    env: Env,
) -> None:
    def vanishing_bus(cmd: list[str]) -> None:
        if cmd[2] == "disable":
            raise OSError("dbus socket vanished")
        env.run(cmd)

    base = with_competitors(
        env,
        user=detection_listing((COMPETING_TIMER, "enabled")),
        system=detection_listing((COMPETING_SERVICE, "enabled")),
    )
    report = turn_on(replace(base, run=vanishing_bus), "tmp-cleanup")
    text = " ".join(report.warnings)
    assert f"sudo systemctl stop {COMPETING_SERVICE}" in text  # system scope, still disclosed
    assert f"systemctl --user disable --now {COMPETING_TIMER}" in text  # still running


def test_a_failing_detection_probe_behaves_like_no_competitor(env: Env) -> None:
    def raising(cmd: list[str]) -> str:
        if "list-unit-files" in cmd:
            raise CommandError(cmd, 1)
        return env.output(cmd)

    report = turn_on(replace(env.ctx, read_output=raising), "tmp-cleanup")
    assert not any(cmd[2] == "disable" for cmd in env.run.calls)
    assert report.warnings == ()


def test_no_competitor_means_no_warning(env: Env) -> None:
    assert turn_on(env.ctx, "tmp-cleanup").warnings == ()


# macOS: the plist, the bootout-then-bootstrap order and the rollback (the old launchd policy)


def mac_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> Env:
    return make_env(tmp_path, monkeypatch, os_key="macos", **kwargs)  # type: ignore[arg-type]


def mac_plist_path(env: Env) -> Path:
    return env.home / "Library/LaunchAgents/com.tools-installer.prune-tmpdir.plist"


def test_the_macos_tmp_plist_carries_the_schedule_the_environment_and_the_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    ctx = env.ctx
    report = turn_on(ctx, "tmp-cleanup")
    assert report.warnings == ()
    data = plistlib.loads(mac_plist_path(env).read_bytes())
    assert data["StartCalendarInterval"] == [{"Hour": 3, "Minute": 0}]
    argv = data["ProgramArguments"]
    assert str(env.uv) in argv
    assert str(ctx.data_dir / "prune-user-tmpdir.sh") in argv
    assert str(daemon.DEFAULT_DAYS) in argv
    assert data["EnvironmentVariables"]["TMPDIR"] == ctx.tmpdir
    assert data["EnvironmentVariables"]["HOME"] == str(env.home)
    assert data["EnvironmentVariables"]["PATH"] == clean_unit_path(
        env.home, platform_os="macos", environ=ctx.environ
    )
    assert daemon.decided(ctx.myshellrc_path) is True
    assert systemd_daemon.decided(ctx.myshellrc_path) is False
    assert row_state(
        ctx,
        load_state(ctx.state_path).state,
        schedule_by_id("tmp-cleanup"),
        manager=True,
        present=None,
    ) == RowState("on")

    turn_off(ctx, "tmp-cleanup")
    assert not mac_plist_path(env).exists()
    assert daemon.decided(ctx.myshellrc_path) is True  # an explicit off is still decided


def test_a_macos_reapply_keeps_a_time_set_with_retime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")
    retime(env.ctx, "tmp-cleanup", 24, "04:15")
    turn_on(env.ctx, "tmp-cleanup")
    data = plistlib.loads(mac_plist_path(env).read_bytes())
    assert data["StartCalendarInterval"] == [{"Hour": 4, "Minute": 15}]


@pytest.mark.parametrize("platform_os", ["fedora", "macos"])
def test_a_bad_environment_fails_closed_before_any_unit_or_asset_is_written(
    platform_os: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key=platform_os)
    ctx = replace(env.ctx, tmpdir="relative/not/absolute")
    with pytest.raises(DaemonScheduleError):
        turn_on(ctx, "tmp-cleanup")
    assert files_left(env.home) == []
    assert env.run.calls == []
    assert not mac_plist_path(env).exists()


def test_a_macos_first_bootstrap_failure_rolls_back_the_plist_and_the_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch, fail_on=frozenset({("bootstrap", 1)}))
    with pytest.raises(CommandError):
        turn_on(env.ctx, "tmp-cleanup")
    assert not mac_plist_path(env).exists()
    assert not env.ctx.data_dir.exists()
    assert load_state(env.ctx.state_path).state.records == {}
    assert daemon.decided(env.ctx.myshellrc_path) is False
    assert [cmd[1] for cmd in env.run.calls] == ["bootout", "bootstrap"]


def test_a_launchd_log_that_already_existed_survives_a_failed_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch, fail_on=frozenset({("bootstrap", 1)}))
    daemon.ensure_log_path(env.ctx.launchd_log_path)
    with pytest.raises(CommandError):
        turn_on(env.ctx, "tmp-cleanup")
    assert env.ctx.launchd_log_path.exists()


def test_a_macos_plist_write_failure_on_the_first_apply_rolls_back_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)

    def disk_full(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated disk full writing the plist")

    monkeypatch.setattr(daemon, "write_agent_plist", disk_full)
    with pytest.raises(OSError, match="disk full"):
        turn_on(env.ctx, "tmp-cleanup")
    assert not mac_plist_path(env).exists()
    assert not env.ctx.data_dir.exists()
    assert not any(cmd[1] == "bootstrap" for cmd in env.run.calls)
    assert daemon.decided(env.ctx.myshellrc_path) is False


def test_a_macos_plist_write_failure_on_a_reapply_restores_the_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")
    original = mac_plist_path(env).read_bytes()
    env.run.calls.clear()

    def disk_full(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated disk full writing the plist")

    monkeypatch.setattr(daemon, "write_agent_plist", disk_full)
    with pytest.raises(OSError, match="disk full"):
        turn_on(env.ctx, "tmp-cleanup")
    assert mac_plist_path(env).read_bytes() == original
    assert [cmd[1] for cmd in env.run.calls].count("bootstrap") == 1  # the best-effort re-register


def test_a_macos_bootstrap_failure_on_a_reapply_restores_the_bytes_and_reregisters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")
    original = mac_plist_path(env).read_bytes()
    env.run.calls.clear()
    env.run.arm(frozenset({("bootstrap", 1)}))
    with pytest.raises(CommandError):
        turn_on(env.ctx, "tmp-cleanup")
    assert mac_plist_path(env).read_bytes() == original
    assert [cmd[1] for cmd in env.run.calls].count("bootstrap") == 2  # the failed one + re-register


def test_a_macos_retime_bootstrap_failure_rolls_back_and_reregisters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")
    original = mac_plist_path(env).read_bytes()
    env.run.calls.clear()
    env.run.arm(frozenset({("bootstrap", 1)}))
    with pytest.raises(CommandError):
        retime(env.ctx, "tmp-cleanup", 24, "04:15")
    assert mac_plist_path(env).read_bytes() == original
    assert [cmd[1] for cmd in env.run.calls].count("bootstrap") == 2
    record = load_state(env.ctx.state_path).state.records["tmp-cleanup"]
    assert record.start == "03:00"  # the saved time is not changed by a failed re-register


def test_a_macos_bootout_failure_leaves_the_plist_and_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")
    env.run.arm(frozenset({("bootout", 1)}))
    with pytest.raises(CommandError):
        turn_off(env.ctx, "tmp-cleanup")
    assert mac_plist_path(env).exists()
    assert daemon.decided(env.ctx.myshellrc_path) is True  # unchanged from the earlier apply
    assert load_state(env.ctx.state_path).state.records["tmp-cleanup"].decided is True


def test_a_macos_bootout_of_a_job_that_is_not_loaded_completes_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")

    def not_loaded(cmd: list[str]) -> None:
        env.run(cmd)
        if cmd[1] == "bootout":
            raise CommandError(cmd, 3)  # launchctl's idempotent "not loaded" exit

    report = turn_off(replace(env.ctx, run=not_loaded), "tmp-cleanup")
    assert report.warnings == ()
    assert not mac_plist_path(env).exists()


def test_a_macos_plist_unlink_failure_raises_and_keeps_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    turn_on(env.ctx, "tmp-cleanup")
    plist = mac_plist_path(env)
    real = Path.unlink

    def failing(self: Path, missing_ok: bool = False) -> None:
        if self == plist:
            raise OSError("simulated unlink failure")
        real(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing)
    with pytest.raises(OSError, match="simulated unlink failure"):
        turn_off(env.ctx, "tmp-cleanup")
    assert plist.exists()
    assert plist in {
        Path(a.path) for a in load_state(env.ctx.state_path).state.records["tmp-cleanup"].files
    }


def test_a_macos_retime_on_an_off_row_only_saves_and_writes_no_plist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = mac_tmp(tmp_path, monkeypatch)
    report = retime(env.ctx, "tmp-cleanup", 24, "04:15")
    assert report.changed is True
    assert report.next_run is None
    assert env.run.calls == []
    assert not mac_plist_path(env).exists()
    assert load_state(env.ctx.state_path).state.records["tmp-cleanup"].start == "04:15"
