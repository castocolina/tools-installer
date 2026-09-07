import json
import subprocess

import pytest

import installer.install_ownership as ownership
from installer.install_ownership import Ownership, detect_owner
from installer.model import Method, Tool


def _tool(
    *,
    owner_probes: tuple[str, ...] = (),
    methods: tuple[Method, ...] | None = None,
) -> Tool:
    return Tool(
        id="demo",
        name="Demo",
        category="dev",
        cmd="demo",
        methods=methods or (Method(kind="brew", params={"formula": "demo"}),),
        owner_probes=owner_probes,
    )


def _manager_for(command: list[str]) -> str:
    return {
        "tools-installer-managed-download": "managed-download",
        "brew": "brew",
        "dpkg-query": "apt",
        "rpm": "dnf",
        "pacman": "pacman",
        "pnpm": "pnpm",
        "sdk": "sdkman",
    }[command[0]]


def _probe(results: dict[str, str | Exception]):
    def run(command: list[str]) -> str:
        result = results[_manager_for(command)]
        if isinstance(result, Exception):
            raise result
        return result

    return run


def test_run_probe_captures_output_without_sharing_the_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="demo 1.0\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert ownership.run_probe(["brew", "list", "--versions", "demo"]) == "demo 1.0\n"
    assert calls == [
        (
            ["brew", "list", "--versions", "demo"],
            {
                "capture_output": True,
                "text": True,
                "check": True,
                "stdin": subprocess.DEVNULL,
                "timeout": 5,
            },
        )
    ]


def test_owner_uses_first_successful_declared_probe() -> None:
    owner = detect_owner(
        _tool(owner_probes=("sdkman", "brew")),
        _probe({"sdkman": "", "brew": "demo 1.2.3\n"}),
    )
    assert owner == Ownership("Homebrew", "verified", "brew lists demo")


def test_owner_does_not_guess_from_command_path() -> None:
    assert detect_owner(_tool(), _probe({})) == Ownership(None, "unknown", "no verified manager")


def test_host_setup_owner_uses_the_reviewed_setup_probe() -> None:
    commands: list[list[str]] = []
    tool = _tool(
        owner_probes=("host-setup",),
        methods=(Method(kind="host_setup", params={"setup_id": "pi"}),),
    )

    owner = detect_owner(
        tool,
        lambda command: commands.append(command) or "@earendil-works/pi-coding-agent\n",
    )

    assert owner == Ownership("pnpm", "verified", "host setup lists pi")
    assert commands == [["pnpm", "list", "--global", "--depth", "0", "--json"]]


@pytest.mark.parametrize(
    ("probe", "methods", "output", "manager", "detail"),
    [
        (
            "managed-download",
            (Method(kind="github_release", params={"member": "demo"}),),
            "demo\n",
            "managed download",
            "managed download lists demo",
        ),
        (
            "brew",
            (Method(kind="brew", params={"formula": "demo"}),),
            "demo 1.2.3\n",
            "Homebrew",
            "brew lists demo",
        ),
        (
            "apt",
            (Method(kind="apt", params={"package": "demo"}),),
            "demo\n",
            "apt",
            "apt lists demo",
        ),
        (
            "dnf",
            (Method(kind="dnf", params={"package": "demo"}),),
            "demo\n",
            "dnf",
            "dnf lists demo",
        ),
        (
            "pacman",
            (Method(kind="pacman", params={"package": "demo"}),),
            "demo\n",
            "pacman",
            "pacman lists demo",
        ),
        (
            "pnpm",
            (Method(kind="node", params={"npm_pkg": "@scope/demo"}),),
            json.dumps([{"name": "@scope/demo", "version": "1.2.3"}]),
            "pnpm",
            "pnpm lists @scope/demo",
        ),
        (
            "sdkman",
            (Method(kind="script", params={"sdk_candidate": "java"}),),
            "Using java version 21.0.1-tem\n",
            "SDKMAN",
            "sdkman lists java",
        ),
    ],
)
def test_owner_verifies_each_manager_from_its_own_output(
    probe: str,
    methods: tuple[Method, ...],
    output: str,
    manager: str,
    detail: str,
) -> None:
    assert detect_owner(
        _tool(owner_probes=(probe,), methods=methods), _probe({probe: output})
    ) == Ownership(manager, "verified", detail)


@pytest.mark.parametrize(
    "response", [FileNotFoundError(), RuntimeError("failed"), "not installed\n"]
)
def test_owner_treats_unavailable_failed_or_unparseable_probes_as_unknown(
    response: str | Exception,
) -> None:
    owner = detect_owner(_tool(owner_probes=("brew",)), _probe({"brew": response}))
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_owner_treats_injected_command_failure_as_unknown() -> None:
    owner = detect_owner(
        _tool(owner_probes=("brew",)),
        _probe({"brew": subprocess.CalledProcessError(1, ["brew", "list", "--versions", "demo"])}),
    )
    assert owner == Ownership(None, "unknown", "no verified manager")
