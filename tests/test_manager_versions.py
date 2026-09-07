from collections.abc import Collection

from installer.manager_versions import (
    ManagerVersion,
    brew_outdated,
    parse_brew_outdated_json,
    parse_pnpm_outdated_json,
    parse_uv_tool_outdated,
    pnpm_outdated_global,
    read_outdated,
    uv_tool_outdated,
)
from installer.run import CommandError

_BREW_PAYLOAD = """{
  "formulae": [
    {
      "name": "ast-grep",
      "installed_versions": ["0.45.1"],
      "current_version": "0.45.3",
      "pinned": false,
      "pinned_version": null
    },
    {
      "name": "broot",
      "installed_versions": ["1.58.0"],
      "current_version": "1.59.0",
      "pinned": false,
      "pinned_version": null
    }
  ],
  "casks": []
}"""

_PNPM_PAYLOAD = """{
  "pnpm": {
    "current": "11.9.0",
    "latest": "12.3.4",
    "wanted": "11.9.0",
    "isDeprecated": false,
    "dependencyType": "dependencies"
  }
}"""

_UV_PAYLOAD = """graphifyy v0.9.53 [latest: 0.9.55]
- graphify
- graphify-mcp
pre-commit v4.6.0 [latest: 4.6.2]
- pre-commit
"""


def test_parse_brew_outdated_json_section_4_1_payload() -> None:
    parsed = parse_brew_outdated_json(_BREW_PAYLOAD)
    assert parsed is not None
    formulae, casks = parsed
    assert formulae["ast-grep"] == ManagerVersion("0.45.1", "0.45.3")
    assert casks == {}


def test_parse_brew_outdated_json_keeps_formula_and_cask_namespaces_apart() -> None:
    payload = """{
      "formulae": [{"name": "foo", "installed_versions": ["1.0"], "current_version": "1.1"}],
      "casks": [{"name": "foo", "installed_versions": ["2.0"], "current_version": "2.1"}]
    }"""
    parsed = parse_brew_outdated_json(payload)
    assert parsed is not None
    formulae, casks = parsed
    assert formulae["foo"] == ManagerVersion("1.0", "1.1")
    assert casks["foo"] == ManagerVersion("2.0", "2.1")


def test_parse_brew_outdated_json_non_list_formulae_is_none() -> None:
    assert parse_brew_outdated_json('{"formulae": {}, "casks": []}') is None


def test_parse_brew_outdated_json_malformed_entry_is_none() -> None:
    payload = """{
      "formulae": [
        {"name": "ast-grep", "installed_versions": ["0.45.1"], "current_version": "0.45.3"},
        {"name": "broot", "installed_versions": ["1.58.0"]}
      ],
      "casks": []
    }"""
    assert parse_brew_outdated_json(payload) is None


def test_parse_brew_outdated_json_missing_casks_key_is_none() -> None:
    payload = """{
      "formulae": [
        {"name": "ast-grep", "installed_versions": ["0.45.1"], "current_version": "0.45.3"}
      ]
    }"""
    assert parse_brew_outdated_json(payload) is None


def test_parse_pnpm_outdated_json_section_4_2_payload() -> None:
    parsed = parse_pnpm_outdated_json(_PNPM_PAYLOAD)
    assert parsed == {"pnpm": ManagerVersion("11.9.0", "12.3.4")}


def test_parse_pnpm_outdated_json_malformed_entry_is_none() -> None:
    payload = """{
      "pnpm": {"current": "11.9.0", "latest": "12.3.4"},
      "broken": {"current": "1.0.0"}
    }"""
    assert parse_pnpm_outdated_json(payload) is None


def test_pnpm_outdated_global_accepts_exit_1() -> None:
    seen: dict[str, object] = {}

    def query(cmd: list[str], **kwargs: object) -> str:
        seen["cmd"] = cmd
        seen["accept_codes"] = kwargs.get("accept_codes")
        return _PNPM_PAYLOAD

    result = pnpm_outdated_global(resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm", query=query)
    assert result == {"pnpm": ManagerVersion("11.9.0", "12.3.4")}
    accept = seen["accept_codes"]
    assert isinstance(accept, Collection)
    assert 1 in accept


def test_pnpm_outdated_global_exit_2_is_none() -> None:
    def query(cmd: list[str], **_kwargs: object) -> str:
        raise CommandError(cmd, 2)

    assert pnpm_outdated_global(resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm", query=query) is None


def test_pnpm_outdated_global_uses_absolute_path_not_bare_name() -> None:
    seen: list[list[str]] = []

    def query(cmd: list[str], **_kwargs: object) -> str:
        seen.append(cmd)
        return "{}"

    pnpm_outdated_global(resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm", query=query)
    assert seen
    assert seen[0][0] == "/opt/homebrew/bin/pnpm"
    assert "pnpm" not in seen[0]


def test_parse_uv_tool_outdated_section_4_3_payload() -> None:
    parsed = parse_uv_tool_outdated(_UV_PAYLOAD)
    assert parsed == {
        "graphifyy": ManagerVersion("0.9.53", "0.9.55"),
        "pre-commit": ManagerVersion("4.6.0", "4.6.2"),
    }


def test_parse_uv_tool_outdated_fail_closed_cases() -> None:
    # Absence from a non-None map means up to date, so garbage must not become {}.
    assert parse_uv_tool_outdated("warning: format changed\n" + _UV_PAYLOAD) is None
    assert parse_uv_tool_outdated("graphifyy v0.9.53 [latest: 0.9.55\n") is None
    assert parse_uv_tool_outdated("No tools installed\n") == {}
    assert parse_uv_tool_outdated("") == {}


def test_brew_outdated_sets_homebrew_env_overrides() -> None:
    seen: dict[str, object] = {}

    def query(cmd: list[str], **kwargs: object) -> str:
        seen["cmd"] = cmd
        seen["env"] = kwargs.get("env")
        return _BREW_PAYLOAD

    result = brew_outdated(query=query)
    assert result is not None
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["HOMEBREW_NO_AUTO_UPDATE"] == "1"
    assert env["HOMEBREW_NO_ENV_HINTS"] == "1"
    assert seen["cmd"] == ["brew", "outdated", "--json=v2"]


def test_read_outdated_isolates_brew_failure() -> None:
    def query(cmd: list[str], **_kwargs: object) -> str:
        if cmd and cmd[0] == "brew":
            raise CommandError(cmd, 1)
        if cmd[:3] == ["uv", "tool", "list"]:
            return _UV_PAYLOAD
        if "outdated" in cmd:
            return "{}"
        raise AssertionError(cmd)

    report = read_outdated(
        has_brew=True,
        query=query,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    assert report.brew is None
    assert report.cask is None
    assert report.uv is not None
    assert "graphifyy" in report.uv


def test_read_outdated_skips_brew_when_absent() -> None:
    calls: list[list[str]] = []

    def query(cmd: list[str], **_kwargs: object) -> str:
        calls.append(cmd)
        if cmd[:3] == ["uv", "tool", "list"]:
            return ""
        return "{}"

    report = read_outdated(
        has_brew=False,
        query=query,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    assert all(cmd[0] != "brew" for cmd in calls)
    assert report.brew is None
    assert report.cask is None


def test_read_outdated_issues_at_most_three_queries() -> None:
    calls: list[list[str]] = []

    def query(cmd: list[str], **_kwargs: object) -> str:
        calls.append(cmd)
        if cmd[:3] == ["uv", "tool", "list"]:
            return ""
        if cmd[0] == "brew":
            return _BREW_PAYLOAD
        return "{}"

    read_outdated(has_brew=True, query=query, resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm")
    assert len(calls) == 3


def test_uv_tool_outdated_none_on_command_error() -> None:
    def query(cmd: list[str], **_kwargs: object) -> str:
        raise CommandError(cmd, 127)

    assert uv_tool_outdated(query=query) is None
