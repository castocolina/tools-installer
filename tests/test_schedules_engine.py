"""The Schedules engine: turning a schedule on and off against recording systemctl fakes.

Every systemctl call goes to a recording runner; `which`, `present` and `read_models` are fakes
and every file lands under `tmp_path`. Private names are read through `vars(schedules)`.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from installer import receipts
from installer.run import CommandError
from installer.schedules import (
    ScheduleContext,
    ScheduleUnavailable,
    basename_for,
    clean_unit_path,
    context_for,
    label_for,
    load_state,
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
        self._seen: dict[str, int] = {}

    def verb(self, cmd: list[str]) -> str:
        return cmd[2] if cmd[0] == "systemctl" else cmd[1]

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        verb = self.verb(cmd)
        self._seen[verb] = self._seen.get(verb, 0) + 1
        if verb in self.hooks:
            self.hooks[verb](cmd)
        if (verb, self._seen[verb]) in self.fail_on:
            raise CommandError(cmd, 5)
        if cmd[0] != "systemctl" or not cmd[-1].endswith(".timer"):
            return
        link = self.unit_dir / "timers.target.wants" / cmd[-1]
        if verb == "enable":
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
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(exist_ok=True)
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
