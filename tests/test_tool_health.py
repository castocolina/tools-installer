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
