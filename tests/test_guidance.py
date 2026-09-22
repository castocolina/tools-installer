from pathlib import Path

from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.enums import DaemonState
from installer.guidance import (
    Guidance,
    competing_mechanism_guidance,
    disk_pressure_guidance,
    doctor_guidance,
    guard_guidance,
    node_globals_guidance,
)
from installer.pnpm_globals import IncompleteGroup, NodeGlobal, NodeGlobalsReport
from installer.systemd_daemon import CompetingUnit

# The exact sentence D-03c's UNAVAILABLE branch uses for its one-off manual
# prune next step. Pinned here, not imported, so this test independently
# proves the ACTIVE/INACTIVE branches never reuse it verbatim -- if they did,
# a reader could no longer tell "this is a one-off with nothing to enable"
# apart from "this has a policy to flip", which is the whole point of D-03c.
_RUNNABLE_PRUNE_SENTENCE = (
    "Run `./scripts/prune-user-tmpdir.sh --apply` for an immediate one-off cleanup."
)
# WR-08: the Linux rule (tmp_threshold) names the Linux script -- the macOS
# one defaults to $TMPDIR with no /tmp fallback and prunes another platform's
# file families entirely.
_RUNNABLE_PRUNE_SENTENCE_LINUX = (
    "Run `./scripts/prune-tmp-linux.sh --apply` for an immediate one-off cleanup."
)


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


def test_split_group_warning_states_the_measured_condition_not_a_disproved_one() -> None:
    """05-01's Tier-3 container measured BROWNFIELD_BEFORE=ok for this shape.

    A standalone mmdc plus a standalone allow-build puppeteer rendered fine on
    pnpm 12.3.4 with default `autoInstallPeers`, so "the dependent cannot load
    its peer at runtime" is an unmeasured consequence stated as fact — against
    this phase's own evidence. The defensible claim is narrower and is the one
    05-01 gives for keeping `co_install` at all: the pair survives only through
    a user-settable pnpm option.
    """
    items = node_globals_guidance(
        NodeGlobalsReport(
            entries=(),
            missing=(),
            managed=("@mermaid-js/mermaid-cli", "puppeteer"),
            split_groups=(("@mermaid-js/mermaid-cli", "puppeteer"),),
        )
    )
    meaning = items[0].meaning
    assert "cannot load its peer at runtime" not in meaning
    assert "auto-install-peers" in meaning


def test_node_globals_guidance_warns_on_an_incomplete_install_group() -> None:
    """The brownfield machine used to get NOTHING from the Doctor.

    `mmdc` present, `puppeteer` never installed globally: no missing command
    (mmdc resolves), no split (a split needs two present members), so every
    surface was silent while the tool could not render.
    """
    items = node_globals_guidance(
        NodeGlobalsReport(
            entries=(NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),),
            missing=(),
            managed=("@mermaid-js/mermaid-cli",),
            incomplete_groups=(
                IncompleteGroup(present=("@mermaid-js/mermaid-cli",), missing=("puppeteer",)),
            ),
        )
    )
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert "@mermaid-js/mermaid-cli" in item.meaning
    assert "puppeteer" in item.meaning
    assert item.next_step.startswith("Run `make setup`")


def test_group_members_are_joined_as_a_sentence_not_repeated_ands() -> None:
    items = node_globals_guidance(
        NodeGlobalsReport(
            entries=(),
            missing=(),
            managed=("a", "b", "c"),
            split_groups=(("a", "b", "c"),),
        )
    )
    assert "a, b and c" in items[0].meaning
    assert "a and b and c" not in items[0].meaning


def test_guidance_is_frozen() -> None:
    g = Guidance(title="t", meaning="m", next_step="n", severity="ok")
    try:
        g.title = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Guidance should be frozen")


def test_node_globals_guidance_warns_when_an_installed_tool_fails_its_smoke_check() -> None:
    """CR-02: install-time success is not evidence of ongoing correctness.

    The command still resolves, so `missing` is empty and every other surface
    is quiet — this item is the only one that reports the tool as broken.
    """
    items = node_globals_guidance(
        NodeGlobalsReport(
            entries=(NodeGlobal("puppeteer", "puppeteer", "puppeteer", "puppeteer-browser"),),
            missing=(),
            managed=("puppeteer",),
            unhealthy=(("puppeteer", "installed browser /x/chrome could not be started."),),
        )
    )
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert "puppeteer" in item.meaning
    assert "could not be started" in item.meaning
    # `r` replays pnpm's global set; a missing shared library is not in it.
    assert not item.next_step.startswith("Run `make setup`")
    assert item.next_step


def _pressure(
    *,
    home_free_percent: float | None,
    tmp_used_percent: float | None,
    daemon: DaemonState,
    tmp_threshold: bool = True,
) -> DiskPressure:
    return DiskPressure(
        home_free_percent=home_free_percent,
        tmp_used_percent=tmp_used_percent,
        daemon=daemon,
        tmp_threshold=tmp_threshold,
    )


def test_disk_pressure_guidance_inactive_low_disk_is_one_emphasised_error() -> None:
    pressure = _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.INACTIVE)
    items = disk_pressure_guidance(pressure)
    assert len(items) == 1
    item = items[0]
    assert item.severity == "error"
    assert item.emphasis is True
    assert "cleanup" in item.title.lower()
    assert "low" in item.title.lower() or "disk" in item.title.lower()
    assert "9.5%" in item.meaning
    assert item.next_step  # runnable from a console


def test_disk_pressure_guidance_inactive_high_tmp_is_one_emphasised_error_naming_tmp() -> None:
    pressure = _pressure(home_free_percent=None, tmp_used_percent=81.2, daemon=DaemonState.INACTIVE)
    items = disk_pressure_guidance(pressure)
    assert len(items) == 1
    item = items[0]
    assert item.severity == "error"
    assert item.emphasis is True
    assert "/tmp" in item.meaning
    assert "81.2%" in item.meaning
    assert "not only this tool" in item.meaning


def test_disk_pressure_guidance_inactive_both_conditions_is_still_one_item() -> None:
    pressure = _pressure(home_free_percent=9.5, tmp_used_percent=81.2, daemon=DaemonState.INACTIVE)
    items = disk_pressure_guidance(pressure)
    assert len(items) == 1  # never two competing red findings
    item = items[0]
    assert item.severity == "error"
    assert item.emphasis is True
    assert "9.5%" in item.meaning
    assert "81.2%" in item.meaning


def test_disk_pressure_guidance_active_low_disk_is_an_ordinary_non_emphasised_warning() -> None:
    pressure = _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.ACTIVE)
    items = disk_pressure_guidance(pressure)
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert item.emphasis is False


def test_disk_pressure_guidance_active_high_tmp_is_an_ordinary_non_emphasised_warning() -> None:
    pressure = _pressure(home_free_percent=None, tmp_used_percent=81.2, daemon=DaemonState.ACTIVE)
    items = disk_pressure_guidance(pressure)
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert item.emphasis is False


def test_disk_pressure_guidance_unavailable_is_an_ordinary_non_emphasised_warning() -> None:
    pressure = _pressure(
        home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.UNAVAILABLE
    )
    items = disk_pressure_guidance(pressure)
    assert len(items) == 1
    item = items[0]
    assert item.severity == "warn"
    assert item.emphasis is False
    assert "no managed background cleanup" in item.meaning.lower()


def test_disk_pressure_guidance_unavailable_next_step_is_the_runnable_prune_sentence() -> None:
    macos = _pressure(
        home_free_percent=9.5,
        tmp_used_percent=None,
        daemon=DaemonState.UNAVAILABLE,
        tmp_threshold=False,
    )
    assert _RUNNABLE_PRUNE_SENTENCE in disk_pressure_guidance(macos)[0].next_step
    linux = _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.UNAVAILABLE)
    assert _RUNNABLE_PRUNE_SENTENCE_LINUX in disk_pressure_guidance(linux)[0].next_step


def test_disk_pressure_guidance_unavailable_never_denies_the_row_exists_here() -> None:
    """IN-06: a timed-out or bus-error query is UNAVAILABLE on a host that
    does have the Policies row, so "no such policy on this host" was wrong."""
    pressure = _pressure(
        home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.UNAVAILABLE
    )
    item = disk_pressure_guidance(pressure)[0]
    assert "no such policy" not in item.next_step.lower()
    assert "could not be read" in item.next_step


def test_disk_pressure_guidance_next_step_names_the_platforms_own_prune_script() -> None:
    """WR-08: the emphasised INACTIVE finding's one immediate-relief command
    must run on the platform the /tmp rule applies to."""
    linux = _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.INACTIVE)
    linux_step = disk_pressure_guidance(linux)[0].next_step
    assert "prune-tmp-linux.sh --apply" in linux_step
    assert "prune-user-tmpdir.sh" not in linux_step
    macos = _pressure(
        home_free_percent=9.5,
        tmp_used_percent=None,
        daemon=DaemonState.INACTIVE,
        tmp_threshold=False,
    )
    macos_step = disk_pressure_guidance(macos)[0].next_step
    assert "prune-user-tmpdir.sh --apply" in macos_step
    assert "prune-tmp-linux.sh" not in macos_step


def test_disk_pressure_guidance_unavailable_next_step_never_offers_to_enable_a_row() -> None:
    pressure = _pressure(
        home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.UNAVAILABLE
    )
    item = disk_pressure_guidance(pressure)[0]
    assert "enable" not in item.next_step.lower()
    assert "policies" not in item.next_step.lower()
    assert "setup" not in item.next_step.lower()


def test_disk_pressure_guidance_inactive_next_step_points_at_enabling_the_policy() -> None:
    pressure = _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.INACTIVE)
    item = disk_pressure_guidance(pressure)[0]
    assert "enable" in item.next_step.lower()
    assert "prune-tmp-linux.sh" in item.next_step


def test_disk_pressure_guidance_inactive_and_active_never_use_the_unavailable_sentence() -> None:
    inactive = disk_pressure_guidance(
        _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.INACTIVE)
    )[0]
    active = disk_pressure_guidance(
        _pressure(home_free_percent=9.5, tmp_used_percent=None, daemon=DaemonState.ACTIVE)
    )[0]
    assert _RUNNABLE_PRUNE_SENTENCE not in inactive.next_step
    assert _RUNNABLE_PRUNE_SENTENCE not in active.next_step
    assert _RUNNABLE_PRUNE_SENTENCE_LINUX not in inactive.next_step
    assert _RUNNABLE_PRUNE_SENTENCE_LINUX not in active.next_step


def test_disk_pressure_guidance_empty_when_daemon_inactive_and_no_pressure() -> None:
    pressure = _pressure(home_free_percent=90.0, tmp_used_percent=0.0, daemon=DaemonState.INACTIVE)
    assert disk_pressure_guidance(pressure) == []


def test_disk_pressure_guidance_empty_when_daemon_unavailable_and_no_pressure() -> None:
    pressure = _pressure(
        home_free_percent=90.0, tmp_used_percent=0.0, daemon=DaemonState.UNAVAILABLE
    )
    assert disk_pressure_guidance(pressure) == []


def test_disk_pressure_guidance_empty_when_daemon_active_and_no_pressure() -> None:
    pressure = _pressure(home_free_percent=90.0, tmp_used_percent=0.0, daemon=DaemonState.ACTIVE)
    assert disk_pressure_guidance(pressure) == []


def test_disk_pressure_guidance_empty_for_every_daemon_state_when_percentages_unknown() -> None:
    for daemon in DaemonState:
        pressure = _pressure(home_free_percent=None, tmp_used_percent=None, daemon=daemon)
        assert disk_pressure_guidance(pressure) == []


def test_guidance_emphasis_defaults_to_false() -> None:
    g = Guidance(title="t", meaning="m", next_step="n", severity="ok")
    assert g.emphasis is False


def test_guidance_emphasis_can_be_set_true() -> None:
    g = Guidance(title="t", meaning="m", next_step="n", severity="error", emphasis=True)
    assert g.emphasis is True


def _competitor(name: str, scope: str) -> CompetingUnit:
    return CompetingUnit(name=name, scope=scope, state="enabled")


def test_competing_mechanism_guidance_is_silent_without_a_system_scope_unit() -> None:
    assert competing_mechanism_guidance(()) == []
    user_only = (_competitor("cleanup-bun-tmp-cache.timer", "user"),)
    # A user-scope competitor is taken over by the apply, so it is not a
    # standing disclosure here.
    assert competing_mechanism_guidance(user_only) == []


def test_competing_mechanism_guidance_names_the_unit_and_the_manual_root_command() -> None:
    """WR-10: D-02a's disclosure existed only inside the first apply's result,
    so a user who missed one console line never saw it again."""
    units = (_competitor("cleanup-bun-tmp-cache.timer", "system"),)
    [item] = competing_mechanism_guidance(units)
    assert "cleanup-bun-tmp-cache.timer" in item.title
    assert "sudo systemctl disable --now cleanup-bun-tmp-cache.timer" in item.meaning
    assert item.severity == "warn"
    assert item.emphasis is False
    assert "sudo" in item.next_step  # named as the user's own action, never run here


def test_duplicate_path_guidance_wording_is_unchanged() -> None:
    """15.8-01: The duplicate-PATH guidance wording is intentionally unchanged.

    Migration via apply_block makes this a runtime issue (in-memory PATH in an
    already-running shell) that resolves on shell restart. The existing wording
    already says so. No new wording is needed.
    """
    items = doctor_guidance(DoctorReport(missing=(), broken=(), duplicated=(Path("/b/bin"),)))
    item = next(i for i in items if "/b/bin" in i.title)
    assert item.severity == "warn"
    assert item.next_step
    assert "new shell" in item.next_step.lower() or "reload" in item.next_step.lower()
