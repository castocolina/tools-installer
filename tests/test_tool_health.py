"""The pure Health precedence core (phase 19-03, D-01 / SPEC R2)."""

import pytest

from installer.version_status import Evidence, Health, tool_health

Row = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], Health]


def test_health_declaration_order_is_precedence() -> None:
    assert [h.name for h in Health] == [
        "CHECKING",
        "BROKEN",
        "MISCONFIGURED",
        "OUTDATED",
        "OK",
        "MISSING",
        "UNAVAILABLE",
    ]
    for member in Health:
        assert member.value == member.name.lower()


PRESENT_ROWS: list[Row] = [
    # (checking, broken, misconfigured, outdated, expected Health)
    ((), (), (), (), Health.OK),
    (("probing",), (), (), (), Health.CHECKING),
    ((), ("shim present, package missing",), (), (), Health.BROKEN),
    ((), (), ("config owned by npm",), (), Health.MISCONFIGURED),
    ((), (), (), ("1.2.3 -> 1.3.0 available",), Health.OUTDATED),
    (("probing",), ("broken",), (), (), Health.CHECKING),
    (("probing",), (), ("m",), (), Health.CHECKING),
    (("probing",), (), (), ("o",), Health.CHECKING),
    (("probing",), ("broken",), ("m",), (), Health.CHECKING),
    (("probing",), ("broken",), (), ("o",), Health.CHECKING),
    (("probing",), (), ("m",), ("o",), Health.CHECKING),
    (("probing",), ("broken",), ("m",), ("o",), Health.CHECKING),
    ((), ("broken",), ("m",), (), Health.BROKEN),
    ((), ("broken",), (), ("o",), Health.BROKEN),
    ((), ("broken",), ("m",), ("o",), Health.BROKEN),
    ((), (), ("m",), ("o",), Health.MISCONFIGURED),
]


@pytest.mark.parametrize(
    ("checking", "broken", "misconfigured", "outdated", "expected"),
    PRESENT_ROWS,
)
def test_tool_health_precedence_table(
    checking: tuple[str, ...],
    broken: tuple[str, ...],
    misconfigured: tuple[str, ...],
    outdated: tuple[str, ...],
    expected: Health,
) -> None:
    ev = Evidence(
        present=True,
        available=True,
        checking=checking,
        broken=broken,
        misconfigured=misconfigured,
        outdated=outdated,
    )
    health, _reasons = tool_health(ev)
    assert health is expected


@pytest.mark.parametrize("available", [True, False])
def test_tool_health_precedence_table_absent(available: bool) -> None:
    ev = Evidence(present=False, available=available)
    health, _reasons = tool_health(ev)
    assert health is (Health.MISSING if available else Health.UNAVAILABLE)


def test_broken_and_outdated_is_broken_with_both_reasons() -> None:
    ev = Evidence(
        present=True,
        available=True,
        broken=("shim present, package missing — remove the shim",),
        outdated=("1.2.3 -> 1.3.0 available",),
    )
    assert tool_health(ev) == (
        Health.BROKEN,
        ("shim present, package missing — remove the shim", "1.2.3 -> 1.3.0 available"),
    )


def test_reasons_put_the_winner_first_then_precedence_then_notes() -> None:
    ev = Evidence(
        present=True,
        available=True,
        misconfigured=("m",),
        outdated=("o",),
        notes=("n1", "n2"),
    )
    assert tool_health(ev) == (Health.MISCONFIGURED, ("m", "o", "n1", "n2"))


def test_reasons_follow_precedence_when_groups_share_a_tuple() -> None:
    """Precedence is the Health, not the tuple's identity (G17).

    One tuple object is both the broken and misconfigured facts. The winner's
    fact stays first, then the other group's fact, then the note.
    """
    shared = ("fact",)
    ev = Evidence(
        present=True,
        available=True,
        broken=shared,
        misconfigured=shared,
        outdated=("outdated fact",),
        notes=("note",),
    )
    assert tool_health(ev) == (Health.BROKEN, ("fact", "outdated fact", "note"))


def test_unavailable_lists_its_reason_first() -> None:
    ev = Evidence(present=False, available=False, absent_reason="needs macOS", notes=("x",))
    assert tool_health(ev) == (Health.UNAVAILABLE, ("needs macOS", "x"))


def test_missing_keeps_its_notes() -> None:
    note = "/usr/bin/java is the macOS stub; install a real JDK"
    ev = Evidence(present=False, available=True, notes=(note,))
    assert tool_health(ev) == (Health.MISSING, (note,))


def test_absent_tools_ignore_present_only_facts() -> None:
    ev = Evidence(present=False, available=False, broken=("b",), outdated=("o",))
    health, reasons = tool_health(ev)
    assert health is Health.UNAVAILABLE
    assert "b" not in reasons
    assert "o" not in reasons


def test_absent_tool_keeps_configuration_notes() -> None:
    ev = Evidence(
        present=False,
        available=True,
        misconfigured=("m",),
        notes=(
            "disabled: superpowers@claude-plugins-official in user scope (6.4.1)",
            "duplicate: superpowers@superpowers-marketplace in user scope (6.2.0)",
            "no manager claimed the tool",
        ),
    )
    assert tool_health(ev) == (
        Health.MISSING,
        (
            "disabled: superpowers@claude-plugins-official in user scope (6.4.1)",
            "duplicate: superpowers@superpowers-marketplace in user scope (6.2.0)",
            "no manager claimed the tool",
        ),
    )


def test_notes_never_change_the_state() -> None:
    ev = Evidence(
        present=True,
        available=True,
        notes=("shadowed by /usr/local/bin/rg", "off-policy: installed outside the registry"),
    )
    assert tool_health(ev) == (
        Health.OK,
        ("shadowed by /usr/local/bin/rg", "off-policy: installed outside the registry"),
    )


def test_duplicate_sentences_are_listed_once() -> None:
    ev = Evidence(
        present=True,
        available=True,
        broken=("dup",),
        outdated=("dup",),
        notes=("dup", "other"),
    )
    assert tool_health(ev) == (Health.BROKEN, ("dup", "other"))
