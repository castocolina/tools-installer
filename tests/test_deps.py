import pytest

from installer.deps import (
    DependencyCycleError,
    Resolution,
    requires_integrity_errors,
    resolve_dependencies,
)
from installer.model import Method, Tool


def _tool(tool_id: str, *requires: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(Method(kind="node", params={"npm_pkg": f"@x/{tool_id}"}),),
        requires=tuple(requires),
    )


def _resolve(
    selected: list[Tool],
    catalog: list[Tool],
    *,
    available_ids: list[str] | None = None,
    installed_ids: tuple[str, ...] | list[str] = (),
) -> Resolution:
    ids: set[str] = {t.id for t in catalog} if available_ids is None else set(available_ids)
    installed: set[str] = set(installed_ids)
    return resolve_dependencies(
        selected,
        catalog,
        available=lambda t: t.id in ids,
        is_installed=lambda t: t.id in installed,
    )


def test_no_requires_returns_selection_unchanged() -> None:
    a, b = _tool("a"), _tool("b")
    result = _resolve([a, b], [a, b])
    assert isinstance(result, Resolution)
    assert [t.id for t in result.order] == ["a", "b"]
    assert result.dragged_in == ()
    assert result.warnings == ()


def test_missing_dependency_is_dragged_in() -> None:
    pnpm = _tool("pnpm")
    mmdc = _tool("mmdc", "pnpm")
    result = _resolve([mmdc], [mmdc, pnpm])
    assert "pnpm" in result.dragged_in
    assert [t.id for t in result.order] == ["pnpm", "mmdc"]


def test_already_installed_dependency_is_not_dragged_in() -> None:
    pnpm = _tool("pnpm")
    mmdc = _tool("mmdc", "pnpm")
    result = _resolve([mmdc], [mmdc, pnpm], installed_ids=["pnpm"])
    assert result.dragged_in == ()
    assert [t.id for t in result.order] == ["mmdc"]


def test_transitive_chain_orders_deepest_first() -> None:
    a = _tool("a", "b")
    b = _tool("b", "c")
    c = _tool("c")
    result = _resolve([a], [a, b, c])
    assert [t.id for t in result.order] == ["c", "b", "a"]


def test_diamond_installs_shared_dep_once_before_dependents() -> None:
    d = _tool("d")
    b = _tool("b", "d")
    c = _tool("c", "d")
    a = _tool("a", "b", "c")
    order = [t.id for t in _resolve([a], [a, b, c, d]).order]
    assert order.index("d") < order.index("b") < order.index("a")
    assert order.index("d") < order.index("c") < order.index("a")
    assert order.count("d") == 1


def test_cycle_raises_config_error_not_hang() -> None:
    a = _tool("a", "b")
    b = _tool("b", "a")
    with pytest.raises(DependencyCycleError):
        _resolve([a], [a, b])


def test_unavailable_dependency_skips_dependent_with_warning() -> None:
    dep = _tool("dep")
    user = _tool("user", "dep")
    result = _resolve([user], [user, dep], available_ids=["user"])
    assert [t.id for t in result.order] == []
    assert any("not available" in w for w in result.warnings)


def test_unavailable_but_installed_dependency_is_fine() -> None:
    dep = _tool("dep")
    user = _tool("user", "dep")
    result = _resolve([user], [user, dep], available_ids=["user"], installed_ids=["dep"])
    assert [t.id for t in result.order] == ["user"]
    assert result.warnings == ()


def test_unknown_required_id_warns_and_continues() -> None:
    user = _tool("user", "ghost")
    result = _resolve([user], [user])
    assert [t.id for t in result.order] == ["user"]
    assert any("unknown tool 'ghost'" in w for w in result.warnings)


def test_integrity_flags_unknown_requires_id() -> None:
    good = _tool("good")
    bad = _tool("bad", "ghost")
    errors = requires_integrity_errors([good, bad])
    assert any("bad" in e and "ghost" in e for e in errors)


def test_integrity_clean_catalog_has_no_errors() -> None:
    a = _tool("a", "b")
    b = _tool("b")
    assert requires_integrity_errors([a, b]) == []
