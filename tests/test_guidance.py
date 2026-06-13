from pathlib import Path

from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance


def test_healthy_report_yields_a_single_ok_item() -> None:
    items = doctor_guidance(DoctorReport(missing=(), broken=(), duplicated=()))
    assert len(items) == 1
    assert items[0].severity == "ok"
    assert "healthy" in items[0].title.lower()
    assert items[0].next_step == ""  # nothing to do


def test_broken_dir_is_an_error_with_meaning_and_next_step() -> None:
    items = doctor_guidance(DoctorReport(missing=(), broken=(Path("/c/bin"),), duplicated=()))
    item = next(i for i in items if "/c/bin" in i.title)
    assert item.severity == "error"
    assert item.meaning and item.next_step
    assert "/c/bin" in item.meaning


def test_missing_dir_warns_and_points_at_make_fix() -> None:
    items = doctor_guidance(DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()))
    item = next(i for i in items if "/a/bin" in i.title)
    assert item.severity == "warn"
    assert "make fix" in item.next_step
    assert "new terminal" in item.next_step or "source" in item.next_step


def test_duplicated_dir_warns_and_says_duplicates_clear_on_reload() -> None:
    items = doctor_guidance(DoctorReport(missing=(), broken=(), duplicated=(Path("/b/bin"),)))
    item = next(i for i in items if "/b/bin" in i.title)
    assert item.severity == "warn"
    assert "new shell" in item.next_step.lower() or "reload" in item.next_step.lower()


def test_every_problem_finding_carries_meaning_and_next_step() -> None:
    report = DoctorReport(
        missing=(Path("/a/bin"),), broken=(Path("/c/bin"),), duplicated=(Path("/b/bin"),)
    )
    items = doctor_guidance(report)
    assert len(items) == 3  # no healthy item when there are problems
    assert all(i.meaning and i.next_step for i in items)


def test_guard_guidance_silent_when_inactive_and_no_warning() -> None:
    assert guard_guidance({"pip": False, "npm": False}, None) == []


def test_guard_guidance_reports_active_ban_with_reload_step() -> None:
    items = guard_guidance({"pip": True, "npm": False}, None)
    item = next(i for i in items if "ban active" in i.title)
    assert item.severity == "ok"
    assert "pip" in item.meaning
    assert "hash -r" in item.next_step or "new shell" in item.next_step


def test_guard_guidance_reports_path_order_warning() -> None:
    items = guard_guidance({"pip": False}, "shim dir is behind the real binary")
    item = next(i for i in items if "order" in i.title.lower())
    assert item.severity == "warn"
    assert "shim dir is behind the real binary" in item.meaning
    assert item.next_step


def test_guidance_is_frozen() -> None:
    g = Guidance(title="t", meaning="m", next_step="n", severity="ok")
    try:
        g.title = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Guidance should be frozen")
