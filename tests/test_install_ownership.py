import json
import subprocess

import pytest

import installer.install_ownership as ownership
from installer.install_ownership import Ownership, detect_owner
from installer.model import OWNER_PROBES, Method, Tool


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
        "rpm-ostree": "rpm-ostree",
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


def _rpm_ostree_status(deployments: list[dict[str, object]]) -> str:
    return json.dumps({"deployments": deployments})


def _rpm_ostree_tool(package: str = "jq") -> Tool:
    return _tool(
        owner_probes=("rpm-ostree",),
        methods=(Method(kind="dnf", params={"package": package}),),
    )


def test_rpm_ostree_owner_verifies_the_booted_deployments_layered_package() -> None:
    status = _rpm_ostree_status(
        [
            {
                "booted": False,
                "packages": ["podman-compose"],
                "requested-packages": ["podman-compose"],
            },
            {
                "booted": True,
                "packages": ["jq", "podman-compose"],
                "requested-packages": ["jq", "podman-compose"],
            },
        ]
    )
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}))
    assert owner == Ownership("rpm-ostree", "verified", "rpm-ostree layers jq")


def test_rpm_ostree_owner_does_not_credit_a_non_booted_deployments_layered_package() -> None:
    status = _rpm_ostree_status(
        [
            {"booted": False, "packages": ["jq"], "requested-packages": ["jq"]},
            {
                "booted": True,
                "packages": ["podman-compose"],
                "requested-packages": ["podman-compose"],
            },
        ]
    )
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}))
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_rpm_ostree_owner_returns_none_without_a_booted_deployment() -> None:
    status = _rpm_ostree_status(
        [{"booted": False, "packages": ["jq"], "requested-packages": ["jq"]}]
    )
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}))
    assert owner == Ownership(None, "unknown", "no verified manager")


@pytest.mark.parametrize(
    "status",
    [
        "not json",
        json.dumps({"no-deployments-key": []}),
        json.dumps({"deployments": [{"booted": True}]}),
        json.dumps({"deployments": [{"booted": True, "requested-packages": "jq"}]}),
    ],
    ids=[
        "malformed-json",
        "missing-deployments-key",
        "missing-requested-packages",
        "requested-packages-not-a-list",
    ],
)
def test_rpm_ostree_owner_fails_closed_on_malformed_input(status: str) -> None:
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}))
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_rpm_ostree_owner_never_runs_the_probe_without_a_declared_dnf_package() -> None:
    calls: list[list[str]] = []
    tool = _tool(
        owner_probes=("rpm-ostree",),
        methods=(Method(kind="brew", params={"formula": "jq"}),),
    )
    owner = detect_owner(tool, lambda command: calls.append(command) or "{}")
    assert owner == Ownership(None, "unknown", "no verified manager")
    assert calls == []


def test_rpm_ostree_owner_treats_a_missing_binary_as_unknown() -> None:
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": FileNotFoundError()}))
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_owner_probes_closed_set_and_probe_registry_are_the_same_set() -> None:
    # Addresses review concern (cycle 2, L247@ca67acb): a one-way subset check
    # in either direction alone is not enough. `set(_PROBES) <= set(OWNER_PROBES)`
    # would miss a probe implemented but never made declarable (inert, not
    # dangerous). The direction that actually bites is the reverse:
    # `detect_owner` does `_PROBES[name](tool, probe)` with no `.get` and no
    # default, so a name present only in `OWNER_PROBES` passes registry
    # validation at load time and then raises `KeyError` on the refresh pass
    # that calls it. Assert both directions as separate statements so a
    # failure names which side is short.
    declarable = set(OWNER_PROBES)
    # Deliberate private-member access: this test's whole purpose is pinning
    # the internal probe registry against the public closed set, so it must
    # reach _PROBES directly rather than through any public wrapper.
    implemented = set(ownership._PROBES)  # pyright: ignore[reportPrivateUsage]
    assert declarable <= implemented, sorted(declarable - implemented)
    assert implemented <= declarable, sorted(implemented - declarable)
