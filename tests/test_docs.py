import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE = REPO_ROOT / ".claude" / "architecture.md"
TOOL_ONBOARDING_SKILL = REPO_ROOT / ".claude" / "skills" / "tool-onboarding" / "SKILL.md"

_TRUNCATION_BANNER_FRAGMENTS = (
    "[Showing lines",
    "Use offset=",
)


def _rule_document_paths() -> list[Path]:
    paths = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "README.md",
        REPO_ROOT / ".claude" / "architecture.md",
        REPO_ROOT / ".claude" / "dev-environment.md",
        REPO_ROOT / ".claude" / "git-workflow.md",
        REPO_ROOT / ".claude" / "python-tooling.md",
        REPO_ROOT / ".claude" / "testing.md",
        REPO_ROOT / ".claude" / "skills" / "tool-onboarding" / "SKILL.md",
    ]
    paths.extend(sorted(REPO_ROOT.glob("docs/**/*.md")))
    return paths


_REQUIRED = (
    "installer/ownership.py",
    "install-preference ladder",
    "never provenance",
    "plan_uninstall",
    "MUTATION_GRADE",
    "unknown_reason",
    "update_download",
    "atomic_write_text",
    "invalidate",
)


def test_architecture_records_phase_12_mechanisms() -> None:
    """The comment is the mechanism; the test keeps it from rotting away unnoticed.

    Each substring anchors a paragraph whose deletion would lose a finding
    Phase 12's two cross-AI review cycles produced.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


_PHASE_13_REQUIRED = (
    "installer/execute_screen.py",
    "StreamingRunner",
    "attributed_install",
    "should_continue",
    "installer/settings.py",
    "ModalScreen",
    "push_screen_wait",
    "feat/install-experience",
    "nothing sources",
)


def test_architecture_records_phase_13_mechanisms() -> None:
    """The comment is the mechanism; the test keeps it from rotting away unnoticed.

    Each substring anchors a paragraph whose deletion would lose a finding
    Phase 13 produced. execute_screen.py / feat/install-experience: the
    screen is an IO adapter, not a second decision layer, because the
    abandoned branch split that responsibility. ModalScreen: not a
    registered view, or the navigable-stack invariant breaks.
    StreamingRunner / attributed_install: the only incremental Runner, and
    attribution is structural. push_screen_wait: the checksum-mismatch
    seam is a documented exception to rule 2, not a violation of it.
    should_continue: weak cancel, never during a tool. settings.py: link
    mode lives here, asked at most once, no new view. nothing sources:
    every consumer re-reads the mode, or a ban after a split-mode switch
    writes aliases into a file nothing sources.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_13_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


_PHASE_14_REQUIRED = (
    "resolve_dependencies",
    "cannot update",
    "installer/post_install.py",
    "set_login_shell",
    "Platform.immutable",
    "4159",
    "binds the sensitive-action confirmation",
)


def test_architecture_records_phase_14_mechanisms() -> None:
    """The comment is the mechanism; the test keeps it from rotting away unnoticed.

    Each substring anchors a paragraph whose deletion would lose a finding
    Phase 14 produced. resolve_dependencies: the install/update split is
    made beside the resolver, never inside it, because deps.py has no
    version or ownership state. cannot update: a refused batch update
    uses the same sentence the per-row u keybind already produces.
    installer/post_install.py / set_login_shell: the plural action list
    is a sibling of the singular hook, not an extension of it, and the
    one action has no execution seam. Platform.immutable / 4159: the
    login-shell action is hard-blocked on atomic hosts because
    ublue-os/bazzite#4159 was closed with no root-cause analysis.
    binds the sensitive-action confirmation inside execute_plan's one
    _with_force wrapper, while SensitiveInstall carries the live seam.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_14_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


_PHASE_15_2_REQUIRED = (
    "PYTHONUNBUFFERED",
    "stdbuf -oL",
    "LD_PRELOAD",
    "retried unwrapped",
    "unwrapped argv",
    "still running",
    "silence generation",
    "per in-flight tool",
)


def test_architecture_records_phase_15_2_mechanisms() -> None:
    """The comment is the mechanism; the test keeps it from rotting away unnoticed.

    Each substring anchors a paragraph whose deletion would lose a finding
    Phase 15.2's two cross-AI review cycles produced. PYTHONUNBUFFERED: the
    one rung that needs no availability check, because it is Python-specific
    and a no-op elsewhere. stdbuf -oL: opt-in, resolved once, silently
    skipped when absent, and carries no manager name -- the rung exists for
    pnpm/SDKMAN, never a branch inside it. LD_PRELOAD: why stdbuf reaches a
    curl | sh installer's own grandchildren and is a harmless no-op across
    sudo's setuid boundary. retried unwrapped / unwrapped argv: a launch that
    fails on the wrapped argv is retried unwrapped exactly once, safe only
    because Popen raised before the target command started, and CommandError
    always reports the unwrapped argv a user can paste back. still running:
    the UI-side indicator and its timestamped heartbeat lines, produced by
    ExecuteScreen's self-re-arming silence tick, that claim only liveness and
    waiting -- never that the child is healthy. silence generation: the token
    every transient carries,
    without which a stale reassurance could be rendered after the output it
    was waiting for. per in-flight tool: the indicator is cleared by THE
    tool that finished, matched by id, and established only by the first
    non-transient log line for that tool -- never a global flag.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_15_2_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


def test_rule_documents_carry_no_truncation_banner() -> None:
    """Agent edit tools can paste a read-tool banner into rule documents.

    Each fragment is copied from 18-REVIEW CR-01; a hit means doctrine was
    truncated and must be restored before merge.
    """
    for path in _rule_document_paths():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT)
        for fragment in _TRUNCATION_BANNER_FRAGMENTS:
            assert fragment not in text, f"{rel}: truncation banner fragment {fragment!r}"
        assert text.endswith("\n"), f"{rel}: missing trailing newline"


_PHASE_15_8_REQUIRED = (
    "a second text-level scan covers",
    "PNPM_HOME",
    "~/.shellrc.tools-installer.old",
    "this project does NOT parse shell",
    "EVERY write in",
    "reasoned residual, never a completed proof",
    "such file exists on this host.",
)

_PHASE_18_AUTHORING = (
    "verified = YYYY-MM-DD",
    "METHOD_PARAMS",
    "smoke_argv",
)


_PHASE_20_REQUIRED = (
    "build_plan",
    "PlanRow",
    "execute_plan",
    "RowOutcome",
    "WORDS",
    "exit_code",
    "retained",
    "ran_anything",
    "Resolution.closure",
    "_await_state",
    "single flight",
    "Summary — ",
    "never escalated",
    "update_refusal",
    "(r: reinstall)",
)


def test_architecture_records_phase_20_mechanisms() -> None:
    """Keep the Phase 20 plan, engine and vocabulary doctrine load-bearing."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_20_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


_PHASE_21_REQUIRED = (
    "## Phase 21: one screen family",
    "state_refreshed",
    "clear_transient",
    "request_refresh",
    "full-catalog-refresh",
    "await_publication",
    "mark_pending",
    "uninstall_group",
    "uninstall-removal",
    "_exit_after_removal",
    "MutationLock",
    "MutationHolder",
    "{Holder} is running; wait for it to finish. Navigation still works.",
    "record_evidence",
    "test_the_replaced_forks_are_gone",
)


def test_architecture_records_phase_21_mechanisms() -> None:
    """Keep the Phase 21 screen-family doctrine load-bearing."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_21_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


_PHASE_19_REQUIRED = (
    "ToolState",
    "state_of",
    "tool_health",
    "receipts.py",
    "artifact_paths",
    "plan_removal",
    "remove_proven",
    "native_index",
    "ConfigStep",
    "uv tool dir",
    "write=False",
    "adopted: the file matches the release checksum",
    "live_platform",
    "PROJECT_HOOK_CONFIGS",
    "single flight",
    "Contents/Info.plist",
    "quarantine sibling",
    "resolve inside the directory",
    "interrupted removal",
)


def test_architecture_records_phase_19_mechanisms() -> None:
    """The comment is the mechanism; the test keeps it from rotting away unnoticed.

    Each substring anchors the Phase 19 section: the one seq-gated ToolState
    and state_of, tool_health, receipts.py and its removal proof, the batched
    native_index, the live platform, and the misconfiguration evidence.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_19_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"


def test_architecture_records_phase_15_8_mechanisms() -> None:
    """The comment is the mechanism; the test keeps it from rotting away unnoticed.

    Each substring anchors a paragraph whose deletion would lose Phase 15.8
    doctrine (shell PATH scan, PNPM_HOME, ~/.shellrc consolidation). The
    Phase 18 authoring phrases must stay present after any restoration.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _PHASE_15_8_REQUIRED:
        assert phrase in text, f"missing load-bearing phrase: {phrase}"
    for phrase in _PHASE_18_AUTHORING:
        assert phrase in text, f"missing Phase 18 authoring phrase: {phrase}"


_INSTALL_TUNING_RULE_PHRASES = (
    "install-time tuning",
    "no runtime question",
    "reverted with the tool",
    "outside any install",
    "never becomes a Policies knob by default",
)


def test_tool_onboarding_skill_states_the_install_tuning_rule() -> None:
    """TUNE-04: an accepted customization is install tuning, never a Policies knob by default.

    The phrases anchor the section 7 paragraph and the Common Mistakes bullet.
    skill_pack and skill_lifecycle are the retired 23.1 vocabulary and must
    not come back. Every line that names Policies stays plain ASCII.
    """
    text = TOOL_ONBOARDING_SKILL.read_text(encoding="utf-8")
    for phrase in _INSTALL_TUNING_RULE_PHRASES:
        assert phrase in text, f"missing install-tuning rule phrase: {phrase}"
    assert "skill_pack" not in text, "retired skill_pack vocabulary is back"
    assert "skill_lifecycle" not in text, "retired skill_lifecycle vocabulary is back"
    for line in text.splitlines():
        if "Policies" in line:
            assert line.isascii(), f"non-ASCII line naming Policies: {line!r}"


def _skill_section(number: str) -> str:
    """The text of one numbered `### N.` step of the onboarding skill, heading included."""
    text = TOOL_ONBOARDING_SKILL.read_text(encoding="utf-8")
    start = re.search(rf"^### {re.escape(number)}\. ", text, re.MULTILINE)
    assert start, f"missing skill step {number}"
    nxt = re.search(r"^### \d+b?\. ", text[start.end() :], re.MULTILINE)
    return text[start.start() : start.end() + nxt.start()] if nxt else text[start.start() :]


def test_tool_onboarding_skill_names_every_lifecycle_param() -> None:
    """ONB-03: step 4b gives one TOML example line for each Phase 22 lifecycle param."""
    text = TOOL_ONBOARDING_SKILL.read_text(encoding="utf-8")
    section = _skill_section("4b")
    every = ("paths", "remove", "update", "writable_prefix", "config_paths", "cargo_distrobox")
    for param in every:
        assert param in text, f"skill never names {param}"
    for param in ("paths", "remove", "update", "writable_prefix", "config_paths"):
        example = re.search(rf"^\s*{param} = ", section, re.MULTILINE)
        assert example, f"4b has no example for {param}"


_POLICIES_RULE_SENTENCES = (
    "A Policies row is only for something outside any install",
    "never becomes a Policies knob by default",
)


def test_tool_onboarding_skill_keeps_the_policies_rule_verbatim() -> None:
    """D-24: 23.2's two rule sentences survive every skill edit, character for character."""
    text = TOOL_ONBOARDING_SKILL.read_text(encoding="utf-8")
    for sentence in _POLICIES_RULE_SENTENCES:
        assert sentence in text, f"rule sentence dropped: {sentence}"


def test_tool_onboarding_skill_has_no_skill_pack_text() -> None:
    """D-24: skill packs left the catalog in 23.1; the skill must not mention them."""
    text = TOOL_ONBOARDING_SKILL.read_text(encoding="utf-8")
    assert not re.search(r"skill.pack|skill_lifecycle", text, re.IGNORECASE)


def test_tool_onboarding_skill_terminal_bullet() -> None:
    """D-24: step 7 sends a terminal's shell to the zsh sync, the rest to install tuning."""
    section = _skill_section("7")
    assert "zsh terminal sync" in section
    assert "install tuning" in section
    assert "never a Policies row" in section


def test_tool_onboarding_skill_has_a_cargo_distrobox_example() -> None:
    """R2-07: step 4b holds a parseable cargo_distrobox method with the four params' shapes."""
    section = _skill_section("4b")
    blocks = re.findall(r"```toml\n(.*?)```", section, re.DOTALL)
    parsed = [tomllib.loads(block) for block in blocks]
    methods = [
        method
        for doc in parsed
        for tool in doc.get("tool", [])
        for method in tool.get("method", [])
        if method.get("kind") == "cargo_distrobox"
    ]
    assert methods, "4b has no fenced toml block with kind = cargo_distrobox"
    method = methods[0]
    assert re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", method["repo"])
    assert re.fullmatch(r"[a-z0-9.-]+\.[a-z]+/\S+:\S+", method["image"])
    assert method["packages"] and all(isinstance(p, str) for p in method["packages"])
    assert method["artifacts"]
    assert all(set(a) == {"box", "host"} for a in method["artifacts"])


def test_tool_onboarding_skill_has_no_pre_phase_22_removal_text() -> None:
    """R2-08: removal is planned by receipt now; the pre-Phase-22 caveats must be gone."""
    text = TOOL_ONBOARDING_SKILL.read_text(encoding="utf-8")
    assert "removal-manifest" not in text
    assert "download and app kinds only" not in text
    assert "removal_plan" in _skill_section("8")


_INSTALL_TUNING_ARCHITECTURE_PHRASES = (
    "install tuning",
    "set_omz_plugins",
    "apply_agent_tuning",
    "outside any install",
    "uninstall._omz_policy",
)


def test_architecture_records_the_install_tuning_rule() -> None:
    """D-19, D-09, D-12: install tuning is the rule; omz_plugins_policy is no Policies row.

    The phrases anchor the tree branch, the sentence after it and the rewritten
    Oh-My-Zsh paragraph. The old sentence that called the plugins a Policy row
    must be gone, so the paragraph cannot quietly keep the retired wiring.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in _INSTALL_TUNING_ARCHITECTURE_PHRASES:
        assert phrase in text, f"missing install-tuning phrase: {phrase}"
    retired = "a `Policy` produced by `installer/policy.py::omz_plugins_policy`"
    assert retired not in text, "the Oh-My-Zsh paragraph still calls the plugins a Policy row"
