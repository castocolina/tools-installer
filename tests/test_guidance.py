from pathlib import Path

from installer.doctor import DoctorReport
from installer.guidance import Guidance, doctor_guidance, guard_guidance, node_globals_guidance
from installer.pnpm_globals import NodeGlobal, NodeGlobalsReport


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


def test_guard_guidance_reports_active_guards_with_per_command_labels() -> None:
    items = guard_guidance({"npx": True, "pip": True, "npm": False}, None)
    item = next(i for i in items if "guards active" in i.title)
    assert item.severity == "ok"
    assert item.title == "Package manager guards active"
    assert "npx: redirected to pnpm dlx" in item.meaning
    assert "pip: blocked" in item.meaning
    assert "npm:" not in item.meaning
    assert "hash -r" in item.next_step


def test_guard_guidance_reports_path_order_warning() -> None:
    items = guard_guidance({"pip": False}, "shim dir is behind the real binary")
    item = next(i for i in items if "order" in i.title.lower())
    assert item.severity == "warn"
    assert item.meaning == "shim dir is behind the real binary"
    assert item.next_step


def test_guard_guidance_npm_label_names_volta_split() -> None:
    items = guard_guidance({"npm": True}, None)
    item = next(i for i in items if "guards active" in i.title)
    assert "npm: global installs redirected to volta install, other npm use blocked" in item.meaning


def test_guard_guidance_entries_follow_guarded_names_order() -> None:
    items = guard_guidance({"npx": True, "pip": True, "npm": False}, None)
    item = next(i for i in items if "guards active" in i.title)
    assert item.meaning.index("pip:") < item.meaning.index("npx:")


def test_guard_guidance_cross_references_warning_when_redirect_is_active() -> None:
    items = guard_guidance({"npx": True}, "npx is hard-blocked because pnpm was not resolvable")
    item = next(i for i in items if "guards active" in i.title)
    without = next(i for i in guard_guidance({"npx": True}, None) if "guards active" in i.title)
    assert len(item.meaning) > len(without.meaning)
    assert "warning" in item.meaning.lower()


def test_guard_guidance_no_cross_reference_without_warning() -> None:
    items = guard_guidance({"npx": True}, None)
    item = next(i for i in items if "guards active" in i.title)
    assert "warning" not in item.meaning.lower()


def test_guard_guidance_no_cross_reference_for_plain_block() -> None:
    items = guard_guidance({"pip": True}, "PATH order warning")
    item = next(i for i in items if "guards active" in i.title)
    assert "warning" not in item.meaning.lower()


def test_guard_guidance_volta_note_follows_guards_when_pnpm_is_live() -> None:
    items = guard_guidance({"pnpm": True, "npm": True}, None)
    assert "guards active" in items[0].title
    volta = items[1]
    assert "volta" in volta.title.lower()
    assert volta.severity == "ok"
    assert "npm install --global" in volta.meaning
    assert "install scripts" in volta.meaning
    assert "pnpm add" in volta.next_step


def test_guard_guidance_volta_note_shown_when_only_the_npm_wrapper_is_live() -> None:
    # install_global_redirect_shims writes the npm wrapper whenever volta
    # resolves, pnpm or no pnpm — and `npm i -g pnpm` is itself redirected now,
    # so volta-with-no-pnpm is a normal machine, not an edge case.
    items = guard_guidance({"npm": True, "pnpm": False}, None)
    volta = next(i for i in items if "volta" in i.title.lower())
    assert "npm install --global" in volta.meaning
    assert "pnpm add" in volta.next_step


def test_guard_guidance_volta_note_absent_when_no_redirect_name_is_live() -> None:
    items = guard_guidance({"pip": True, "npm": False, "pnpm": False}, None)
    assert not [i for i in items if "volta" in i.title.lower()]


def test_guard_guidance_volta_note_never_appears_alone() -> None:
    assert guard_guidance({"pip": False, "npm": False}, None) == []


def test_node_globals_guidance_silent_when_empty() -> None:
    assert node_globals_guidance(NodeGlobalsReport(entries=(), missing=(), managed=())) == []


def test_node_globals_guidance_silent_when_healthy() -> None:
    entries = (NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),)
    assert (
        node_globals_guidance(
            NodeGlobalsReport(entries=entries, missing=(), managed=("@mermaid-js/mermaid-cli",))
        )
        == []
    )


def test_node_globals_guidance_warns_and_points_at_make_setup() -> None:
    entries = (NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),)
    items = node_globals_guidance(
        NodeGlobalsReport(entries=entries, missing=("mmdc",), managed=("@mermaid-js/mermaid-cli",))
    )
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert "mmdc" in item.meaning
    assert "pnpm" in item.meaning.lower()
    assert item.next_step.startswith("Run `make setup`")


def test_node_globals_guidance_warns_on_a_split_install_group() -> None:
    items = node_globals_guidance(
        NodeGlobalsReport(
            entries=(),
            missing=(),
            managed=("@mermaid-js/mermaid-cli", "puppeteer"),
            split_groups=(("@mermaid-js/mermaid-cli", "puppeteer"),),
        )
    )
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert "puppeteer" in item.meaning
    assert "mermaid" in item.meaning
    assert item.next_step.startswith("Run `make setup`")


def test_node_globals_guidance_reports_missing_and_split_together() -> None:
    items = node_globals_guidance(
        NodeGlobalsReport(
            entries=(NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),),
            missing=("mmdc",),
            managed=("@mermaid-js/mermaid-cli", "puppeteer"),
            split_groups=(("@mermaid-js/mermaid-cli", "puppeteer"),),
        )
    )
    assert len(items) == 2
    assert items[0].next_step.startswith("Run `make setup`")
    assert items[1].next_step.startswith("Run `make setup`")
    assert "puppeteer" in items[1].meaning


def test_guidance_is_frozen() -> None:
    g = Guidance(title="t", meaning="m", next_step="n", severity="ok")
    try:
        g.title = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Guidance should be frozen")
