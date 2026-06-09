from pathlib import Path

from installer.doctor import DoctorReport, audit_path, has_problems


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
