"""Self-check decisions over a fully fake Git runner."""

import os
import re
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from installer import schedules, update_check
from installer.helper_assets import schedule_runner
from installer.run import CommandError
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    encode_manager_snapshot,
    save_version_cache,
)
from installer.version_status import Health, ToolState
from tests.state_doubles import absent_state, empty_inventory, empty_outdated
from tests.update_check_doubles import (
    SHA_B,
    FakeGit,
    FakeNotifier,
    FakeRefresher,
    check_context,
    current_state,
    outdated_state,
    stale_current_state,
    stale_outdated_state,
    tool_named,
    unknown_state,
)


def test_the_git_runner_is_isolated_bounded_and_credential_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    for key in ("GIT_ASKPASS", "SSH_ASKPASS", "GIT_DIR"):
        monkeypatch.setenv(key, "/unsafe")
    assert update_check.git_for_check(["git", "-C", "/w", "rev-parse", "HEAD"]) == "ok"
    assert seen["cmd"] == [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.autocrlf=false",
        "-c",
        "credential.helper=",
        "-c",
        "core.askPass=",
        "-C",
        "/w",
        "rev-parse",
        "HEAD",
    ]
    assert seen["timeout"] == 20
    assert seen["start_new_session"] is False
    assert seen["stdin"] is subprocess.DEVNULL
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes"
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_ASKPASS"] == ""
    assert "SSH_ASKPASS" not in env and "GIT_DIR" not in env


@pytest.mark.parametrize(
    "raw",
    [
        b"{not json",
        b"\xff\xfe",
        b'{"version":2,"notified":[]}',
        b'{"version":true,"notified":[]}',
        b'{"version":1.0,"notified":[]}',
        b"[]",
        b'{"version":1,"notified":"a"}',
        b'{"version":1,"notified":[1]}',
        b'{"version":1,"notified":["Bad Id"]}',
        b'{"version":1,"notified":["../x"]}',
        b'{"version":1,"notified":[""]}',
        b"x" * (65536 + 1),
    ],
)
def test_read_notified_is_strict(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "notified"
    assert update_check.read_notified(path) == (frozenset(), True)
    path.write_bytes(b'{"version": 1, "notified": ["a", "b"]}')
    assert update_check.read_notified(path) == (frozenset({"a", "b"}), True)
    path.write_bytes(raw)
    assert update_check.read_notified(path) == (frozenset(), False)
    path.unlink()
    target = tmp_path / "target"
    target.write_bytes(b"keep")
    path.symlink_to(target)
    assert update_check.read_notified(path) == (frozenset(), False)
    path.unlink()
    path.mkdir()
    assert update_check.read_notified(path) == (frozenset(), False)
    assert path.is_dir()


def test_write_notified_text_mode_and_link_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "planted-secret-a")
    monkeypatch.setenv("GH_TOKEN", "planted-secret-b")
    path = tmp_path / "parent" / "notified"
    update_check.write_notified(path, {"b", "a"})
    data = path.read_bytes()
    assert data == b'{"version": 1, "notified": ["a", "b"]}\n'
    assert path.stat().st_mode & 0o777 == 0o600
    assert all(
        s not in data
        for s in (b"GITHUB_TOKEN", b"GH_TOKEN", b"planted-secret-a", b"planted-secret-b")
    )
    path.unlink()
    target = tmp_path / "target"
    target.write_bytes(b"unchanged")
    path.symlink_to(target)
    update_check.write_notified(path, {"a"})
    assert not path.is_symlink() and path.is_file()
    assert target.read_bytes() == b"unchanged"
    path.unlink()
    path.mkdir()
    (path / "keep").write_bytes(b"keep")
    with pytest.raises(OSError):
        update_check.write_notified(path, {"a"})
    assert (path / "keep").read_bytes() == b"keep"


def test_fresh_ids_reads_the_stamp_of_the_right_source(tmp_path: Path) -> None:
    now = datetime(2026, 11, 22, tzinfo=UTC)
    older = (now - timedelta(seconds=1)).isoformat()
    stamps = {
        "equal": now.isoformat(),
        "old": older,
        "missing": None,
        "naive": "2026-11-22T00:00:00",
        "invalid": "oops",
        "stale": now.isoformat(),
    }
    names = [*stamps, "brew", "cask", "pnpm", "uv"]
    tools = [tool_named(name) for name in names]
    states = {t.id: outdated_state(t) for t in tools}
    states["stale"] = stale_outdated_state(tool_named("stale"))
    for name in ("brew", "cask", "pnpm", "uv"):
        state = states[name]
        assert state.version is not None
        states[name] = replace(state, version=replace(state.version, source=name))
    entries = {name: VersionCacheEntry("2", stamp) for name, stamp in stamps.items()}
    entries.update({name: VersionCacheEntry("2", older) for name in ("brew", "cask", "pnpm", "uv")})
    path = tmp_path / "cache"
    snapshot = ManagerSnapshot(empty_inventory(), empty_outdated(), now.isoformat())
    save_version_cache(path, entries, managers=encode_manager_snapshot(snapshot))
    assert update_check.fresh_ids(tools, states.get, path, started=now, now=now) == frozenset(
        {"equal", "brew", "cask", "pnpm", "uv"}
    )
    entries.update(
        {name: VersionCacheEntry("2", now.isoformat()) for name in ("brew", "cask", "pnpm", "uv")}
    )
    save_version_cache(
        path, entries, managers=encode_manager_snapshot(replace(snapshot, checked_at=older))
    )
    assert update_check.fresh_ids(tools, states.get, path, started=now, now=now) == frozenset(
        {"equal"}
    )
    path.unlink()
    assert not update_check.fresh_ids(tools, states.get, path, started=now, now=now)
    path.write_bytes(b"\xff\xfe")
    assert not update_check.fresh_ids(tools, states.get, path, started=now, now=now)
    path.unlink()
    os.mkfifo(path)
    assert not update_check.fresh_ids(tools, states.get, path, started=now, now=now)


def test_next_set_confirmed_changes_move_membership() -> None:
    tools = [tool_named(c) for c in "abcdef"]
    states = {
        "a": outdated_state(tools[0]),
        "b": current_state(tools[1]),
        "c": absent_state(tools[2]),
        "d": outdated_state(tools[3]),
    }
    prior = frozenset({"a", "b", "c"})
    fresh = frozenset("abcdef")
    assert update_check.next_set(tools, states.get, (True, None), prior, fresh) == frozenset(
        {"a", "d", "tools-installer"}
    )
    assert update_check.next_set(
        tools, states.get, (False, None), prior | {"tools-installer"}, fresh
    ) == frozenset({"a", "d"})


def test_next_set_unknown_keeps_prior_membership() -> None:
    tools = [tool_named(c) for c in "abcdefghij"]
    states: dict[str, ToolState | None] = {
        "a": None,
        "b": replace(outdated_state(tools[1]), health=Health.CHECKING),
        "c": unknown_state(tools[2]),
        "d": stale_current_state(tools[3]),
        "e": stale_outdated_state(tools[4]),
        "f": outdated_state(tools[5]),
        "g": current_state(tools[6]),
        "h": replace(current_state(tools[7]), version=None),
        "i": absent_state(tools[8]),
        "j": current_state(tools[9]),
    }
    prior = frozenset("abcdefghij") | {"tools-installer", "outside"}
    fresh = frozenset("abcdehij")
    assert update_check.next_set(
        tools, states.get, (False, "origin query failed"), prior, fresh
    ) == frozenset("abcdefgh") | {"tools-installer"}
    assert (
        update_check.next_set(tools, states.get, (False, "origin query failed"), frozenset(), fresh)
        == frozenset()
    )
    assert (
        update_check.next_set([tools[8]], states.get, (False, None), frozenset({"i"}), frozenset())
        == frozenset()
    )


def test_the_message_names_ids_only_and_is_bounded() -> None:
    message = vars(update_check)["_message"]
    summary, body = message({"one"})
    assert (summary, body) == ("1 tool update available", "one")
    summary, body = message({f"t{i:02d}" for i in range(12)})
    assert summary == "12 tool updates available"
    assert body == "t00, t01, t02, t03, t04, t05, t06, t07, and 4 more"
    assert summary[0].isdigit() and body[0].isalnum()
    assert all(c not in summary + body for c in "<>&\n\"'")


def test_failed_reason_text() -> None:
    assert update_check.failed_reason(CommandError(["x"], 1, detail="boom")) == "boom"
    assert update_check.failed_reason(OSError("disk full")) == "disk full"
    assert update_check.failed_reason(ValueError()) == "ValueError"


def test_the_result_line_fits_the_runner_cap_whatever_the_reasons() -> None:
    labels = ["lookups failed", "installer skipped", "notify skipped", "not saved"]
    line = update_check.result_line(2, [(label, "x" * 500) for label in labels])
    assert len(line) <= update_check.RESULT_LIMIT
    assert [line.index(label) for label in labels] == sorted(line.index(label) for label in labels)
    assert len(update_check.result_line(2, [("problem", "x" * 1000)])) <= update_check.RESULT_LIMIT
    assert update_check.result_line(2, []) == "ok: 2 updates available"
    line = update_check.result_line(2, [("problem", " a\t b  c \x1b[31m\x07\x9b31m\x85")])
    assert "a b c" in line
    assert not re.search(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", line)
    assert line == vars(schedule_runner)["_sanitize"](line)
    assert vars(schedule_runner)["_MAX_REASON"] == update_check.RESULT_LIMIT


BRANCH = ("rev-parse", "--abbrev-ref", "HEAD")
HEAD = ("rev-parse", "HEAD")
REMOTE = ("ls-remote", "origin", "refs/heads/main")
OBJECT = ("cat-file", "-e", SHA_B)
ANCESTOR = ("merge-base", "--is-ancestor", SHA_B, "HEAD")


TOPLEVEL = ("rev-parse", "--show-toplevel")
CONFIG = ("config", "--get-regexp", r"^(extensions\.partialclone|remote\..*\.promisor)$")


def test_the_hardened_self_check_issues_only_read_only_subcommands(tmp_path: Path) -> None:
    (tmp_path / "file").write_bytes(b"content")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    for behind, expected in (
        (True, ["rev-parse", "rev-parse", "rev-parse", "ls-remote", "config", "cat-file"]),
        (False, ["rev-parse", "rev-parse", "rev-parse", "ls-remote"]),
    ):
        git = FakeGit(behind=behind)
        assert update_check.installer_behind(tmp_path, git) == (behind, None)
        commands = [call[3] for call in git.calls]
        assert commands == expected
        assert set(commands) <= {"rev-parse", "ls-remote", "cat-file", "merge-base", "config"}
        assert not set(commands) & {"fetch", "pull", "checkout", "merge", "reset", "clone"}
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


def test_a_checkout_that_is_not_its_own_worktree_root_is_skipped(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git = FakeGit(toplevel=tmp_path)
    assert update_check.installer_behind(checkout, git) == (False, "not the checkout root")
    assert [tuple(call[3:]) for call in git.calls] == [BRANCH, TOPLEVEL]
    link = tmp_path / "link"
    link.symlink_to(checkout, target_is_directory=True)
    assert update_check.installer_behind(checkout, FakeGit(toplevel=link)) == (True, None)
    git = FakeGit()
    git.answers[TOPLEVEL] = CommandError(list(TOPLEVEL), 128)
    assert update_check.installer_behind(checkout, git) == (False, "not a git checkout")


def test_a_partial_clone_skips_the_object_queries(tmp_path: Path) -> None:
    git = FakeGit(partial=True)
    assert update_check.installer_behind(tmp_path, git) == (False, "partial clone")
    assert all(call[3] not in {"cat-file", "merge-base"} for call in git.calls)
    equal = FakeGit(partial=True, behind=False)
    assert update_check.installer_behind(tmp_path, equal) == (False, None)
    assert all(call[3] != "config" for call in equal.calls)
    for code, reason in ((128, "git query failed"), (124, "git query timed out")):
        failing = FakeGit()
        failing.answers[CONFIG] = CommandError(list(CONFIG), code)
        assert update_check.installer_behind(tmp_path, failing) == (False, reason)


def test_the_skip_reasons_are_the_nine_fixed_strings(tmp_path: Path) -> None:
    assert {
        "not a git checkout",
        "git not found",
        "git query timed out",
        "git query failed",
        "origin query failed",
        "origin has no main branch",
        "origin returned an unexpected answer",
        "not the checkout root",
        "partial clone",
    } == update_check.SKIP_REASONS
    url = "https://user:ghp_planted_value@example.test/r.git"
    for query in (TOPLEVEL, CONFIG):
        git = FakeGit()
        git.answers[query] = CommandError([url], 128, detail=url)
        behind, reason = update_check.installer_behind(tmp_path, git)
        assert not behind and reason in update_check.SKIP_REASONS
        assert reason is not None
        assert all(secret not in reason for secret in ("ghp_planted_value", "user:", "https://"))


def test_a_checkout_behind_main_reports_behind(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_bytes(b"config")
    (tmp_path / "file").write_bytes(b"content")
    before = {
        p.relative_to(tmp_path): sha256(p.read_bytes()).digest()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    git = FakeGit()
    assert update_check.installer_behind(tmp_path, git) == (True, None)
    assert all(call[:3] == ["git", "-C", str(tmp_path)] for call in git.calls)
    commands = [call[3] for call in git.calls]
    assert commands[0] == "rev-parse"
    assert commands.index("ls-remote") < commands.index("cat-file")
    assert git.calls[-1][-3:] == ["cat-file", "-e", SHA_B]
    assert set(commands) <= {"rev-parse", "ls-remote", "cat-file", "merge-base", "config"}
    after = {
        p.relative_to(tmp_path): sha256(p.read_bytes()).digest()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert after == before


def test_an_ancestor_remote_is_not_behind(tmp_path: Path) -> None:
    equal = FakeGit(behind=False)
    assert update_check.installer_behind(tmp_path, equal) == (False, None)
    assert all(call[3] != "cat-file" for call in equal.calls)
    git = FakeGit()
    git.answers[OBJECT] = ""
    assert update_check.installer_behind(tmp_path, git) == (False, None)
    git.answers[ANCESTOR] = CommandError(list(ANCESTOR), 1)
    assert update_check.installer_behind(tmp_path, git) == (True, None)
    git.answers[ANCESTOR] = CommandError(list(ANCESTOR), 128, detail="failure")
    assert update_check.installer_behind(tmp_path, git) == (False, "git query failed")


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1, (True, None)),
        (128, (False, "git query failed")),
        (124, (False, "git query timed out")),
        (127, (False, "git not found")),
    ],
)
def test_only_exit_code_one_means_a_missing_object(
    tmp_path: Path, code: int, expected: tuple[bool, str | None]
) -> None:
    git = FakeGit()
    git.answers[OBJECT] = CommandError(list(OBJECT), code, detail="failure")
    assert update_check.installer_behind(tmp_path, git) == expected
    assert all(call[3] != "merge-base" for call in git.calls)


@pytest.mark.parametrize("branch", ["HEAD", "feature/x"])
def test_a_branch_other_than_main_or_a_detached_head_is_a_silent_skip(
    tmp_path: Path, branch: str
) -> None:
    git = FakeGit(branch=branch)
    assert update_check.installer_behind(tmp_path, git) == (False, None)
    assert len(git.calls) == 1


@pytest.mark.parametrize(
    ("query", "code", "reason"),
    [
        (BRANCH, 128, "not a git checkout"),
        (BRANCH, 127, "git not found"),
        (BRANCH, 124, "git query timed out"),
        (HEAD, 128, "git query failed"),
        (REMOTE, 128, "origin query failed"),
        (REMOTE, 124, "git query timed out"),
    ],
)
def test_failures_map_to_the_fixed_categories(
    tmp_path: Path, query: tuple[str, ...], code: int, reason: str
) -> None:
    git = FakeGit()
    git.answers[query] = CommandError(list(query), code)
    assert update_check.installer_behind(tmp_path, git) == (False, reason)
    assert reason in update_check.SKIP_REASONS


@pytest.mark.parametrize("query", [BRANCH, HEAD, REMOTE, OBJECT, ANCESTOR])
def test_a_credential_bearing_remote_never_reaches_a_reason(
    tmp_path: Path, query: tuple[str, ...]
) -> None:
    git = FakeGit()
    git.answers[OBJECT] = ""
    url = "https://user:ghp_planted_value@example.test/r.git"
    git.answers[query] = CommandError(
        [url], 128, detail=f"fatal: unable to access '{url}/': Could not resolve host\nmore"
    )
    behind, reason = update_check.installer_behind(tmp_path, git)
    assert not behind
    assert reason in update_check.SKIP_REASONS
    assert reason is not None
    assert all(secret not in reason for secret in ("ghp_planted_value", "user:", "https://"))


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ("", "origin has no main branch"),
        (f"{SHA_B}\trefs/heads/dev/refs/heads/main\n", "origin has no main branch"),
        ("--upload-pack=x\trefs/heads/main\n", "origin returned an unexpected answer"),
        (f"{'b' * 39}\trefs/heads/main\n", "origin returned an unexpected answer"),
        (f"{'B' + 'b' * 39}\trefs/heads/main\n", "origin returned an unexpected answer"),
    ],
)
def test_a_missing_main_ref_and_a_malformed_answer_give_reasons(
    tmp_path: Path, answer: str, reason: str
) -> None:
    git = FakeGit()
    git.answers[REMOTE] = answer
    assert update_check.installer_behind(tmp_path, git) == (False, reason)
    assert all(call[3] not in {"cat-file", "merge-base"} for call in git.calls)


def test_sha256_remote_is_accepted(tmp_path: Path) -> None:
    git = FakeGit()
    sha = "b" * 64
    git.answers[REMOTE] = f"{sha}\trefs/heads/main\n"
    git.answers[("cat-file", "-e", sha)] = CommandError([], 1)
    assert update_check.installer_behind(tmp_path, git) == (True, None)
    assert git.calls[-1][3:] == ["cat-file", "-e", sha]


def test_tools_are_refreshed_oldest_attempt_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 11, 22, tzinfo=UTC)
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "abcdef"]
    entries = {
        "a": VersionCacheEntry("2", (now - timedelta(hours=1)).isoformat()),
        "b": VersionCacheEntry("2", (now - timedelta(days=2)).isoformat()),
        "d": VersionCacheEntry("2", "invalid"),
        "e": VersionCacheEntry("2", "2026-11-01T00:00:00"),
        "f": VersionCacheEntry("2", (now + timedelta(days=10)).isoformat()),
    }

    def check_order(
        names: list[str], cache: dict[str, VersionCacheEntry], expected: list[str]
    ) -> None:
        selected = [tool_named(name) for name in names]
        refresh = FakeRefresher(tmp_path / "cache", {}, seed_cache=cache, clock=lambda: now)
        line, code = update_check.run_check(
            selected,
            refresh=refresh,
            notify=FakeNotifier(),
            context=ctx,
            git=FakeGit(branch="feature"),
            clock=lambda: now,
        )
        assert code == 0 and line.startswith("ok:")
        assert [tool.id for tool in refresh.calls[0][0]] == expected

    check_order([t.id for t in tools], entries, list("cdefba"))
    entries["c"] = VersionCacheEntry(
        "2", (now - timedelta(days=10)).isoformat(), (now - timedelta(days=1)).isoformat()
    )
    check_order(list("abc"), entries, list("bca"))
    names = [f"tool-{i:02d}" for i in range(25)]
    failures = {
        name: VersionCacheEntry(
            "2", (now - timedelta(days=10)).isoformat(), (now - timedelta(hours=7)).isoformat()
        )
        for name in names[:20]
    }
    check_order(names, failures, names[20:] + names[:20])
    check_order(list("cba"), {}, list("cba"))


def test_an_invalid_utf8_version_cache_before_the_refresh_does_not_crash_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "cba"]
    refresh = FakeRefresher(tmp_path / "cache", {}, seed_cache=b"\xff\xfe{")
    line, code = update_check.run_check(
        tools, refresh=refresh, notify=FakeNotifier(), context=ctx, git=FakeGit(branch="feature")
    )
    assert code == 0 and line.startswith("ok:")
    assert refresh.calls[0][0] == tuple(tools)


def test_the_result_line_counts_outdated_tools_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "abc"]
    states = {t.id: outdated_state(t) if t.id != "c" else current_state(t) for t in tools}
    refresh = FakeRefresher(tmp_path / "cache", states)
    notify = FakeNotifier()
    assert update_check.run_check(
        tools, refresh=refresh, notify=notify, context=ctx, git=FakeGit(branch="feature")
    ) == ("ok: 2 updates available", 0)
    assert len(refresh.calls) == 1
    called, stale, sink = refresh.calls[0]
    assert called == tuple(tools) and stale == timedelta(hours=20) == update_check.CHECK_STALE_AFTER
    assert sink is not None and len(notify.calls) == 1
    schedules.notified_path(ctx).unlink()
    refresh.states = {t.id: current_state(t) for t in tools}
    notify.calls.clear()
    assert update_check.run_check(
        tools, refresh=refresh, notify=notify, context=ctx, git=FakeGit(branch="feature")
    ) == ("ok: 0 updates available", 0)
    assert not notify.calls and not schedules.notified_path(ctx).exists()


def test_the_set_rules_over_several_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "abc"]

    def clock() -> datetime:
        return datetime(2026, 11, 22, tzinfo=UTC)

    refresh = FakeRefresher(
        tmp_path / "cache",
        {t.id: outdated_state(t) for t in tools[:2]} | {"c": current_state(tools[2])},
        clock=clock,
    )
    notify = FakeNotifier()

    def run() -> tuple[str, int]:
        return update_check.run_check(
            tools,
            refresh=refresh,
            notify=notify,
            context=ctx,
            git=FakeGit(branch="feature"),
            clock=clock,
        )

    assert run() == ("ok: 2 updates available", 0)
    path = schedules.notified_path(ctx)
    original = path.read_bytes()
    assert run() == ("ok: 2 updates available", 0) and path.read_bytes() == original
    tools.reverse()
    assert run() == ("ok: 2 updates available", 0) and len(notify.calls) == 1
    refresh.states["c"] = outdated_state(tool_named("c"))
    assert run() == ("ok: 3 updates available", 0)
    assert run() == ("ok: 3 updates available", 0) and len(notify.calls) == 2
    refresh.states["b"] = current_state(tool_named("b"))
    refresh.states["c"] = current_state(tool_named("c"))
    assert run() == ("ok: 1 updates available", 0) and notify.calls[-1][1] == "a"
    refresh.states["a"] = current_state(tool_named("a"))
    count = len(notify.calls)
    assert run() == ("ok: 0 updates available", 0) and len(notify.calls) == count
    assert path.read_bytes() == b'{"version": 1, "notified": []}\n'
    refresh.states["a"] = outdated_state(tool_named("a"))
    assert run() == ("ok: 1 updates available", 0) and len(notify.calls) == count + 1


def test_a_transient_origin_failure_neither_removes_nor_renotifies_the_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tool = tool_named("a")
    refresh = FakeRefresher(tmp_path / "cache", {"a": outdated_state(tool)})
    notify = FakeNotifier()
    git = FakeGit()

    def run() -> tuple[str, int]:
        return update_check.run_check([tool], refresh=refresh, notify=notify, context=ctx, git=git)

    assert run() == ("ok: 2 updates available; installer behind origin/main", 0)
    data = schedules.notified_path(ctx).read_bytes()
    git.answers[REMOTE] = CommandError([], 1)
    assert run() == ("ok: 2 updates available; installer check skipped: origin query failed", 0)
    del git.answers[REMOTE]
    assert run() == ("ok: 2 updates available; installer behind origin/main", 0)
    assert len(notify.calls) == 1 and schedules.notified_path(ctx).read_bytes() == data


def test_stale_or_unstamped_evidence_keeps_a_notified_tool_until_it_is_confirmed_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    a, b = [tool_named(c) for c in "ab"]
    refresh = FakeRefresher(tmp_path / "cache", {"a": outdated_state(a), "b": outdated_state(b)})
    notify = FakeNotifier()

    def run() -> tuple[str, int]:
        return update_check.run_check(
            [a, b], refresh=refresh, notify=notify, context=ctx, git=FakeGit(branch="feature")
        )

    assert run() == ("ok: 2 updates available", 0)
    path = schedules.notified_path(ctx)
    data = path.read_bytes()
    for state in (stale_outdated_state(a), stale_current_state(a), current_state(a)):
        refresh.states["a"] = state
        refresh.stamped = {"b"}
        assert run() == ("ok: 2 updates available", 0)
        assert len(notify.calls) == 1 and path.read_bytes() == data
    path.unlink()
    refresh.states = {"a": stale_outdated_state(a), "b": current_state(b)}
    refresh.stamped = None
    assert run() == ("ok: 0 updates available", 0) and len(notify.calls) == 1


def test_a_real_shrink_is_told_apart_from_stale_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    a, b = [tool_named(c) for c in "ab"]
    refresh = FakeRefresher(tmp_path / "cache", {"a": outdated_state(a), "b": outdated_state(b)})
    notify = FakeNotifier()

    def run() -> tuple[str, int]:
        return update_check.run_check(
            [a, b], refresh=refresh, notify=notify, context=ctx, git=FakeGit(branch="feature")
        )

    assert run() == ("ok: 2 updates available", 0)
    refresh.states["a"] = current_state(a)
    assert run() == ("ok: 1 updates available", 0)
    assert notify.calls[-1][1] == "b" and len(notify.calls) == 2
    assert schedules.notified_path(ctx).read_bytes() == b'{"version": 1, "notified": ["b"]}\n'


@pytest.mark.parametrize("raw", [b"\xff\xfe", b"{not json"])
def test_a_corrupt_or_invalid_utf8_state_file_is_rewritten_and_a_directory_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    path = schedules.notified_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    a = tool_named("a")
    refresh = FakeRefresher(tmp_path / "cache", {"a": outdated_state(a)})
    notify = FakeNotifier()

    def run() -> tuple[str, int]:
        return update_check.run_check(
            [a], refresh=refresh, notify=notify, context=ctx, git=FakeGit(branch="feature")
        )

    assert run() == ("ok: 1 updates available", 0)
    assert path.read_bytes() == b'{"version": 1, "notified": ["a"]}\n' and len(notify.calls) == 1
    path.unlink()
    path.mkdir()
    (path / "keep").write_bytes(b"keep")
    line, code = run()
    assert code == 0 and line.startswith("ok: 1 updates available; notified set not saved: ")
    assert len(notify.calls) == 2 and (path / "keep").read_bytes() == b"keep"
    refresh.corrupt_cache = b"\xff\xfe{"
    assert run()[0].startswith("ok:")


def test_a_failed_notification_does_not_store_the_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "ab"]
    refresh = FakeRefresher(tmp_path / "cache", {t.id: outdated_state(t) for t in tools})
    notify = FakeNotifier("notify-send not found")
    writes: list[Path] = []
    original = update_check.atomic_replace_entry

    def spy(path: Path, data: bytes, *, mode: int) -> None:
        writes.append(path)
        original(path, data, mode=mode)

    monkeypatch.setattr(update_check, "atomic_replace_entry", spy)

    def run() -> tuple[str, int]:
        return update_check.run_check(
            tools, refresh=refresh, notify=notify, context=ctx, git=FakeGit(branch="feature")
        )

    assert run() == ("ok: 2 updates available; notify skipped: notify-send not found", 0)
    assert not writes and not schedules.notified_path(ctx).exists()
    notify.reason = None
    assert run() == ("ok: 2 updates available", 0) and len(notify.calls) == 2 and len(writes) == 1


def test_a_write_failure_is_a_clause_not_a_failed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "ab"]
    refresh = FakeRefresher(tmp_path / "cache", {t.id: outdated_state(t) for t in tools})

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(update_check, "atomic_replace_entry", fail)
    assert update_check.run_check(
        tools, refresh=refresh, notify=FakeNotifier(), context=ctx, git=FakeGit(branch="feature")
    ) == ("ok: 2 updates available; notified set not saved: disk full", 0)


def test_the_installer_clause_is_independent_of_notification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "ab"]
    refresh = FakeRefresher(tmp_path / "cache", {t.id: outdated_state(t) for t in tools})
    notify = FakeNotifier()

    def run(git: FakeGit) -> tuple[str, int]:
        return update_check.run_check(tools, refresh=refresh, notify=notify, context=ctx, git=git)

    assert run(FakeGit()) == ("ok: 3 updates available; installer behind origin/main", 0)
    assert "tools-installer" in notify.calls[-1][1]
    schedules.notified_path(ctx).unlink()
    notify.reason = "boom"
    assert run(FakeGit()) == (
        "ok: 3 updates available; installer behind origin/main; notify skipped: boom",
        0,
    )
    notify.reason = None
    refresh.states = {t.id: current_state(t) for t in tools}
    assert run(FakeGit()) == ("ok: 1 updates available; installer behind origin/main", 0)
    for git in (FakeGit(behind=False), FakeGit(branch="HEAD"), FakeGit(branch="feature")):
        schedules.notified_path(ctx).unlink(missing_ok=True)
        assert run(git) == ("ok: 0 updates available", 0)
    git = FakeGit()
    git.answers[REMOTE] = CommandError([], 1)
    assert run(git) == ("ok: 0 updates available; installer check skipped: origin query failed", 0)


def test_clauses_are_ordered_and_split_where_the_flow_splits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    tools = [tool_named(c) for c in "ab"]
    reason = "failed to resolve tag for owner/a: HTTP Error 403: rate limit exceeded"
    refresh = FakeRefresher(
        tmp_path / "cache",
        {t.id: outdated_state(t) for t in tools},
        failures=[("a", reason + "\x07\nsecret"), ("b", "other")],
    )
    notify = FakeNotifier()

    def run(git: FakeGit) -> tuple[str, int]:
        return update_check.run_check(tools, refresh=refresh, notify=notify, context=ctx, git=git)

    assert run(FakeGit(branch="feature")) == (
        f"ok: 2 updates available; 2 lookups failed: {reason}",
        0,
    )
    schedules.notified_path(ctx).unlink()
    git = FakeGit()
    git.answers[REMOTE] = CommandError([], 1)
    notify.reason = "boom"
    assert run(git) == (
        f"ok: 2 updates available; 2 lookups failed: {reason}"
        "; installer check skipped: origin query failed; notify skipped: boom",
        0,
    )
    notify.reason = None

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(update_check, "atomic_replace_entry", fail)
    assert run(FakeGit()) == (
        f"ok: 3 updates available; 2 lookups failed: {reason}"
        "; installer behind origin/main; notified set not saved: disk full",
        0,
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [(CommandError(["x"], 1, detail="boom"), "boom"), (OSError("disk full"), "disk full")],
)
def test_a_failing_refresh_is_a_failed_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, reason: str
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    refresh = FakeRefresher(tmp_path / "cache", {}, raises=error)
    notify, git = FakeNotifier(), FakeGit()
    assert update_check.run_check([], refresh=refresh, notify=notify, context=ctx, git=git) == (
        f"failed: {reason}",
        1,
    )
    assert not notify.calls and not git.calls and not schedules.notified_path(ctx).exists()
