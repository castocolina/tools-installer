from installer.model import Method, Tool
from installer.selection import (
    Choice,
    categories,
    select_tools,
    tools_in,
    unstaged_recommends,
)


def _tool(tool_id: str, category: str, desc: str = "", *, recommends: tuple[str, ...] = ()) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        desc=desc,
        recommends=recommends,
    )


def test_categories_are_unique_in_first_seen_order() -> None:
    tools = [_tool("rg", "search"), _tool("jq", "data"), _tool("fd", "search")]
    assert categories(tools) == ["search", "data"]


def test_tools_in_filters_by_category() -> None:
    tools = [_tool("rg", "search"), _tool("jq", "data"), _tool("fd", "search")]
    assert [t.id for t in tools_in(tools, "search")] == ["rg", "fd"]


def test_tools_in_unknown_category_is_empty() -> None:
    assert tools_in([_tool("rg", "search")], "ghost") == []


def test_choice_tag_and_description_default_empty() -> None:
    choice = Choice(id="x", label="x", checked=False)
    assert choice.tag == ""
    assert choice.description == ""


def test_select_tools_keeps_catalog_order_and_ignores_unknown_ids() -> None:
    tools = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    assert [t.id for t in select_tools(tools, ["jq", "rg", "ghost"])] == ["rg", "jq"]


def test_unstaged_recommends_names_uninstalled_unstaged_ids() -> None:
    catalog = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    tool = _tool("claude", "ai", recommends=("rg", "fd", "jq"))
    assert unstaged_recommends(tool, catalog, staged=set[str](), installed={}) == ("rg", "fd", "jq")


def test_unstaged_recommends_skips_staged_installed_and_unknown() -> None:
    catalog = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    tool = _tool("claude", "ai", recommends=("rg", "fd", "jq", "ghost"))
    assert unstaged_recommends(tool, catalog, staged={"rg"}, installed={"jq": True}) == ("fd",)
    assert (
        unstaged_recommends(tool, catalog, staged={"rg", "fd", "jq"}, installed=dict[str, bool]())
        == ()
    )


def test_unstaged_recommends_is_flat_one_hop() -> None:
    a = _tool("a", "x", recommends=("b",))
    b = _tool("b", "x", recommends=("c",))
    c = _tool("c", "x")
    catalog = [a, b, c]
    assert unstaged_recommends(a, catalog, staged=set[str](), installed={}) == ("b",)


def test_unstaged_recommends_dedupes_preserving_declared_order() -> None:
    catalog = [_tool("rg", "search"), _tool("jq", "data")]
    tool = _tool("claude", "ai", recommends=("jq", "rg", "jq"))
    assert unstaged_recommends(tool, catalog, staged=set[str](), installed={}) == ("jq", "rg")


def test_unstaged_recommends_skips_unavailable_ids() -> None:
    catalog = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    tool = _tool("claude", "ai", recommends=("rg", "fd", "jq"))
    assert unstaged_recommends(
        tool, catalog, staged=set[str](), installed={}, unavailable={"jq": True}
    ) == ("rg", "fd")
    assert unstaged_recommends(tool, catalog, staged=set[str](), installed={}) == ("rg", "fd", "jq")
