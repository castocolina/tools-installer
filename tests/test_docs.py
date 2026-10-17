from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE = REPO_ROOT / ".claude" / "architecture.md"

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
    "with_sensitive_confirm",
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
    with_sensitive_confirm: confirmation is bound at a composition
    point so the shared Install protocol — and its twenty-nine fakes —
    stay unchanged.
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
    "waiting for output",
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
    always reports the unwrapped argv a user can paste back. waiting for
    output: the UI-side indicator, produced by ExecuteScreen's self-re-arming
    one-shot timer, that claims only liveness and waiting -- never that the
    child is healthy. silence generation: the token every transient carries,
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
