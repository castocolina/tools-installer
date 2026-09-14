from pathlib import Path

ARCHITECTURE = Path(__file__).resolve().parent.parent / ".claude" / "architecture.md"

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
