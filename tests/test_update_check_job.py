"""Hermetic composition through the scheduled runner and a real setup child."""

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from installer import receipts
from installer.helper_assets import schedule_runner
from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.model import Method, Tool
from installer.ownership import ManagerInventory
from installer.platform import Platform
from installer.run import CommandError
from installer.update_check import run_check, write_notified
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    encode_manager_snapshot,
    save_version_cache,
)
from installer.version_status import VersionRefreshService
from installer.versions import VersionError
from tests.update_check_doubles import (
    YQ_SHA,
    FakeGit,
    FakeNotifier,
    check_context,
    place_yq,
    place_yq_with_receipt,
    real_service,
    yq_tool,
)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): (str(p.readlink()).encode() if p.is_symlink() else p.read_bytes())
        for p in root.rglob("*")
        if p.is_file() or p.is_symlink()
    }


def make_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> tuple[Path, Path, Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        receipts, "receipts_dir", lambda: home / ".local/state/tools-installer/receipts"
    )
    if scenario == "adopt":
        place_yq(home)
    else:
        placed = place_yq_with_receipt(home)
        if scenario == "retire":
            placed.unlink()
    cache = home / ".local/state/tools-installer/versions.json"
    stamp = datetime.now(UTC) - timedelta(days=0 if scenario == "adopt" else 1)
    save_version_cache(
        cache,
        {
            "yq": VersionCacheEntry(
                "v5.0.0",
                stamp.isoformat(),
                digests={"yq_linux_amd64": YQ_SHA} if scenario == "adopt" else {},
            )
        },
    )
    if scenario == "link":
        target = tmp_path / "target"
        target.write_bytes(cache.read_bytes())
        cache.unlink()
        cache.symlink_to(target)
    checkout = tmp_path / "co"
    (checkout / ".git").mkdir(parents=True)
    (checkout / "setup.py").write_text("scratch")
    (checkout / "other").write_text("keep")
    (checkout / ".git/config").write_text("keep")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/dummy/bus")
    monkeypatch.setenv("GITHUB_TOKEN", "planted")
    monkeypatch.setenv("GH_TOKEN", "planted")
    notify = bindir / "notify-send"
    notify.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{tmp_path / "notify"}"\n'
        f'printf "%s\\n" "${{DBUS_SESSION_BUS_ADDRESS-unset}}" >> "{tmp_path / "bus"}"\n'
    )
    notify.chmod(0o755)
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "home": str(home),
                "checkout": str(checkout),
                "result": str(tmp_path / "result.json"),
                "traceback": str(tmp_path / "traceback"),
            }
        )
    )
    uv = bindir / "fake-uv"
    root = Path(__file__).resolve().parent.parent
    uv.write_text(
        f"#!{sys.executable}\nimport sys; sys.path.insert(0, {str(root)!r})\n"
        f"from tests.update_check_child import main; raise SystemExit(main({str(config)!r}))\n"
    )
    uv.chmod(0o755)
    return home, checkout, uv, cache


def run_job(tmp_path: Path, checkout: Path, uv: Path) -> tuple[int, list[str]]:
    log = tmp_path / "run/log"
    code = schedule_runner.main(
        [
            "check-updates",
            "--installer",
            str(checkout),
            "--uv",
            str(uv),
            "--log",
            str(log),
            "--lock",
            str(tmp_path / "run/lock"),
            "--cap-bytes",
            "262144",
        ]
    )
    return code, log.read_text().splitlines()


@pytest.mark.parametrize("scenario", ["plain", "adopt", "retire", "link"])
def test_the_hermetic_check_job_changes_only_the_allowed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    home, checkout, uv, cache = make_job(tmp_path, monkeypatch, scenario)
    before, co_before = snapshot(home), snapshot(checkout)
    target_before = (tmp_path / "target").read_bytes() if scenario == "link" else b""
    code, lines = run_job(tmp_path, checkout, uv)
    assert code == 0, (
        lines,
        (tmp_path / "traceback").read_text() if (tmp_path / "traceback").exists() else "",
    )
    count = 1 if scenario in ("plain", "link") else 0
    assert len(lines) == 2
    assert re.fullmatch(r"\S+ check-updates start", lines[0])
    assert re.fullmatch(rf"\S+ check-updates ok: {count} updates available", lines[1])
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["code"] == 0 and result["bytecode"] == "1"
    assert not result["github_token"] and not result["gh_token"] and result["runs"] == []
    assert len(result["git"]) == 4
    assert all(argv[:3] == ["git", "-C", str(checkout.resolve())] for argv in result["git"])
    assert [argv[3:] for argv in result["git"]] == [
        ["rev-parse", "--abbrev-ref", "HEAD"],
        ["rev-parse", "--show-toplevel"],
        ["rev-parse", "HEAD"],
        ["ls-remote", "origin", "refs/heads/main"],
    ]
    if count:
        assert (tmp_path / "notify").read_text().splitlines() == [
            "--app-name=tools-installer",
            "--urgency=normal",
            "--",
            "1 tool update available",
            "yq",
        ]
        assert (tmp_path / "bus").read_text().strip() == "unix:path=/dummy/bus"
    else:
        assert not (tmp_path / "notify").exists()
    after = snapshot(home)
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    allowed = {
        ".local/state/tools-installer/versions.json",
        ".local/state/tools-installer/update-check.json",
        ".local/state/tools-installer/receipts/yq.json",
    }
    assert changed <= allowed
    if scenario in ("plain", "link"):
        assert {
            ".local/state/tools-installer/versions.json",
            ".local/state/tools-installer/update-check.json",
        } <= changed
    if scenario == "adopt":
        assert ".local/state/tools-installer/receipts/yq.json" in changed
        assert not (cache.parent / "update-check.json").exists()
    if scenario == "retire":
        assert ".local/state/tools-installer/receipts/yq.json" in changed
        assert not (cache.parent / "receipts/yq.json").exists()
    assert not (cache.parent / "schedules.json").exists()
    assert snapshot(checkout) == co_before
    if scenario == "link":
        assert not cache.is_symlink() and cache.is_file()
        assert (tmp_path / "target").read_bytes() == target_before


def test_the_job_is_deterministic_on_a_second_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, checkout, uv, cache = make_job(tmp_path, monkeypatch, "plain")
    code, first = run_job(tmp_path, checkout, uv)
    assert code == 0
    first_state = snapshot(home)
    save_version_cache(
        cache,
        {"yq": VersionCacheEntry("v5.0.0", (datetime.now(UTC) - timedelta(days=1)).isoformat())},
    )
    code, lines = run_job(tmp_path, checkout, uv)
    assert (
        code == 0
        and first[-1].split(" check-updates ", 1)[1] == lines[-1].split(" check-updates ", 1)[1]
    )
    second = snapshot(home)
    first_state.pop(".local/state/tools-installer/versions.json")
    second.pop(".local/state/tools-installer/versions.json")
    assert first_state == second
    assert (tmp_path / "bus").read_text().splitlines() == ["unix:path=/dummy/bus"]


@pytest.mark.parametrize("case", ["stale_positive", "failed_manager_query"])
@pytest.mark.parametrize("planted", [False, True])
def test_stale_evidence_never_moves_the_notified_set_through_the_real_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: bool, case: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        receipts, "receipts_dir", lambda: tmp_path / ".local/state/tools-installer/receipts"
    )
    now = datetime.now(UTC)
    cache = tmp_path / ".local/state/tools-installer/versions.json"
    if case == "stale_positive":
        place_yq_with_receipt(tmp_path)
        tool = yq_tool()
        save_version_cache(
            cache, {"yq": VersionCacheEntry("v5.0.0", (now - timedelta(days=1)).isoformat())}
        )

        def failed(_repo: str) -> str:
            raise VersionError("rate limited: HTTP 403")

        service = real_service(tmp_path, resolve_tag=failed, now=lambda: now, installed="v4.0.0")
    else:
        tool = Tool(
            id="rg",
            name="rg",
            category="search",
            cmd="rg",
            methods=(Method(kind="brew", params={"formula": "ripgrep"}),),
        )
        inventory = ManagerInventory(
            brew_formulae={"ripgrep": "14.1.0"},
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=tmp_path / "brew",
        )
        outdated = OutdatedReport(
            brew={"ripgrep": ManagerVersion("14.1.0", "14.1.1")}, cask={}, pnpm={}, uv={}
        )
        old = ManagerSnapshot(inventory, outdated, (now - timedelta(hours=7)).isoformat())
        save_version_cache(cache, {}, managers=encode_manager_snapshot(old))

        def failed_outdated(**_kwargs: object) -> OutdatedReport:
            raise CommandError(["brew", "outdated"], 1)

        def read_inventory(**_kwargs: object) -> ManagerInventory:
            return inventory

        service = VersionRefreshService(
            platform=Platform(os="macos", arch="amd64", immutable=False, has_brew=True),
            cache_path=cache,
            now=lambda: now,
            home=tmp_path,
            managed_bin_dir=tmp_path / "bin",
            which=lambda cmd: str(tmp_path / "brew/bin" / cmd),
            artifacts_for=lambda _tool: [],
            read_inventory_fn=read_inventory,
            read_outdated_fn=failed_outdated,
            pnpm_packages=lambda: (),
            resolve_pnpm=lambda: None,
            bun_versions=lambda: {},
            query=lambda *_args, **_kwargs: "",
            probe_output=lambda _argv: "14.1.0",
        )
    path = cache.parent / "update-check.json"
    if planted:
        write_notified(path, {tool.id})
    before = path.read_bytes() if planted else None
    notifier = FakeNotifier()
    line, code = run_check(
        [tool],
        refresh=service,
        notify=notifier,
        context=check_context(tmp_path, monkeypatch),
        git=FakeGit(branch="feature"),
        clock=lambda: now,
    )
    suffix = "; 1 lookups failed: rate limited: HTTP 403" if case == "stale_positive" else ""
    assert code == 0 and line == f"ok: {int(planted)} updates available{suffix}"
    state = service.state_of(tool.id)
    assert state is not None and state.version is not None and state.version.outdated
    assert state.version.stale == (case == "stale_positive")
    assert notifier.calls == []
    assert (path.read_bytes() if path.exists() else None) == before


def test_the_runner_logs_a_replayed_result_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "co"
    checkout.mkdir()
    (checkout / "setup.py").write_text("scratch")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir))
    uv = bindir / "fake-uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        'print("ok: 2 updates available; notify skipped: osascript exited 1")\n'
    )
    uv.chmod(0o755)
    code, lines = run_job(tmp_path, checkout, uv)
    assert code == 0 and len(lines) == 2
    assert re.fullmatch(r"\S+ check-updates start", lines[0])
    assert re.fullmatch(
        r"\S+ check-updates ok: 2 updates available; notify skipped: osascript exited 1", lines[1]
    )
