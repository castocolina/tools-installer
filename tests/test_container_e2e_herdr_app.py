"""Host tests for the herdr-app container proof."""

from __future__ import annotations

import hashlib
import re
import shlex
import shutil
import subprocess
import time
import tomllib
import uuid
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from installer.herdr_app_keys import HERDR_APP_DEFAULTS_VERSION
from installer.model import load_tools
from installer.receipts import ReceiptArtifact
from installer.terminal_keys import TERMINAL_KEYS, apply_terminal_keys
from installer.uninstall import SweepResult
from tests import e2e_herdr_app_driver as driver


def test_install_verdict_ok_and_each_problem() -> None:
    assert (
        driver.install_verdict("app-first", "script", 0, "herdr-app 0.1.16", [], [])
        == "TRACER_HERDR_APP_INSTALL_OK order=app-first method=script version=herdr-app 0.1.16"
    )
    line = driver.install_verdict("app-first", "other", 3, "", ["a", "b"], ["c", "d"])
    for part in (
        "method other",
        "exited 3",
        "printed nothing",
        "a is missing",
        "b is missing",
        "the receipt lacks c",
        "the receipt lacks d",
        "; ",
    ):
        assert part in line
    assert "_FAILED" in driver.install_verdict("app-first", "script", 0, "invalid", [], [])


def test_expected_keys_text_matches_the_row_golden(tmp_path: Path) -> None:
    apply_terminal_keys(
        TERMINAL_KEYS["herdr-app"], "herdr-app", "fedora", tmp_path, {}, skip_recorded=False
    )
    text = (tmp_path / ".config/herdr-app/keys.json").read_text()
    assert driver.expected_keys_text("fedora") == text
    assert '"ctrl-shift-k": "send:\\f"' in text
    assert '"ctrl-shift-k": "mod.open:picker"' in text


def test_keys_verdict() -> None:
    v = HERDR_APP_DEFAULTS_VERSION
    assert (
        driver.keys_verdict("app-first", "a", "a", v) == "TRACER_HERDR_APP_KEYS_OK order=app-first"
    )
    assert "keys.json is missing" in driver.keys_verdict("app-first", None, "a", v)
    for text, expected, number in [("a\nb", "a\nc", 2), ("a", "a\nb", 2), ("a\nb", "a", 2)]:
        assert f"line {number}" in driver.keys_verdict("app-first", text, expected, v)
    for other in (None, "9.9.9"):
        name = other or "unknown"
        assert f"_UNPROVEN order=app-first installed={name} pinned={v}" in driver.keys_verdict(
            "app-first", None, "a", other
        )
        assert f"was written although the installed herdr-app is {name}" in driver.keys_verdict(
            "app-first", "a", "a", other
        )


def test_digest_path_covers_files_folders_and_absence(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    assert driver.digest_path(a) == "absent"
    a.mkdir()
    b.mkdir()
    empty = driver.digest_path(a)
    assert empty != "absent" and empty == driver.digest_path(b)
    (a / "x").write_text("abc")
    (b / "x").write_text("abc")
    assert driver.digest_path(a / "x") == hashlib.sha256(b"abc").hexdigest()
    assert driver.digest_path(a) == driver.digest_path(b) != empty
    old = driver.digest_path(a)
    (a / "x").write_text("other")
    assert driver.digest_path(a) != old
    (a / "x").write_text("abc")
    (a / "x").rename(a / "y")
    assert driver.digest_path(a) != old
    (a / "y").rename(a / "x")
    (a / "nested").mkdir()
    assert driver.digest_path(a) != old
    (a / "nested" / "z").touch()
    assert driver.digest_path(a) != old
    paths = [a, b]
    expected = hashlib.sha256(
        "\n".join(sorted(f"{p}\t{driver.digest_path(p)}" for p in paths)).encode()
    ).hexdigest()
    assert driver.digest_paths(paths) == driver.digest_paths(paths[::-1]) == expected
    (b / "x").write_text("changed")
    assert driver.digest_paths(paths) != expected
    (a / "link").symlink_to("missing")
    assert driver.digest_path(a / "link") != "absent"


@pytest.mark.parametrize("point", ["install", "removal"])
def test_isolation_verdict_names_what_changed(point: str) -> None:
    def check(before: tuple[str, str], after: tuple[str, str]) -> str:
        return driver.isolation_verdict("herdr-first", point, before, after)

    assert (
        check(("a", "b"), ("a", "b"))
        == f"TRACER_HERDR_APP_ISOLATION_OK order=herdr-first point={point}"
    )
    line = check(("a", "b"), ("c", "d"))
    assert (
        f"after the app {point}:" in line
        and "the herdr binary changed" in line
        and "~/.config/herdr changed" in line
    )
    assert "the herdr binary changed" in check(("a", "b"), ("c", "b"))
    assert "~/.config/herdr changed" in check(("a", "b"), ("a", "c"))
    for before, name in [
        (("absent", "b"), "the herdr binary"),
        (("a", "absent"), "~/.config/herdr"),
    ]:
        assert f"{name} was absent before the app {point}; there was nothing to preserve" in check(
            before, before
        )
        assert "_UNPROVEN" in check(before, before)


@pytest.mark.parametrize("point", ["install", "removal"])
def test_reverse_verdict_names_what_changed(point: str) -> None:
    def check(before: tuple[str, str, str], after: tuple[str, str, str]) -> str:
        return driver.reverse_verdict("app-first", point, before, after)

    assert (
        check(("a", "b", "absent"), ("a", "b", "absent"))
        == f"TRACER_HERDR_APP_REVERSE_OK order=app-first point={point}"
    )
    for i, name in enumerate(
        ("the herdr-app binary", "the herdr-app paths", "~/.config/herdr-app")
    ):
        after = ["a", "b", "c"]
        after[i] = "changed"
        assert f"{name} changed" in check(("a", "b", "c"), (after[0], after[1], after[2]))
    line = check(("a", "b", "c"), ("x", "y", "z"))
    assert f"after the multiplexer {point}:" in line and all(
        x in line for x in ("binary changed", "paths changed", "~/.config/herdr-app changed")
    )
    for before, name in [(("absent", "b", "c"), "binary"), (("a", "absent", "c"), "paths")]:
        assert (
            f"the herdr-app {name} was absent before the multiplexer {point}; "
            "there was nothing to preserve" in check(before, before)
        )
        assert "_UNPROVEN" in check(before, before)


def test_removal_problem_reads_the_sweep_result() -> None:
    assert driver.removal_problem("herdr-app", SweepResult(removed=("herdr-app",))) is None
    assert driver.removal_problem("herdr-app", SweepResult()) == "herdr-app was not removed"
    for result in (
        SweepResult(removed=("herdr-app",), remove_failed=(("herdr-app", "denied"),)),
        SweepResult(remove_failed=(("herdr-app", "denied"),)),
    ):
        assert "herdr-app removal failed" in str(
            driver.removal_problem("herdr-app", result)
        ) and "denied" in str(driver.removal_problem("herdr-app", result))
    assert (
        driver.removal_problem(
            "herdr-app", SweepResult(removed=("herdr-app",), remove_failed=(("herdr", "denied"),))
        )
        is None
    )


def test_the_seed_gives_the_multiplexer_config_something_to_lose(tmp_path: Path) -> None:
    folder = tmp_path / ".config/herdr"
    folder.mkdir(parents=True)
    empty = driver.digest_path(folder)
    driver.seed_multiplexer_config(tmp_path)
    seed = folder / "config.toml"
    assert seed.read_text() == driver.SEED_TEXT and driver.SEED_TEXT
    assert driver.digest_path(folder) not in ("absent", empty)
    seed.write_text("changed")
    assert driver.digest_path(folder) != empty
    (folder / "other").touch()
    driver.clear_multiplexer_seed(tmp_path)
    assert folder.exists() and not seed.exists()
    (folder / "other").unlink()
    driver.clear_multiplexer_seed(tmp_path)
    assert not folder.exists()


def test_remove_verdict_ok_and_each_problem() -> None:
    def check(
        *,
        installed: list[str] | None = None,
        after: list[str] | None = None,
        receipt_left: bool = False,
        records_left: list[str] | None = None,
        keys_expected: bool = True,
    ) -> str:
        return driver.remove_verdict(
            "herdr-first",
            before=["old"],
            installed=installed
            if installed is not None
            else ["old", "binary", driver.KEYS_RELATIVE],
            after=after if after is not None else ["old"],
            allowed=["allowed"],
            receipt_paths=["binary"],
            receipt_left=receipt_left,
            records_left=records_left or [],
            keys_expected=keys_expected,
        )

    assert (
        check(after=["old", "allowed", *driver.STANDARD_EMPTY_DIRS])
        == "TRACER_HERDR_APP_REMOVE_OK order=herdr-first"
    )
    assert "binary still present" in check(after=["old", "binary"])
    assert "other still present" in check(after=["old", "other"])
    assert "old existed before the install and is gone" in check(after=[])
    assert "binary is missing after the install" in check(installed=["old", driver.KEYS_RELATIVE])
    assert f"{driver.KEYS_RELATIVE} is missing after the install" in check(
        installed=["old", "binary"]
    )
    assert "_OK" in check(installed=["old", "binary"], keys_expected=False)
    assert "the receipt is still present" in check(receipt_left=True)
    assert "record is still present" in check(records_left=["record"])
    assert "and 2 more" in check(after=["old", *(f"x{i:02}" for i in range(12))])


def test_transcript_problem_reads_the_recorded_run() -> None:
    lines = [
        p + ("0.1.16" if p.endswith("herdr-app ") else "")
        for prefixes in driver.EXPECTED_LINES.values()
        for p in prefixes
    ]
    lines.append("TRACER_LANDING_TEARDOWN_OK")
    assert driver.transcript_problem("\n".join(lines)) is None
    assert "the transcript lacks" in str(driver.transcript_problem("\n".join(lines[1:])))
    assert "the transcript lacks" in str(
        driver.transcript_problem(
            "\n".join([driver.EXPECTED_LINES["app-first"][0][:-2], *lines[1:]])
        )
    )
    for bad in ("X_FAILED", "X_UNPROVEN", "TRACER_LANDING_INFEASIBLE"):
        assert f"{bad} is in the transcript" in str(
            driver.transcript_problem("\n".join([bad, *lines]))
        )
    assert driver.transcript_problem("") is not None
    assert driver.transcript_problem("\n".join(lines[:-1])) is not None
    assert driver.transcript_problem("\n".join([*lines, "later"])) is not None


def test_the_transcript_digest_names_the_recorded_run() -> None:
    assert driver.transcript_digest(b"abc") == "ba7816bf8f01"
    assert (
        driver.transcript_digest(b"abc")
        == driver.transcript_digest(b"abc")
        != driver.transcript_digest(b"abd")
    )


def test_purge_paths_name_only_the_known_files() -> None:
    declared = (".local/bin/herdr-app", ".local/share/herdr-app/")
    paths = driver.purge_paths("herdr-app", declared)
    assert set(paths) == {
        *declared,
        ".config/herdr-app/",
        *(
            driver.RECORD_PREFIX + n
            for n in (
                "terminal-tuning-herdr-app",
                "terminal-herdr-app-created",
                "terminal-herdr-app-created-path",
            )
        ),
    }
    assert driver.purge_paths("herdr", declared) == (".local/bin/herdr",)
    assert not any(
        x in paths
        for x in (".local/bin/herdr-core", ".local/bin/hc", ".config/herdr/", ".local/bin/")
    )
    with pytest.raises(ValueError):
        driver.purge_paths("other", declared)


def test_the_target_local_allowlist_allows_exactly_the_nested_core_install() -> None:
    allowed = driver.allowed_prefixes(driver.ALLOWLIST.read_text())
    assert driver.TARGET_ALLOWED == (".local/bin/herdr-core", ".local/bin/hc")
    other = [
        ".local/bin/herdr-core-extra",
        ".local/bin/hc-extra",
        ".local/bin/herdr-core/child",
        ".local/bin/hc/child",
        ".local/bin/other",
        ".local/share/herdr-core/",
    ]
    assert driver.target_leftovers(
        [], [*other, ".local/bin/herdr-core", ".local/bin/hc/", ".cache/x"], allowed
    ) == sorted(other)


def test_paths_share_one_identity_across_declared_receipt_and_listing(tmp_path: Path) -> None:
    declared = driver.declared_app_paths(["~/.local/share/herdr-app/", "~/.local/bin/herdr-app"])
    assert declared == (".local/share/herdr-app/", ".local/bin/herdr-app")
    assert driver.norm_path(declared[0]) == driver.norm_path(declared[0][:-1])
    paths = driver.receipt_relative_paths(
        [
            ReceiptArtifact(tmp_path / ".local/share/herdr-app", "tree"),
            ReceiptArtifact(tmp_path / ".local/bin/herdr-app", "link"),
        ],
        tmp_path,
    )
    assert paths == (".local/bin/herdr-app", ".local/share/herdr-app")
    assert driver.lacking(declared, paths) == []
    assert driver.lacking(declared, paths[:1]) == [declared[0]]
    assert (
        driver.lacking(declared, [*paths, ".local/share/herdr-app/bin/x"], descendants=True) == []
    )
    assert driver.lacking(declared, paths[:1], descendants=True) == [declared[0]]
    assert driver.receipt_relative_paths([ReceiptArtifact(Path("/outside"), "link")], tmp_path) == (
        "/outside",
    )


def test_purge_targets_name_only_new_known_paths() -> None:
    declared = (".local/bin/herdr-app", ".local/share/herdr-app/")
    before = [
        ".config/herdr-app/",
        ".local/bin/herdr-app",
        driver.RECORD_PREFIX + "terminal-tuning-herdr-app",
    ]
    after = [
        *before,
        ".local/share/herdr-app",
        driver.RECORD_PREFIX + "terminal-herdr-app-created",
        ".local/bin/hc",
        "unknown",
    ]
    assert set(driver.purge_targets("herdr-app", declared, before, after)) == {
        ".local/share/herdr-app/",
        driver.RECORD_PREFIX + "terminal-herdr-app-created",
    }


def test_the_shared_allowlist_never_names_the_nested_core_install() -> None:
    assert Path("scripts/e2e-residue-allowlist.txt") == driver.ALLOWLIST
    assert not any(
        p.startswith((".local/bin/herdr-core", ".local/bin/hc"))
        for p in driver.allowed_prefixes(driver.ALLOWLIST.read_text())
    )


def test_the_standard_empty_directories_include_the_nested_icon_folders() -> None:
    assert (
        frozenset(
            {
                ".local/share/applications/",
                ".local/share/icons/",
                ".local/share/icons/hicolor/",
                ".local/share/icons/hicolor/scalable/",
                ".local/share/icons/hicolor/scalable/apps/",
                ".local/share/tools-installer/",
            }
        )
        == driver.STANDARD_EMPTY_DIRS
    )


def test_run_version_does_not_wait_for_a_helper_that_keeps_the_output_open(tmp_path: Path) -> None:
    binary = tmp_path / "binary"
    binary.write_text("#!/bin/sh\n(sleep 30) &\necho herdr-app 9.9.9\n")
    binary.chmod(0o755)
    start = time.monotonic()
    assert driver.run_version(binary, tmp_path)[:2] == (0, "herdr-app 9.9.9")
    assert time.monotonic() - start < 10
    binary.write_text("#!/bin/sh\nexit 3\n")
    assert driver.run_version(binary, tmp_path)[0] == 3
    assert driver.run_version(tmp_path / "missing", tmp_path)[:2] == (-1, "")
    binary.write_text("#!/bin/sh\nsleep 30\n")
    assert driver.run_version(binary, tmp_path, seconds=0.01)[0] == -1


def test_the_verbs_and_the_refusal_outside_the_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(driver, "in_container", lambda: False)
    before = list(tmp_path.iterdir())
    assert driver.accepts(["lifecycle"])
    assert not any(driver.accepts(x) for x in ([], ["other"], ["lifecycle", "x"]))
    assert driver.main(["lifecycle"]) == 2
    assert (
        "ERROR the herdr-app driver runs only inside the disposable container"
        in capsys.readouterr().out
    )
    assert driver.main(["other"]) == 2
    assert "usage: e2e_herdr_app_driver lifecycle" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == before


def test_the_lifecycle_orders_are_pinned() -> None:
    assert driver.ORDERS == ("app-first", "herdr-first")


def test_main_returns_one_when_any_line_is_failed_or_unproven(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(driver, "in_container", lambda: True)
    for line, result in [("X_FAILED", 1), ("X_UNPROVEN", 1), ("X_OK", 0)]:
        monkeypatch.setattr(driver, "_HANDLERS", {"lifecycle": lambda value=line: [value]})
        assert driver.main(["lifecycle"]) == result
        assert capsys.readouterr().out.strip() == line


def test_record_names() -> None:
    for n in (
        "terminal-tuning-herdr-app",
        "terminal-herdr-app-created",
        "terminal-herdr-app-created-path",
    ):
        assert driver.is_state_record(driver.RECORD_PREFIX + n)
    for n in ("terminal-tuning-ghostty", "terminal-tuning-herdr"):
        assert not driver.is_state_record(driver.RECORD_PREFIX + n)


class FakeOps:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.tools: set[str] = set()
        self.files: set[str] = set()
        self.keys = "golden"
        self.fail_remove = False

    def seed(self) -> None:
        self.calls.append("seed")

    def clear(self) -> None:
        self.calls.append("clear_seed")

    def install(self, tool: str) -> None:
        self.calls.append("install:" + tool)
        self.tools.add(tool)
        self.files.add("binary:" + tool)
        if tool == "herdr-app":
            self.files.add(driver.KEYS_RELATIVE)

    def remove(self, tool: str) -> SweepResult:
        self.calls.append("remove:" + tool)
        if self.fail_remove and tool == "herdr-app":
            return SweepResult(remove_failed=((tool, "denied"),))
        self.tools.discard(tool)
        self.files.discard("binary:" + tool)
        if tool == "herdr-app":
            self.files.discard(driver.KEYS_RELATIVE)
        return SweepResult(removed=(tool,))

    def installed(self, tool: str) -> bool:
        return tool in self.tools

    def listing(self) -> list[str]:
        return sorted(self.files)

    def multiplexer(self) -> tuple[str, str]:
        self.calls.append("multiplexer")
        return ("m" if "herdr" in self.tools else "absent", "config")

    def app(self) -> tuple[str, str, str]:
        self.calls.append("app")
        return ("a" if "herdr-app" in self.tools else "absent", "paths", "config")

    def receipt(self) -> tuple[str, tuple[str, ...]] | None:
        return ("script", ("binary:herdr-app",)) if "herdr-app" in self.tools else None

    def ops(self) -> driver.Ops:
        return driver.Ops(
            self.seed,
            self.clear,
            self.install,
            self.remove,
            self.installed,
            self.multiplexer,
            self.app,
            self.listing,
            lambda: (0, "herdr-app 0.1.16"),
            lambda: self.keys,
            self.receipt,
            lambda: (),
            lambda tool, targets: self.calls.append("purge:" + tool),
        )


@pytest.mark.parametrize("order", ["app-first", "herdr-first"])
def test_run_order_sequences_both_orders(order: str) -> None:
    fake = FakeOps()
    driver.run_order(
        order, fake.ops(), expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    events = [
        x
        for x in fake.calls
        if x in ("seed", "clear_seed") or x.startswith(("install:", "remove:"))
    ]
    first = (
        ["install:herdr-app", "install:herdr"]
        if order == "app-first"
        else ["install:herdr", "install:herdr-app"]
    )
    assert events == [
        "seed",
        *first,
        "remove:herdr-app",
        "install:herdr-app",
        "remove:herdr",
        "remove:herdr-app",
        "clear_seed",
    ]


def test_run_order_prints_the_verdicts_of_each_order() -> None:
    for order in driver.ORDERS:
        lines = driver.run_order(
            order,
            FakeOps().ops(),
            expected_keys="golden",
            declared=("binary:herdr-app",),
            allowed=[],
        )
        assert len(lines) == len(driver.EXPECTED_LINES[order])
        assert all(
            line.startswith(prefix)
            for line, prefix in zip(lines, driver.EXPECTED_LINES[order], strict=True)
        )


def test_run_order_applies_the_stop_or_continue_policy() -> None:
    fake = FakeOps()
    fake.keys = "wrong"
    lines = driver.run_order(
        "app-first", fake.ops(), expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    assert any("KEYS_FAILED" in line for line in lines)
    assert any("REVERSE_OK" in line and "point=removal" in line for line in lines)
    assert fake.calls.index("remove:herdr-app") < fake.calls.index("remove:herdr")
    fake = FakeOps()
    fake.fail_remove = True
    lines = driver.run_order(
        "app-first", fake.ops(), expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    assert any("REMOVE_FAILED" in line for line in lines)
    assert fake.calls.count("remove:herdr") == 1
    assert fake.calls.count("install:herdr-app") == 1
    assert not any("point=removal" in line for line in lines)
    assert fake.calls[-1] == "clear_seed"


def test_run_order_names_a_changed_digest_at_the_right_point() -> None:
    fake = FakeOps()
    original = fake.multiplexer
    count = 0

    def changing() -> tuple[str, str]:
        nonlocal count
        count += 1
        a, b = original()
        return ("changed" if count == 2 else a, b)

    from dataclasses import replace

    ops = replace(fake.ops(), multiplexer=changing)
    lines = driver.run_order(
        "herdr-first", ops, expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    assert any(
        "ISOLATION_FAILED" in line and "after the app install" in line and "binary changed" in line
        for line in lines
    )


def test_run_order_cleans_up_before_returning_and_inspects_the_result() -> None:
    from dataclasses import replace

    fake = FakeOps()

    def failing(tool: str) -> None:
        if tool == "herdr-app":
            raise driver.Failed("TRACER_HERDR_APP_INSTALL_FAILED", "boom")
        fake.install(tool)

    lines = driver.run_order(
        "herdr-first",
        replace(fake.ops(), install=failing),
        expected_keys="golden",
        declared=("binary:herdr-app",),
        allowed=[],
    )
    assert any("INSTALL_FAILED" in line and "boom" in line for line in lines)
    assert "remove:herdr" in fake.calls
    assert fake.calls[-1] == "clear_seed"


def test_cleanup_propagates_unexpected_errors_after_clearing_seed() -> None:
    from dataclasses import replace

    fake = FakeOps()

    def broken() -> tuple[str, str]:
        raise KeyError("unexpected")

    with pytest.raises(KeyError):
        driver.run_order(
            "herdr-first",
            replace(fake.ops(), multiplexer=broken),
            expected_keys="golden",
            declared=("binary:herdr-app",),
            allowed=[],
        )
    assert fake.calls[-1] == "clear_seed"
    assert "remove:herdr" in fake.calls


def test_cleanup_reports_failed_and_missing_removals() -> None:
    from dataclasses import replace

    for result, detail in (
        (SweepResult(remove_failed=(("herdr-app", "denied"),)), "denied"),
        (SweepResult(), "was not removed"),
    ):
        fake = FakeOps()

        def remove(tool: str, fake: FakeOps = fake, result: SweepResult = result) -> SweepResult:
            if tool == "herdr-app" and fake.calls.count("remove:herdr-app") > 0:
                return result
            return fake.remove(tool)

        lines = driver.run_order(
            "app-first",
            replace(fake.ops(), remove=remove),
            expected_keys="golden",
            declared=("binary:herdr-app",),
            allowed=[],
        )
        assert any("cleanup" in line and detail in line for line in lines)


def test_version_mismatch_is_unproven_but_later_phases_run() -> None:
    from dataclasses import replace

    fake = FakeOps()
    ops = replace(fake.ops(), version=lambda: (0, "herdr-app 0.1.17"), keys_text=lambda: None)
    lines = driver.run_order(
        "app-first", ops, expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    assert any("KEYS_UNPROVEN" in line and "installed=0.1.17" in line for line in lines)
    assert any("REVERSE_OK" in line and "point=removal" in line for line in lines)
    assert "remove:herdr" in fake.calls


@pytest.mark.parametrize(
    "order,point,kind",
    [
        ("herdr-first", "install", "multiplexer"),
        ("app-first", "install", "app"),
        ("app-first", "removal", "multiplexer"),
        ("herdr-first", "removal", "multiplexer"),
        ("app-first", "removal", "app"),
        ("herdr-first", "removal", "app"),
    ],
)
@pytest.mark.parametrize(
    "index,mode", [(0, "changed"), (1, "changed"), (0, "absent"), (1, "absent")]
)
def test_run_order_digest_matrix(order: str, point: str, kind: str, index: int, mode: str) -> None:
    fake = FakeOps()
    count = 0
    target = (
        3
        if point == "removal"
        and (
            (kind == "multiplexer" and order == "herdr-first")
            or (kind == "app" and order == "app-first")
        )
        else 1
    )

    def alter(values: tuple[str, ...]) -> tuple[str, ...]:
        nonlocal count
        count += 1
        result = list(values)
        if (mode == "absent" and count == target) or (mode == "changed" and count == target + 1):
            result[index] = mode
        return tuple(result)

    def multiplexer() -> tuple[str, str]:
        value = alter(fake.multiplexer())
        return value[0], value[1]

    def app() -> tuple[str, str, str]:
        value = alter(fake.app())
        return value[0], value[1], value[2]

    ops = (
        replace(fake.ops(), multiplexer=multiplexer)
        if kind == "multiplexer"
        else replace(fake.ops(), app=app)
    )
    lines = driver.run_order(
        order, ops, expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    prefix = "ISOLATION" if kind == "multiplexer" else "REVERSE"
    state = "UNPROVEN" if mode == "absent" else "FAILED"
    name = (
        ("the herdr binary", "~/.config/herdr")
        if kind == "multiplexer"
        else ("the herdr-app binary", "the herdr-app paths", "~/.config/herdr-app")
    )[index]
    assert any(
        f"{prefix}_{state}" in line and f"point={point}" in line and name in line for line in lines
    )


def test_the_driver_refuses_outside_the_container(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(driver, "in_container", lambda: False)
    monkeypatch.setattr(driver, "_HANDLERS", {"lifecycle": lambda: pytest.fail("handler ran")})
    assert driver.main(["lifecycle"]) == 2
    assert (
        capsys.readouterr().out.strip()
        == "ERROR the herdr-app driver runs only inside the disposable container"
    )


def test_main_reports_handler_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(driver, "in_container", lambda: True)

    def fail() -> list[str]:
        raise driver.Failed("TRACER_HERDR_APP_INSTALL_FAILED", "boom\nsecond")

    monkeypatch.setattr(driver, "_HANDLERS", {"lifecycle": fail})
    assert driver.main(["lifecycle"]) == 1
    assert "TRACER_HERDR_APP_INSTALL_FAILED" in capsys.readouterr().out

    def error() -> list[str]:
        raise OSError("broken\nsecond")

    monkeypatch.setattr(driver, "_HANDLERS", {"lifecycle": error})
    assert driver.main(["lifecycle"]) == 1
    assert capsys.readouterr().out.strip() == "ERROR broken"


@pytest.mark.parametrize("order", driver.ORDERS)
@pytest.mark.parametrize("attempt", [1, 2, 3])
def test_failed_install_purges_only_new_known_paths(order: str, attempt: int) -> None:
    fake = FakeOps()
    old = {".config/herdr-app/", driver.RECORD_PREFIX + "terminal-tuning-herdr-app"}
    fake.files.update(old)
    purged: dict[str, tuple[str, ...]] = {}
    count = 0
    failed_tool = ""
    new = ""

    def install(tool: str) -> None:
        nonlocal count, failed_tool, new
        count += 1
        if count == attempt:
            failed_tool = tool
            new = ".local/bin/" + tool
            fake.calls.append("install:" + tool)
            fake.files.update((new, ".local/bin/herdr-core", ".local/bin/hc"))
            raise driver.Failed("TRACER_HERDR_APP_INSTALL_FAILED", "boom")
        fake.install(tool)

    def purge(tool: str, targets: tuple[str, ...]) -> None:
        fake.calls.append("purge:" + tool)
        purged[tool] = targets
        fake.files.difference_update(targets)

    lines = driver.run_order(
        order,
        replace(fake.ops(), install=install, purge=purge),
        expected_keys="golden",
        declared=("binary:herdr-app", ".local/bin/herdr-app"),
        allowed=[],
    )
    assert any("INSTALL_FAILED" in line and "boom" in line for line in lines)
    stray = next(line for line in lines if "left files without a receipt" in line)
    assert failed_tool in stray and new in stray
    assert ".local/bin/herdr-core" not in stray and ".local/bin/hc" not in stray
    assert purged[failed_tool] == (new,)
    assert old <= fake.files and new not in fake.files
    assert fake.calls.index("purge:" + failed_tool) < fake.calls.index("clear_seed")
    assert fake.calls.count("remove:" + failed_tool) == (1 if attempt == 3 else 0)


def test_cleanup_exception_is_reported_and_seed_cleared() -> None:
    fake = FakeOps()

    def remove(tool: str) -> SweepResult:
        if tool == "herdr-app" and fake.calls.count("remove:herdr-app"):
            raise OSError("cleanup denied\nsecond")
        return fake.remove(tool)

    lines = driver.run_order(
        "app-first",
        replace(fake.ops(), remove=remove),
        expected_keys="golden",
        declared=("binary:herdr-app",),
        allowed=[],
    )
    assert any(
        "REMOVE_FAILED" in line and "cleanup" in line and "cleanup denied" in line for line in lines
    )
    assert fake.calls[-1] == "clear_seed"


@pytest.mark.parametrize("order", driver.ORDERS)
def test_digest_reads_bracket_each_lifecycle_operation(order: str) -> None:
    fake = FakeOps()
    driver.run_order(
        order, fake.ops(), expected_keys="golden", declared=("binary:herdr-app",), allowed=[]
    )
    calls = fake.calls
    app_removal = calls.index("remove:herdr-app")
    assert calls[app_removal - 1 : app_removal + 2] == [
        "multiplexer",
        "remove:herdr-app",
        "multiplexer",
    ]
    herdr_removal = calls.index("remove:herdr")
    assert calls[herdr_removal - 1 : herdr_removal + 2] == ["app", "remove:herdr", "app"]
    if order == "herdr-first":
        app_install = calls.index("install:herdr-app")
        assert calls[app_install - 1] == "multiplexer"
        assert calls.index("multiplexer", app_install) < app_removal
    else:
        herdr_install = calls.index("install:herdr")
        assert calls[herdr_install - 1 : herdr_install + 2] == ["app", "install:herdr", "app"]
        assert "multiplexer" not in calls[: calls.index("install:herdr-app")]


def test_step_oserror_is_reported_and_cleanup_runs() -> None:
    fake = FakeOps()

    def broken() -> tuple[str, str]:
        raise OSError("digest failed\nsecond")

    lines = driver.run_order(
        "herdr-first",
        replace(fake.ops(), multiplexer=broken),
        expected_keys="golden",
        declared=("binary:herdr-app",),
        allowed=[],
    )
    assert any(
        "INSTALL_FAILED" in line and "digest failed" in line and "second" not in line
        for line in lines
    )
    assert "remove:herdr" in fake.calls and fake.calls[-1] == "clear_seed"


_SCRIPT: Final = Path(__file__).resolve().parent.parent / "scripts/container-e2e-verify.sh"
_CONSTANTS: Final = (
    "IMAGE_FEDORA",
    "IMAGE_DEBIAN",
    "IMAGE_ARCH",
    "LANDING_IMAGE",
    "LANDING_CONTAINER_NAME",
    "LANDING_KEEP_IMAGE",
    "LANDING_PULLED",
    "TESTER_USER",
)
_CT_STUB: Final = 'ct() { printf "ct %s\\n" "$*" >> "$CALLS"; return 0; }\n'
_APP_FUNCTIONS: Final = (
    "die",
    "select_distro",
    "cmd_herdr_app",
    "herdr_app_root_setup",
    "landing_teardown",
    "landing_note_image",
    "start_container",
    "container_exists",
    "container_running",
    "exec_root",
    "exec_tester",
    "ensure_phase_dir",
)


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None
    return found


def _text() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


def _constant(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)\s*$", _text(), re.MULTILINE)
    assert match is not None, name
    return match.group(1)


def _function(name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, name
    return match.group(0)


def _script(*names: str, variables: Mapping[str, str] | None = None, stubs: str = "") -> str:
    parts = ["set -uo pipefail", *(f"{n}={_constant(n)}" for n in _CONSTANTS)]
    parts.extend(_function(n) for n in names)
    parts.extend(f"{k}={shlex.quote(v)}" for k, v in (variables or {}).items())
    return "\n".join([*parts, stubs])


def _run(script: str, scratch: Path) -> subprocess.CompletedProcess[str]:
    scratch.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(scratch),
        "CALLS": str(scratch / "calls"),
        "LANG": "C",
    }
    path = scratch.parent / f"harness-{uuid.uuid4().hex}.sh"
    path.write_text(script, encoding="utf-8")
    try:
        return subprocess.run(
            [_bash(), str(path)], env=env, capture_output=True, text=True, check=False, timeout=30
        )
    finally:
        path.unlink()


def _calls(scratch: Path) -> list[str]:
    path = scratch / "calls"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _app_run(
    scratch: Path, distro: str = "fedora", status: int = 0, option: str = ""
) -> subprocess.CompletedProcess[str]:
    stubs = (
        _CT_STUB
        + f"""\nlanding_bootstrap() {{ start_container replace; exec_root true; }}
landing_stage() {{ shift; "$@"; }}
landing_step() {{ exec_tester true; return {status}; }}
select_distro {distro}
rc=0; cmd_herdr_app {option} || rc=$?; printf 'RC=%s\\n' "$rc"; exit "$rc"
"""
    )
    return _run(
        _script(
            *_APP_FUNCTIONS,
            variables={"REPO_ROOT": str(scratch / "repo"), "TESTER_HOME": "/home/tester"},
            stubs=stubs,
        ),
        scratch,
    )


def test_the_usage_names_every_verdict_the_driver_expects() -> None:
    usage = _function("usage").split("herdr-app [--keep-image]", 1)[1].split("-h, --help", 1)[0]
    for prefixes in driver.EXPECTED_LINES.values():
        for prefix in prefixes:
            assert prefix.split("TRACER_HERDR_APP_", 1)[1].split()[0] in usage
    assert all(x in usage for x in ("exact path", "herdr-core", "hc"))


def test_gate_problem_accepts_one_pass_line_and_names_each_defect() -> None:
    lines = [
        p + ("0.1.16" if p.endswith("herdr-app ") else "")
        for prefixes in driver.EXPECTED_LINES.values()
        for p in prefixes
    ]
    transcript = ("\n".join([*lines, "TRACER_LANDING_TEARDOWN_OK"]) + "\n").encode()
    digest = driver.transcript_digest(transcript)
    line = f"herdr-app-container: PASS (2026-11-21; transcript {digest})"
    summary = f"## Orchestrator verification\n{line}\n## Next\n"
    assert driver.gate_problem(summary, transcript) is None
    assert (
        driver.gate_problem(summary.replace(digest + ")", digest + "; a note)"), transcript) is None
    )
    cases: list[tuple[str | None, bytes | None, str]] = [
        (None, transcript, "summary"),
        (summary, None, "transcript"),
        (line, transcript, "section"),
        ("## Orchestrator verification\n", transcript, "line"),
        (summary.replace(line, line + "\n" + line), transcript, "line"),
        (f"{line}\n## Orchestrator verification\n", transcript, "section"),
        (summary.replace("PASS", "FAIL"), transcript, "malformed"),
        (summary.replace(line, "herdr-app-container: not run"), transcript, "malformed"),
        *[
            (summary.replace(digest + ")", digest + f"; {note})"), transcript, note)
            for note in ("UNPROVEN", "INFEASIBLE")
        ],
        *[
            (summary.replace("2026-11-21", date), transcript, "date")
            for date in ("2026-02-30", "2026-99-99")
        ],
        *[
            (summary.replace(digest, bad), transcript, "malformed")
            for bad in (digest[:11], digest + "0", "a" * 13, digest.upper())
        ],
        (summary.replace(digest, "0" * 12), transcript, "digest"),
        (summary, transcript + b"\n", "digest"),
        (summary, b"X_FAILED\n" + transcript, "FAILED"),
        (summary, ("\n".join(lines[1:] + ["TRACER_LANDING_TEARDOWN_OK"]) + "\n").encode(), "lacks"),
    ]
    for value, data, cause in cases:
        problem = driver.gate_problem(value, data)
        assert problem is not None and cause in problem, (cause, problem)


def test_herdr_app_is_registered() -> None:
    assert re.search(r'^\s*herdr-app\) cmd_herdr_app "\$@" ;;$', _text(), re.MULTILINE)
    usage = _function("usage").split("herdr-app [--keep-image]", 1)[1].split("-h, --help", 1)[0]
    assert all(x in usage for x in ("TRACER_HERDR_APP_", "libxcb", "Needs the network"))
    body = _function("cmd_herdr_app")
    for item in (
        'LANDING_CONTAINER_NAME="tools-installer-e2e-herdr-app-$$"',
        "LANDING_DRIVER_MODULE=tests.e2e_herdr_app_driver",
        'PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-herdr-app"',
        "DISTRO=fedora",
        'IMAGE="$LANDING_IMAGE"',
    ):
        assert item in body
    assert (
        body.index("trap landing_teardown EXIT")
        < body.index("landing_note_image")
        < body.index("landing_bootstrap")
        < body.index("landing_stage herdr-app-root herdr_app_root_setup")
        < body.index("landing_step")
    )


def test_herdr_app_runs_one_lifecycle_step() -> None:
    assert re.findall(
        r"^  landing_step (\S+) (\S+) \|\| failed=1$", _function("cmd_herdr_app"), re.MULTILINE
    ) == [("lifecycle", "lifecycle")]
    assert driver.accepts(["lifecycle"])


def test_herdr_app_root_setup_installs_only_the_two_libraries(tmp_path: Path) -> None:
    result = _run(
        _script(
            "herdr_app_root_setup",
            "exec_root",
            variables={"CONTAINER_NAME": "test-container"},
            stubs=_CT_STUB + "herdr_app_root_setup\n",
        ),
        tmp_path,
    )
    assert result.returncode == 0
    assert _calls(tmp_path) == ["ct exec test-container dnf install -y libxcb libxkbcommon"]


@pytest.mark.parametrize("distro", ["fedora", "debian", "arch"])
def test_herdr_app_start_is_never_privileged_and_targets_only_its_own_container(
    tmp_path: Path, distro: str
) -> None:
    result = _app_run(tmp_path, distro)
    assert result.returncode == 0, result.stderr
    calls = [c for c in _calls(tmp_path) if c.startswith(("ct run ", "ct exec ", "ct rm "))]
    names: set[str] = set()
    for call in calls:
        match = re.search(r"tools-installer-e2e-herdr-app-\d+", call)
        assert match and not re.search(r"tools-installer-e2e-(fedora|debian|arch)\b", call)
        names.add(match.group())
        assert not any(x in call for x in ("--privileged", "--cap-add", "--device"))
    assert len(names) == 1
    assert any(
        re.search(r"ct run .*--name tools-installer-e2e-herdr-app-\d+ fedora:latest", c)
        for c in calls
    )


@pytest.mark.parametrize("pulled", ["1", "0"])
def test_herdr_app_teardown_removes_only_its_container_and_a_pulled_image(
    tmp_path: Path, pulled: str
) -> None:
    result = _run(
        _script(
            "landing_teardown",
            variables={
                "LANDING_CONTAINER_NAME": "tools-installer-e2e-herdr-app-4242",
                "LANDING_PULLED": pulled,
            },
            stubs=_CT_STUB + "landing_teardown\n",
        ),
        tmp_path,
    )
    assert result.returncode == 0
    calls = _calls(tmp_path)
    assert [c for c in calls if c.startswith("ct rm ")] == [
        "ct rm -f tools-installer-e2e-herdr-app-4242"
    ]
    assert [c for c in calls if c.startswith("ct rmi ")] == (
        ["ct rmi fedora:latest"] if pulled == "1" else []
    )


@pytest.mark.parametrize("status", [0, 1])
def test_a_failing_lifecycle_step_returns_one_and_the_teardown_still_runs(
    tmp_path: Path, status: int
) -> None:
    result = _app_run(tmp_path, status=status)
    assert result.returncode == status and f"RC={status}" in result.stdout
    assert any(
        re.fullmatch(r"ct rm -f tools-installer-e2e-herdr-app-\d+", c) for c in _calls(tmp_path)
    )


def test_an_unknown_herdr_app_option_dies(tmp_path: Path) -> None:
    result = _app_run(tmp_path, option="--bogus")
    assert result.returncode != 0 and "unknown herdr-app option: --bogus" in result.stderr


def test_the_harness_never_prunes_or_resets_for_herdr_app() -> None:
    assert not re.search(
        r"system prune|system reset|image prune|volume prune|container prune|builder prune", _text()
    )
    block = _text().split("# --- herdr-app target", 1)[1].split("\n}\n", 2)[1]
    assert "rm -rf" not in block and "sudo" not in block


def test_the_herdr_app_target_comment_names_the_shared_image() -> None:
    block = _text().split("# --- herdr-app target", 1)[1].split("cmd_herdr_app()", 1)[0]
    assert all(
        x in block for x in ("fedora:latest", "cmd_ghostty", "cmd_herdr_keys", "cmd_bun_lifecycle")
    )
    assert not re.search(r"line\s+\d+", block)


_REGISTRY: Final = _SCRIPT.parent.parent / "installer/registry.toml"


def _awk_program() -> str:
    match = re.search(r"^GENERIC_SKIP_AWK='\n(.*?)^'\s*$", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None
    return match.group(1)


def _blocks(text: str) -> tuple[str, dict[str, str]]:
    lines = text.splitlines(keepends=True)
    starts: list[int] = []
    markers: list[int] = []
    for i, line in enumerate(lines):
        if line == "[[tool]]\n":
            start = i
            while start and lines[start - 1].startswith("#"):
                start -= 1
            starts.append(start)
            markers.append(i)
    blocks: dict[str, str] = {}
    for j, marker in enumerate(markers):
        match = re.fullmatch(r'id = "([^"]+)"\n', lines[marker + 1])
        assert match is not None
        blocks[match.group(1)] = "".join(
            lines[starts[j] : starts[j + 1] if j + 1 < len(starts) else len(lines)]
        )
    return "".join(lines[: starts[0]]), blocks


def _filter_registry(tmp_path: Path, skip: str) -> str:
    program = tmp_path / "filter.awk"
    program.write_text(_awk_program(), encoding="utf-8")
    result = _run(
        f"awk -v {shlex.quote('skip=' + skip)} -f {shlex.quote(str(program))} "
        f"{shlex.quote(str(_REGISTRY))}\n",
        tmp_path / "home",
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_the_generic_skip_awk_drops_exactly_the_named_entry_and_its_own_comment(
    tmp_path: Path,
) -> None:
    original = _REGISTRY.read_text(encoding="utf-8")
    filtered = _filter_registry(tmp_path, "herdr-app")
    preamble, blocks = _blocks(original)
    new_preamble, new_blocks = _blocks(filtered)
    ids = [tool.id for tool in load_tools(_REGISTRY)]
    result_path = tmp_path / "registry.toml"
    result_path.write_text(filtered, encoding="utf-8")
    assert [tool.id for tool in load_tools(result_path)] == [i for i in ids if i != "herdr-app"]
    assert [row["id"] for row in tomllib.loads(filtered)["tool"]] == [
        i for i in ids if i != "herdr-app"
    ]
    assert new_preamble == preamble
    assert new_blocks == {k: v for k, v in blocks.items() if k != "herdr-app"}
    assert filtered == preamble + "".join(v for k, v in blocks.items() if k != "herdr-app")
    app_comment = blocks["herdr-app"].split("[[tool]]", 1)[0]
    assert app_comment not in filtered and "releases.herdr.dev/app/install.sh" not in filtered
    for tool in ("iterm2", "ghostty", "herdr"):
        comment = blocks[tool].split("[[tool]]", 1)[0]
        assert comment and comment in filtered
    assert "# Verified 2026-11-08, re-checked" in new_blocks["herdr"]
    assert 'id = "herdr-app"' not in filtered
    assert blocks["herdr-app"].split("[[tool]]", 1)[1] not in filtered


def test_the_generic_skip_awk_with_an_empty_list_changes_nothing_and_with_two_ids_drops_both(
    tmp_path: Path,
) -> None:
    original = _REGISTRY.read_text(encoding="utf-8")
    assert _filter_registry(tmp_path, "") == original
    assert _filter_registry(tmp_path, "nonexistent") == original
    preamble, blocks = _blocks(original)
    assert _filter_registry(tmp_path, "iterm2,herdr-app") == preamble + "".join(
        block for name, block in blocks.items() if name not in {"iterm2", "herdr-app"}
    )


def test_the_generic_skip_list_is_exactly_the_dedicated_targets() -> None:
    text = _text()
    assert re.findall(r"^GENERIC_SKIP_TOOLS=.*$", text, re.MULTILINE) == [
        "GENERIC_SKIP_TOOLS=herdr-app,aws-cli"
    ]
    before = text.split("GENERIC_SKIP_TOOLS=herdr-app,aws-cli", 1)[0].splitlines()[-5:]
    assert all(word in " ".join(before) for word in ("herdr-app", "herdr-core", "target"))


def test_the_filter_runs_in_the_generic_commands_only() -> None:
    for name, before, after in (
        ("cmd_bootstrap", "  copy_workspace", "  bootstrap_homebrew_and_uv"),
        ("cmd_resync", "  resync_workspace", "  sync_workspace"),
        ("nested_prepare", "  copy_workspace || return 1", "  bootstrap_uv || return 1"),
    ):
        lines = _function(name).splitlines()
        call = "  drop_generic_skipped_tools || return 1"
        assert lines.count(call) == 1
        assert lines.index(before) < lines.index(call) < lines.index(after)
    for name in ("landing_bootstrap", "cmd_ghostty", "cmd_herdr_keys", "cmd_herdr_app"):
        assert "drop_generic_skipped_tools" not in _function(name)


_HELPERS: Final = (
    "exec_root",
    "install_github_token",
    "copy_workspace",
    "drop_generic_skipped_tools",
    "bootstrap_uv",
    "write_tester_path",
    "sync_workspace",
    "ensure_phase_dir",
    "start_container",
    "distro_release_record",
    "install_root_prereqs",
    "create_tester",
    "bootstrap_homebrew_and_uv",
    "container_running",
    "resync_workspace",
)


def _stub_helpers(failure: str = "") -> str:
    return "\n".join(
        f"{name}() {{ echo {name}; return {int(name == failure)}; }}" for name in _HELPERS
    )


def test_nested_prepare_filters_the_registry_copy_after_the_workspace_copy(tmp_path: Path) -> None:
    for failed in ("", "copy_workspace"):
        result = _run(
            _script(
                "nested_prepare", stubs="set -e\n" + _stub_helpers(failed) + "\nnested_prepare\n"
            ),
            tmp_path / (failed or "ok"),
        )
        expected = list(_HELPERS[:7])
        assert result.stdout.splitlines() == (expected if not failed else expected[:3])
        assert result.returncode == int(bool(failed))


def test_a_failing_filter_stops_the_bootstrap_and_the_sync(tmp_path: Path) -> None:
    for name, forbidden in (
        ("nested_prepare", ("bootstrap_uv", "write_tester_path", "sync_workspace")),
        ("cmd_bootstrap", ("bootstrap_homebrew_and_uv",)),
        ("cmd_resync", ("sync_workspace", "TRACER_RESYNC_OK")),
    ):
        result = _run(
            _script(
                name, stubs="set -e\n" + _stub_helpers("drop_generic_skipped_tools") + f"\n{name}\n"
            ),
            tmp_path / name,
        )
        assert result.returncode != 0
        assert "drop_generic_skipped_tools" in result.stdout
        assert all(item not in result.stdout.splitlines() for item in forbidden)


def _filter_script(tmp_path: Path, stub: str, skip: str = "herdr-app") -> str:
    return _script(
        "drop_generic_skipped_tools",
        "exec_tester",
        variables={
            "GENERIC_SKIP_TOOLS": skip,
            "GENERIC_SKIP_AWK": _awk_program(),
            "TESTER_WORKSPACE": str(tmp_path / "workspace"),
            "CONTAINER_NAME": "test-container",
            "TESTER_USER": "tester",
        },
        stubs=stub + "\ndrop_generic_skipped_tools\n",
    )


def test_the_filter_function_stages_the_program_and_cleans_up(tmp_path: Path) -> None:
    stub = """ct() {
  printf 'ct %s\\n' "$*" >> "$CALLS"
  if [[ "$2" == -i ]]; then cat > "$HOME/stdin"; fi
}
"""
    result = _run(_filter_script(tmp_path, stub), tmp_path)
    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path)
    assert sum(call.startswith("ct exec ") for call in calls) == 2
    assert (
        "ct exec -i test-container su - tester -c cat > /tmp/tools-installer-generic-skip.awk"
        in calls[0]
    )
    command = "\n".join(calls[1:])
    assert (
        "awk -v skip=herdr-app -f /tmp/tools-installer-generic-skip.awk installer/registry.toml"
        in command
    )
    assert "mv installer/registry.toml.skip installer/registry.toml" in command
    assert "rm -f /tmp/tools-installer-generic-skip.awk installer/registry.toml.skip" in command
    assert (tmp_path / "stdin").read_text() == _awk_program() + "\n"
    empty = tmp_path / "empty"
    assert _run(_filter_script(empty, stub, ""), empty).returncode == 0
    assert _calls(empty) == []


def test_the_filter_function_propagates_each_failure_and_still_cleans_up(tmp_path: Path) -> None:
    for failure in ("stage", "command"):
        scratch = tmp_path / failure
        stub = f"""ct() {{
  printf 'ct %s\\n' "$*" >> "$CALLS"
  if [[ "$2" == -i ]]; then
    cat > /dev/null; [[ {failure} != stage ]]
  else
    [[ {failure} != command ]]
  fi
}}
"""
        result = _run(_filter_script(scratch, stub), scratch)
        assert result.returncode != 0
        calls = _calls(scratch)
        assert any("rm -f /tmp/tools-installer-generic-skip.awk" in call for call in calls)
    for failure in ("awk", "mv"):
        scratch = tmp_path / failure
        workspace = scratch / "workspace/installer"
        workspace.mkdir(parents=True)
        registry = workspace / "registry.toml"
        original = _REGISTRY.read_text()
        registry.write_text(original)
        stub = rf"""ct() {{
  if [[ "$2" == -i ]]; then cat > "$HOME/staged"; return; fi
  local command="${{*: -1}}"
  command="${{command//\/tmp\/tools-installer-generic-skip.awk/$HOME\/staged}}"
  {failure}() {{ return 3; }}; export -f {failure}
  bash -c "$command"
}}
"""
        result = _run(_filter_script(scratch, stub), scratch)
        assert result.returncode != 0
        assert not (scratch / "staged").exists()
        assert not (workspace / "registry.toml.skip").exists()
        assert registry.read_text() == original


def test_the_production_registry_keeps_herdr_app() -> None:
    assert "herdr-app" in [tool.id for tool in load_tools(_REGISTRY)]
