import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE = REPO_ROOT / ".claude" / "architecture.md"
TOOL_ONBOARDING_SKILL = REPO_ROOT / ".claude" / "skills" / "tool-onboarding" / "SKILL.md"
CATALOG_AUDIT_SKILL = REPO_ROOT / ".claude" / "skills" / "catalog-audit" / "SKILL.md"

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
        TOOL_ONBOARDING_SKILL,
        CATALOG_AUDIT_SKILL,
        CATALOG_AUDIT_SKILL.parent / "references" / "report-template.md",
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
    every consumer re-reads the mode, or a tweak enabled after a split-mode
    switch writes its source line into a file nothing sources.
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


README = REPO_ROOT / "README.md"
TROUBLESHOOTING = REPO_ROOT / "docs" / "TROUBLESHOOTING.md"
LINK_CHECKED_DOCS: tuple[Path, ...] = (README, TROUBLESHOOTING)


def _outside_fences(text: str) -> str:
    """The text with fenced code blocks dropped, so a shell comment is never read as a heading."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            kept.append(line)
    return "\n".join(kept)


def _slug(heading: str) -> str:
    """The GitHub anchor slug of one heading: lowercase, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _headings(text: str) -> set[str]:
    """The anchor slugs of every heading in a document's prose (fences excluded)."""
    found = re.finditer(r"^#{1,6}\s+(.+?)\s*$", _outside_fences(text), re.MULTILINE)
    return {_slug(match.group(1)) for match in found}


def link_targets(doc: Path) -> list[str]:
    """Every non-external link target in doc's prose, exactly as written.

    This is the parser the link test uses; the docs-only drift test reuses it so a new
    link and its runtime-resolved target are checked by the same code.
    """
    text = _outside_fences(doc.read_text(encoding="utf-8"))
    targets: list[str] = []
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
            continue  # an external scheme such as https: or mailto:
        targets.append(target)
    return targets


def _broken_links(doc: Path) -> list[str]:
    """Each relative link or anchor in doc that does not resolve, as written.

    A bare `#anchor` must match a heading of doc itself. A relative target resolves
    from doc's own directory, never the repo root. A `#fragment` on an existing `.md`
    target must match a heading of that target document.
    """
    text = _outside_fences(doc.read_text(encoding="utf-8"))
    broken: list[str] = []
    for target in link_targets(doc):
        path_part, _, fragment = target.partition("#")
        if not path_part:
            if fragment not in _headings(text):
                broken.append(target)
            continue
        dest = doc.parent / path_part
        if not dest.exists() or _missing_fragment(dest, fragment):
            broken.append(target)
    return broken


def _missing_fragment(dest: Path, fragment: str) -> bool:
    """True when a fragment names no heading of an existing Markdown target."""
    if not fragment or dest.suffix != ".md":
        return False
    return fragment not in _headings(dest.read_text(encoding="utf-8"))


def test_readme_and_troubleshooting_links_resolve() -> None:
    """Every anchor and relative link in the two user documents resolves (T-24.4-21)."""
    for doc in LINK_CHECKED_DOCS:
        assert _broken_links(doc) == [], f"{doc.relative_to(REPO_ROOT)}: broken links"


def test_link_checker_resolves_links_from_the_document_dir(tmp_path: Path) -> None:
    """A link in docs/ resolves against docs/, so a root-only file is broken there."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "sibling.md").write_text("# Sibling\n", encoding="utf-8")
    (tmp_path / "root-only.md").write_text("# Root only\n", encoding="utf-8")
    guide = docs / "guide.md"
    guide.write_text("[a](sibling.md) [b](root-only.md)\n", encoding="utf-8")
    assert _broken_links(guide) == ["root-only.md"]


def test_link_checker_checks_cross_document_fragments(tmp_path: Path) -> None:
    """A fragment on an existing target must match one of that target's headings."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "sibling.md").write_text("## Present heading\n", encoding="utf-8")
    guide = docs / "guide.md"
    guide.write_text(
        "[ok](sibling.md#present-heading) [bad](sibling.md#missing-section)\n",
        encoding="utf-8",
    )
    assert _broken_links(guide) == ["sibling.md#missing-section"]


_LADDER_TERMS = (
    "Homebrew",
    "bun",
    "pnpm",
    "`.sh` installer",
    "GitHub release",
    "Native package manager",
)
_MOVE_TO_BUN_TERMS = (
    "without Homebrew",
    "Uninstall view",
    "install it again",
    "receipt",
    "removal command",
    "knows the manager and the package",
    "no command",
    "repair note",
)
_BUN_OVERCLAIMS = ("run without node", "blocks every")


def _install_decision_section(text: str) -> str:
    """The `## How installs are decided` section: its heading up to the next level-2 heading."""
    start = text.index("## How installs are decided")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def _first_position(text: str, term: str) -> int:
    """Index of the first whole-word mention of term, or -1 when the text never names it."""
    match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)
    return match.start() if match else -1


def test_readme_ladder_names_brew_then_bun_then_pnpm() -> None:
    """PRIO-01, PRIO-07 (tracer): the README ladder names brew, bun, pnpm, then the rest."""
    section = _install_decision_section(README.read_text(encoding="utf-8"))
    positions = [_first_position(section, term) for term in _LADDER_TERMS]
    found = dict(zip(_LADDER_TERMS, positions, strict=True))
    missing = [term for term, position in found.items() if position < 0]
    assert not missing, f"install-decision section never names: {missing}"
    assert positions == sorted(positions), f"ladder not in rank order: {found}"


def test_readme_has_no_homebrew_last_resort_line() -> None:
    """PRIO-07: no README line still calls Homebrew a last resort."""
    for line in README.read_text(encoding="utf-8").splitlines():
        if "Homebrew" in line and "last resort" in line:
            raise AssertionError(f"Homebrew called a last resort: {line!r}")


def test_readme_states_the_no_homebrew_case_and_the_move_to_bun() -> None:
    """PRIO-05 (R1-09, R2-14, R3-05): the no-Homebrew case and the move to bun are both stated."""
    section = _install_decision_section(README.read_text(encoding="utf-8"))
    for term in _MOVE_TO_BUN_TERMS:
        assert term in section, f"install-decision section lacks: {term!r}"


def _rank_passage(text: str) -> str:
    """The Phase 12 paragraph that describes the `_RANK` install-preference ladder."""
    start = text.index("`installer/resolve.py::resolve_methods` returns")
    return text[start : text.index("\n\n", start)]


def test_architecture_rank_passage_names_brew_first() -> None:
    """PRIO-07 (R1-26 family): the `_RANK` passage names brew, then bun, then pnpm."""
    passage = _rank_passage(ARCHITECTURE.read_text(encoding="utf-8"))
    assert passage.index("brew") < passage.index("bun") < passage.index("pnpm"), passage
    assert "install-preference ladder" in passage
    assert "never provenance" in passage
    assert "rank 40" not in passage


def test_onboarding_skill_lists_the_bun_kind() -> None:
    """D-22: the onboarding skill names bun in its method list (step 4) and removal table (4b)."""
    assert "`bun`" in _skill_section("4")
    assert "`bun`" in _skill_section("4b")


def test_architecture_names_no_stale_pi_host_setup_example() -> None:
    """R1-26: pi is no longer the host_setup example; the tier note names the mmdc -> bun edge."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert "Worked example: pi." not in text
    assert "`mmdc` -> `bun`" in text


def test_docs_make_no_overclaim_about_bun() -> None:
    """PRIO-07: bun-installed CLIs are said to run under node; no doc claims otherwise."""
    for path in [README, ARCHITECTURE]:
        text = path.read_text(encoding="utf-8").lower()
        rel = path.relative_to(REPO_ROOT)
        assert "run under node" in text, f"{rel}: never says bun-installed CLIs run under node"
        for claim in _BUN_OVERCLAIMS:
            assert claim not in text, f"{rel}: overclaims bun with {claim!r}"


DEV_ENVIRONMENT = REPO_ROOT / ".claude" / "dev-environment.md"
GIT_WORKFLOW = REPO_ROOT / ".claude" / "git-workflow.md"
AGENTS = REPO_ROOT / "AGENTS.md"

_GATE_TARGETS = (
    "make lint",
    "make format-check",
    "make typecheck",
    "make security",
    "make dead-code",
    "make shellcheck",
    "make test",
)


def test_dev_environment_carries_the_gate_table() -> None:
    """HOOK-06 (D-06): every gate, its target, the validate aggregate and the re-run rule."""
    text = DEV_ENVIRONMENT.read_text(encoding="utf-8")
    phrases = (
        *_GATE_TARGETS,
        "make validate",
        "make hooks-e2e",
        "make dev-setup",
        "pre-commit run --all-files",
        "re-run its own target",
    )
    for phrase in phrases:
        assert phrase in text, f"dev-environment.md lacks {phrase!r}"


def test_dev_environment_has_the_stage_table_with_timings() -> None:
    """HOOK-06 (SPEC R6): a Stage table carries measured timings and their measurement date."""
    text = DEV_ENVIRONMENT.read_text(encoding="utf-8")
    assert re.search(r"\|\s*Stage\s*\|", text), "no Stage table header"
    timings = re.findall(r"\d+(?:\.\d+)? ?(?:s|min)\b", text)
    assert len(timings) >= 3, f"fewer than three measured timings: {timings}"
    assert re.search(r"measured[^\n]*2026-", text), "no 2026 measurement date"


def test_dev_environment_documents_the_push_gate_and_recovery() -> None:
    """D-17/D-18/D-25/D-28: refusals and a placeholder-free, guarded edit recovery."""
    text = DEV_ENVIRONMENT.read_text(encoding="utf-8")
    phrases = (
        "--fail-fast",
        "main checkout",
        ".git/info/exclude",
        "GATE_READ_PATHSPECS",
        "even when git ignores",
        "${PRE_COMMIT_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/pre-commit}",
        'git apply --check "$patch" && git apply "$patch"',
    )
    for phrase in phrases:
        assert phrase in text, f"dev-environment.md lacks {phrase!r}"
    for line in text.splitlines():
        stripped = line.strip()
        assert stripped not in ('git apply "$patch"', 'git apply --check "$patch"'), (
            f"unguarded apply line: {line!r}"
        )
        if "git apply" in line:
            assert "<" not in line, f"placeholder on an apply line: {line!r}"


def _section(text: str, heading: str) -> str:
    """One Markdown section: its heading through the next heading of the same or higher level."""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("#") and heading in line),
        None,
    )
    assert start is not None, f"no section headed {heading!r}"
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.startswith("#") and len(line) - len(line.lstrip("#")) <= level:
            end = i
            break
    return "\n".join(lines[start:end])


def test_git_workflow_documents_the_path_to_main() -> None:
    """HOOK-05/06 (D-09, D-16, D-21): branch push, green CI, then a fast-forward of main."""
    text = GIT_WORKFLOW.read_text(encoding="utf-8")
    for phrase in ("git push origin <branch>:main", "strict", "fast-forward", "docs-only"):
        assert phrase in text, f"git-workflow.md lacks {phrase!r}"


def test_escape_hatch_turns_enforce_admins_back_on() -> None:
    """P6 (D-10, review M9/C2-M3): every mutation is guarded so the read-back always runs."""
    section = _section(GIT_WORKFLOW.read_text(encoding="utf-8"), "Escape hatch")
    anchors = (
        "branch=$(git branch --show-current)",
        (
            "gh api -X DELETE repos/castocolina/tools-installer/branches/main/"
            "protection/enforce_admins ||"
        ),
        'git push origin "$branch:main" ||',
        (
            "gh api -X POST repos/castocolina/tools-installer/branches/main/"
            "protection/enforce_admins ||"
        ),
        "gh api repos/castocolina/tools-installer/branches/main/protection --jq",
    )
    offsets = [section.index(anchor) for anchor in anchors]
    assert offsets == sorted(offsets) and len(set(offsets)) == len(offsets), (
        f"escape-hatch steps are not strictly ordered: {offsets}"
    )
    blocks = re.findall(r"```sh\n(.*?)```", section, re.DOTALL)
    assert blocks, "the escape hatch has no shell block"
    for block in blocks:
        for line in block.splitlines():
            if line.startswith("gh api -X") or line.startswith("git push"):
                assert "||" in line, f"unguarded mutating line: {line!r}"
            assert "<" not in line, f"placeholder in the escape block: {line!r}"
    assert "always" in section, "no always-follows statement"
    assert "cannot be restored" in section, "no escalation statement"
