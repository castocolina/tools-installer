import io
from pathlib import Path

import pytest
from rich.console import Console

from installer.doctor import DoctorReport, audit_path, has_problems


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    console = Console(file=buf, width=100, force_terminal=False)
    return console, buf


def _exists(present: set[str]):
    def exists(path: Path) -> bool:
        return str(path) in present

    return exists


def test_audit_flags_missing_broken_and_duplicated():
    bin_dirs = [Path("/a/bin"), Path("/b/bin"), Path("/c/bin")]
    path_value = "/a/bin:/b/bin:/b/bin:/usr/bin"
    exists = _exists({"/a/bin", "/b/bin"})  # /c/bin does not exist
    report = audit_path(bin_dirs, path_value, exists)
    assert report.missing == (Path("/c/bin"),)  # declared but not on PATH
    assert report.broken == (Path("/c/bin"),)  # does not exist on disk
    assert report.duplicated == (Path("/b/bin"),)  # appears twice on PATH


def test_audit_clean_when_all_present_unique_and_existing():
    bin_dirs = [Path("/a/bin")]
    report = audit_path(bin_dirs, "/a/bin:/usr/bin", _exists({"/a/bin"}))
    assert report == DoctorReport(missing=(), broken=(), duplicated=())
    assert has_problems(report) is False


def test_audit_ignores_empty_path_entries():
    report = audit_path([Path("/a/bin")], "/a/bin::", _exists({"/a/bin"}))
    assert report.duplicated == ()


def test_has_problems_true_when_any_bucket_nonempty():
    assert has_problems(DoctorReport(missing=(Path("/x"),), broken=(), duplicated=())) is True


# --- D-13: broken-link scan (plan 17-04) -------------------------------------


def _patch_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path, raising=True)
    monkeypatch.setenv("HOME", str(tmp_path))


def test_scan_reports_a_link_to_a_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from installer.doctor import BrokenLink, scan_bin_links
    from installer.locations import opt_dir

    _patch_home(monkeypatch, tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    target = opt_dir("subl") / "sublime_text"
    target.mkdir(parents=True)  # the live host case: the member is a directory
    bin_dir.mkdir(parents=True)
    link = bin_dir / "subl"
    link.symlink_to(str(target))

    found = scan_bin_links(bin_dir)
    assert found == (
        BrokenLink(path=link, target=str(target), kind="directory", opt_dir=opt_dir("subl")),
    )


def test_scan_ignores_regular_files_and_good_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from installer.doctor import scan_bin_links

    _patch_home(monkeypatch, tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "plain").write_text("x")
    good_target = tmp_path / "real-tool"
    good_target.write_text("binary")
    (bin_dir / "good").symlink_to(str(good_target))

    assert scan_bin_links(bin_dir) == ()
    assert scan_bin_links(tmp_path / "missing-bin") == ()


def test_run_doctor_reports_broken_links_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.app import run_doctor
    from installer.platform import Platform

    _patch_home(monkeypatch, tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    target = tmp_path / ".local" / "opt" / "subl" / "sublime_text"
    target.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (bin_dir / "subl").symlink_to(str(target))

    def snapshot():
        def entry(p: Path):
            if p.is_symlink():
                return "link:" + str(p.readlink())
            if p.is_file():
                return p.read_bytes()
            return "dir"

        return {str(p): entry(p) for p in sorted(tmp_path.rglob("*"))}

    before = snapshot()
    console, buf = _console()
    report = run_doctor(
        [],
        console,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda p: p.exists(),
    )
    assert snapshot() == before  # diagnosis only: the tree is untouched

    assert [str(link.path) for link in report.broken_links] == [str(bin_dir / "subl")]
    out = " ".join(buf.getvalue().split())  # console wrapping must not hide the words
    assert "opt/subl" in out
    assert "reinstall subl" in out


def test_scan_reports_a_dangling_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from installer.doctor import scan_bin_links
    from installer.locations import opt_dir

    _patch_home(monkeypatch, tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ghost").symlink_to(str(opt_dir("ghost") / "ghost"))
    (bin_dir / "shim").symlink_to("/elsewhere/x")  # absolute, missing, not in any opt dir

    found = {link.path.name: link for link in scan_bin_links(bin_dir)}
    assert set(found) == {"ghost", "shim"}
    assert found["ghost"].kind == "dangling"
    assert found["ghost"].opt_dir == opt_dir("ghost")
    assert found["shim"].kind == "dangling"
    assert found["shim"].opt_dir is None
