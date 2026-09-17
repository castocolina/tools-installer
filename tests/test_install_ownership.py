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
        immutable=False,
    )
    assert owner == Ownership("Homebrew", "verified", "brew lists demo", package="demo")


def test_owner_does_not_guess_from_command_path() -> None:
    assert detect_owner(_tool(), _probe({}), immutable=False) == Ownership(
        None, "unknown", "no verified manager"
    )


def test_host_setup_owner_uses_the_reviewed_setup_probe() -> None:
    commands: list[list[str]] = []
    tool = _tool(
        owner_probes=("host-setup",),
        methods=(Method(kind="host_setup", params={"setup_id": "pi"}),),
    )

    owner = detect_owner(
        tool,
        lambda command: commands.append(command) or "@earendil-works/pi-coding-agent\n",
        immutable=False,
    )

    assert owner == Ownership("pnpm", "verified", "host setup lists pi")
    assert commands == [["pnpm", "list", "--global", "--depth", "0", "--json"]]


@pytest.mark.parametrize(
    ("probe", "methods", "output", "manager", "detail", "package"),
    [
        (
            "managed-download",
            (Method(kind="github_release", params={"member": "demo"}),),
            "demo\n",
            "managed download",
            "managed download lists demo",
            None,
        ),
        (
            "brew",
            (Method(kind="brew", params={"formula": "demo"}),),
            "demo 1.2.3\n",
            "Homebrew",
            "brew lists demo",
            "demo",
        ),
        (
            "apt",
            (Method(kind="apt", params={"package": "demo"}),),
            "demo\n",
            "apt",
            "apt lists demo",
            "demo",
        ),
        (
            "dnf",
            (Method(kind="dnf", params={"package": "demo"}),),
            "demo\n",
            "dnf",
            "dnf lists demo",
            "demo",
        ),
        (
            "pacman",
            (Method(kind="pacman", params={"package": "demo"}),),
            "demo\n",
            "pacman",
            "pacman lists demo",
            "demo",
        ),
        (
            "pnpm",
            (Method(kind="node", params={"npm_pkg": "@scope/demo"}),),
            json.dumps([{"name": "@scope/demo", "version": "1.2.3"}]),
            "pnpm",
            "pnpm lists @scope/demo",
            "@scope/demo",
        ),
        (
            "sdkman",
            (Method(kind="script", params={"sdk_candidate": "java"}),),
            "Using java version 21.0.1-tem\n",
            "SDKMAN",
            "sdkman lists java",
            "java",
        ),
    ],
)
def test_owner_verifies_each_manager_from_its_own_output(
    probe: str,
    methods: tuple[Method, ...],
    output: str,
    manager: str,
    detail: str,
    package: str | None,
) -> None:
    """Mutable host: every declared probe answers from its own manager's
    output. The dnf/apt/pacman rows here are the counterpart to
    `test_native_package_manager_probes_stand_down_on_an_immutable_host`.
    `package` is the matched name each probe reports -- `None` only for
    `managed-download`, which never populates it (Round-3 review HIGH)."""
    assert detect_owner(
        _tool(owner_probes=(probe,), methods=methods), _probe({probe: output}), immutable=False
    ) == Ownership(manager, "verified", detail, package=package)


@pytest.mark.parametrize(
    ("probe", "method"),
    [
        ("dnf", Method(kind="dnf", params={"package": "ripgrep"})),
        ("apt", Method(kind="apt", params={"package": "ripgrep"})),
        ("pacman", Method(kind="pacman", params={"package": "ripgrep"})),
        ("rpm-ostree", Method(kind="dnf", params={"package": "ripgrep"})),
    ],
)
def test_native_probe_captures_a_declared_package_name_that_differs_from_cmd(
    probe: str, method: Method
) -> None:
    """Round-3 review HIGH, probe level: `rg`'s cmd is `rg` but its declared
    dnf/apt/pacman package is `ripgrep` -- the captured name must be the
    PACKAGE the database matched, never reconstructed from the tool's own
    cmd. `rpm-ostree` shares the `dnf` method's declared package, mirroring
    `_rpm_ostree`'s own docstring."""
    tool = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(method,),
        owner_probes=(probe,),
    )
    if probe == "rpm-ostree":
        status = json.dumps({"deployments": [{"booted": True, "requested-packages": ["ripgrep"]}]})
        owner = detect_owner(tool, _probe({"rpm-ostree": status}), immutable=True)
    else:
        owner = detect_owner(tool, _probe({probe: "ripgrep\n"}), immutable=False)
    assert owner.package == "ripgrep"
    assert owner.package != tool.cmd


@pytest.mark.parametrize(
    "response", [FileNotFoundError(), RuntimeError("failed"), "not installed\n"]
)
def test_owner_treats_unavailable_failed_or_unparseable_probes_as_unknown(
    response: str | Exception,
) -> None:
    owner = detect_owner(_tool(owner_probes=("brew",)), _probe({"brew": response}), immutable=False)
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_owner_treats_injected_command_failure_as_unknown() -> None:
    owner = detect_owner(
        _tool(owner_probes=("brew",)),
        _probe({"brew": subprocess.CalledProcessError(1, ["brew", "list", "--versions", "demo"])}),
        immutable=False,
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
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}), immutable=True)
    assert owner == Ownership("rpm-ostree", "verified", "rpm-ostree layers jq", package="jq")


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
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}), immutable=True)
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_rpm_ostree_owner_returns_none_without_a_booted_deployment() -> None:
    status = _rpm_ostree_status(
        [{"booted": False, "packages": ["jq"], "requested-packages": ["jq"]}]
    )
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}), immutable=True)
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
    owner = detect_owner(_rpm_ostree_tool(), _probe({"rpm-ostree": status}), immutable=True)
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_rpm_ostree_owner_never_runs_the_probe_without_a_declared_dnf_package() -> None:
    calls: list[list[str]] = []
    tool = _tool(
        owner_probes=("rpm-ostree",),
        methods=(Method(kind="brew", params={"formula": "jq"}),),
    )
    owner = detect_owner(tool, lambda command: calls.append(command) or "{}", immutable=True)
    assert owner == Ownership(None, "unknown", "no verified manager")
    assert calls == []


def test_rpm_ostree_owner_treats_a_missing_binary_as_unknown() -> None:
    owner = detect_owner(
        _rpm_ostree_tool(), _probe({"rpm-ostree": FileNotFoundError()}), immutable=True
    )
    assert owner == Ownership(None, "unknown", "no verified manager")


def _recording_probe(results: dict[str, str | Exception], calls: list[list[str]]):
    inner = _probe(results)

    def run(command: list[str]) -> str:
        calls.append(command)
        return inner(command)

    return run


def _base_image_status(package: str) -> str:
    """A booted ostree deployment that SHIPS `package` in its base image.

    Present in `packages`, absent from `requested-packages`: the user never
    layered it, so `_rpm_ostree` has no explicit-layering evidence to report.
    This is what `git`/`jq`/`zsh`/`podman` look like on Bazzite or Silverblue.
    """
    return _rpm_ostree_status([{"booted": True, "packages": [package], "requested-packages": []}])


def test_dnf_probe_stands_down_for_a_base_image_package_on_an_immutable_host() -> None:
    """CR-02: the booted deployment's rpmdb answers `rpm -q` for every package
    in the base image, so `_dnf` used to claim `git`/`jq`/`zsh`/`podman` on an
    ostree host and tell the user to "update it through dnf" -- a command that
    does not manage that package there. `resolve._applies` already refuses to
    INSTALL through dnf on such a host for the same reason; attribution now
    agrees. Only `_rpm_ostree`'s explicit-layering evidence counts, and a
    base-image package is honestly unknown rather than wrongly dnf's."""
    calls: list[list[str]] = []
    tool = _tool(
        owner_probes=("rpm-ostree", "dnf"),
        methods=(Method(kind="dnf", params={"package": "jq"}),),
    )
    owner = detect_owner(
        tool,
        _recording_probe({"rpm-ostree": _base_image_status("jq"), "dnf": "jq\n"}, calls),
        immutable=True,
    )
    assert owner == Ownership(None, "unknown", "no verified manager")
    # rpm-ostree was asked and answered "not layered"; `rpm -q` was never run.
    assert [command[0] for command in calls] == ["rpm-ostree"]


def test_dnf_probe_still_answers_for_the_same_package_on_a_mutable_host() -> None:
    """The gate is about the host, not the package: on a normal Fedora box the
    identical rpmdb evidence is the right answer, and dnf really is the manager
    of record."""
    calls: list[list[str]] = []
    tool = _tool(
        owner_probes=("rpm-ostree", "dnf"),
        methods=(Method(kind="dnf", params={"package": "jq"}),),
    )
    owner = detect_owner(
        tool,
        _recording_probe({"rpm-ostree": FileNotFoundError(), "dnf": "jq\n"}, calls),
        immutable=False,
    )
    assert owner == Ownership("dnf", "verified", "dnf lists jq", package="jq")
    assert [command[0] for command in calls] == ["rpm-ostree", "rpm"]


@pytest.mark.parametrize(
    ("probe_name", "method"),
    [
        ("dnf", Method(kind="dnf", params={"package": "demo"})),
        ("apt", Method(kind="apt", params={"package": "demo"})),
        ("pacman", Method(kind="pacman", params={"package": "demo"})),
    ],
)
def test_native_package_manager_probes_stand_down_on_an_immutable_host(
    probe_name: str, method: Method
) -> None:
    """The gate covers all three native managers, mirroring `resolve._applies`,
    which returns False for dnf/apt/pacman alike on an immutable host -- not
    just for dnf. None of them is the manager of record on an atomic system."""
    calls: list[list[str]] = []
    tool = _tool(owner_probes=(probe_name,), methods=(method,))
    owner = detect_owner(tool, _recording_probe({probe_name: "demo\n"}, calls), immutable=True)
    assert owner == Ownership(None, "unknown", "no verified manager")
    assert calls == []


@pytest.mark.parametrize(
    ("manager", "method", "argv", "owning_output"),
    [
        (
            "dnf",
            Method(kind="dnf", params={"package": "demo"}),
            ["rpm", "-qf", "--qf", "%{NAME}\\n", "/usr/bin/demo"],
            "demo\n",
        ),
        (
            "rpm-ostree",
            Method(kind="dnf", params={"package": "demo"}),
            ["rpm", "-qf", "--qf", "%{NAME}\\n", "/usr/bin/demo"],
            "demo\n",
        ),
        (
            "apt",
            Method(kind="apt", params={"package": "demo"}),
            ["dpkg-query", "-S", "/usr/bin/demo"],
            "demo: /usr/bin/demo\n",
        ),
        (
            "pacman",
            Method(kind="pacman", params={"package": "demo"}),
            ["pacman", "-Qoq", "/usr/bin/demo"],
            "demo\n",
        ),
    ],
)
def test_package_owns_path_uses_each_managers_own_file_query(
    manager: str, method: Method, argv: list[str], owning_output: str
) -> None:
    """CR-01: each native manager answers "which package owns this file" in
    its own dialect. `rpm-ostree` shares rpm's, because a layered or
    base-image RPM lives in the same rpm database."""
    calls: list[list[str]] = []
    tool = _tool(methods=(method,))
    # Keyed by the probe binary's own manager (`rpm` answers for both dnf and
    # rpm-ostree), not by the owner name being confirmed.
    probe = _recording_probe({_manager_for(argv): owning_output}, calls)
    assert ownership.package_owns_path(tool, manager, "/usr/bin/demo", probe)
    assert calls == [argv]


@pytest.mark.parametrize(
    ("manager", "method", "denying_output"),
    [
        ("dnf", Method(kind="dnf", params={"package": "demo"}), "other-package\n"),
        ("apt", Method(kind="apt", params={"package": "demo"}), "other-package: /usr/bin/demo\n"),
        ("pacman", Method(kind="pacman", params={"package": "demo"}), "other-package\n"),
    ],
)
def test_package_owns_path_rejects_a_file_owned_by_a_different_package(
    manager: str, method: Method, denying_output: str
) -> None:
    """A successful query naming SOMEONE ELSE is a denial, not a claim -- the
    shadowing case where the live binary comes from another package."""
    tool = _tool(methods=(method,))
    assert not ownership.package_owns_path(
        tool, manager, "/usr/bin/demo", _probe({manager: denying_output})
    )


def test_package_owns_path_fails_closed_when_the_query_cannot_run() -> None:
    """`rpm -qf` exits non-zero for a file no package owns -- a hand-built
    binary earlier in PATH. Unanswerable is not confirmed."""
    tool = _tool(methods=(Method(kind="dnf", params={"package": "demo"}),))
    assert not ownership.package_owns_path(
        tool, "dnf", "/home/user/bin/demo", _probe({"dnf": FileNotFoundError()})
    )


def test_package_owns_path_rejects_a_manager_with_no_declared_file_query() -> None:
    """Only the four native managers have a file query here; anything else
    (Homebrew, pnpm, SDKMAN) reaches ownership through its own inventory, and
    an unrecognized name must never confirm by default."""
    calls: list[list[str]] = []
    tool = _tool(methods=(Method(kind="brew", params={"formula": "demo"}),))
    assert not ownership.package_owns_path(
        tool, "Homebrew", "/usr/bin/demo", _recording_probe({}, calls)
    )
    assert calls == []


# -- 15.4-01/D-01: path_owner_package -- the INVERSE query, no expected name.
# The tracer proving case is git: it declares package="git" while the rpm
# database's real answer is "git-core" (15.4-RESEARCH.md Pitfall 1). --------


@pytest.mark.parametrize(
    ("os_family", "argv", "output", "expected"),
    [
        ("fedora", ["rpm", "-qf", "--qf", "%{NAME}\\n", "/usr/bin/git"], "git-core\n", "git-core"),
        ("debian", ["dpkg-query", "-S", "/usr/bin/git"], "git: /usr/bin/git\n", "git"),
        ("arch", ["pacman", "-Qoq", "/usr/bin/git"], "git\n", "git"),
    ],
)
def test_path_owner_package_uses_each_dialects_own_query(
    os_family: str, argv: list[str], output: str, expected: str
) -> None:
    calls: list[list[str]] = []

    def probe(command: list[str]) -> str:
        calls.append(command)
        return output

    assert ownership.path_owner_package(os_family, "/usr/bin/git", probe) == expected
    assert calls == [argv]


def test_path_owner_package_issues_no_query_on_macos() -> None:
    """There is no OS package database to ask on macOS -- the probe is never
    even consulted."""
    calls: list[list[str]] = []
    result = ownership.path_owner_package("macos", "/usr/bin/git", _recording_probe({}, calls))
    assert result is None
    assert calls == []


def test_path_owner_package_returns_none_when_the_query_raises() -> None:
    assert (
        ownership.path_owner_package("fedora", "/usr/bin/git", _probe({"dnf": FileNotFoundError()}))
        is None
    )


def test_path_owner_package_returns_none_for_zero_reported_names() -> None:
    assert ownership.path_owner_package("fedora", "/usr/bin/git", lambda _cmd: "") is None


def test_path_owner_package_returns_none_for_two_or_more_reported_names() -> None:
    """rpm -qf can report more than one owning package; positive confirmation
    must be singular, not merely non-empty."""
    assert (
        ownership.path_owner_package("fedora", "/usr/bin/git", lambda _cmd: "git-core\nother\n")
        is None
    )


@pytest.mark.parametrize("rogue_name", ["-rf /", "git;rm", "../escape", "git core", ""])
def test_path_owner_package_rejects_a_guard_failing_name(rogue_name: str) -> None:
    """Probe stdout is untrusted (module docstring): a planted rpm could
    report a name carrying control characters, path separators, or shell
    metacharacters, and the guard must refuse all of them."""

    def probe(_command: list[str]) -> str:
        return f"{rogue_name}\n"

    assert ownership.path_owner_package("fedora", "/usr/bin/git", probe) is None


def test_package_owns_path_rejects_a_tool_declaring_no_package_for_that_manager() -> None:
    """No declared package name means nothing to confirm, and no subprocess."""
    calls: list[list[str]] = []
    tool = _tool(methods=(Method(kind="brew", params={"formula": "demo"}),))
    assert not ownership.package_owns_path(
        tool, "dnf", "/usr/bin/demo", _recording_probe({}, calls)
    )
    assert calls == []


def _recursion_bomb_json(depth: int) -> str:
    """A syntactically legal JSON document nested past the recursion limit.

    Probe binaries are looked up through the user's `PATH`, and this installer
    prepends a managed bin dir to that `PATH` by design, so a planted or
    corrupted `rpm-ostree`/`pnpm` can put arbitrary bytes on stdout. Deep
    nesting is the cheapest way to turn that stdout into an exception that is
    neither `TypeError` nor `ValueError`.
    """
    return "[" * depth + "]" * depth


def test_rpm_ostree_owner_fails_closed_on_a_recursion_bomb_from_the_probe() -> None:
    """WR-05: `json.loads` raises `RecursionError` on deeply nested input,
    which is not a `ValueError`. An uncaught one would propagate out of the
    catalog refresh worker instead of failing closed the way every other
    malformed-probe-output case in this module already does."""
    owner = detect_owner(
        _rpm_ostree_tool(), _probe({"rpm-ostree": _recursion_bomb_json(20_000)}), immutable=True
    )
    assert owner == Ownership(None, "unknown", "no verified manager")


def test_pnpm_owner_fails_closed_on_a_recursion_bomb_from_the_probe() -> None:
    """WR-05, the other half: `_pnpm_packages` walks the parsed document
    recursively, so input shallow enough for `json.loads` can still exhaust
    the interpreter's stack inside the walk. The guard has to cover the parse
    AND the walk, not just the parse."""
    tool = _tool(
        owner_probes=("pnpm",),
        methods=(Method(kind="node", params={"npm_pkg": "demo"}),),
    )
    owner = detect_owner(tool, _probe({"pnpm": _recursion_bomb_json(5_000)}), immutable=False)
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
