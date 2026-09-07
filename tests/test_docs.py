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
