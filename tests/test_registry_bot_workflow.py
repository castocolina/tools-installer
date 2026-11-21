"""Validate the bot workflow, CI dispatch, Dependabot and proof runbook as plain file parses
without network or gh.
"""

import re
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
BOT_WORKFLOW = ROOT / ".github" / "workflows" / "registry-bot.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RUNBOOK = ROOT / "docs" / "registry-bot-proof.txt"
REQUIRED_CHECKS: tuple[str, str] = (
    "validate & test on ubuntu-latest",
    "validate & test on macos-latest",
)


def _load(path: Path) -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(path.read_text()))


def _triggers(data: dict[Any, Any]) -> dict[Any, Any]:
    return cast(dict[Any, Any], data.get("on", data.get(True, {})))


MAIN_TARGET: re.Pattern[str] = re.compile(r"HEAD:main\b|refs/heads/main\b|\borigin main\b|:main\b")
NO_PR_OR_MERGE: re.Pattern[str] = re.compile(r"\bgh pr\b|\bgit merge\b|\bgh api\b")
PUBLISH_VERBS: tuple[str, ...] = (
    "git commit",
    "git push",
    "gh workflow run",
    "gh issue",
    "gh label",
)
SAME_EXEMPT: frozenset[str] = frozenset(
    {
        "Dispatch CI for an unchanged bot branch",
        "Report a failed push or CI dispatch",
        "Delete older bot branches",
    }
)
BOUNDARY_PHRASE = "a dispatch is an owner act"


def _bot() -> dict[Any, Any]:
    return _load(BOT_WORKFLOW)


def _job() -> dict[Any, Any]:
    return cast(dict[Any, Any], _bot()["jobs"]["bump"])


def _steps() -> list[dict[Any, Any]]:
    return cast(list[dict[Any, Any]], _job()["steps"])


def _step(name: str) -> dict[Any, Any]:
    return next(step for step in _steps() if step.get("name") == name)


def _runs() -> list[str]:
    return [cast(str, step["run"]) for step in _steps() if "run" in step]


def _index(text: str, *parts: str) -> None:
    positions = [text.index(part) for part in parts]
    assert all(a < b for a, b in zip(positions, positions[1:], strict=False))


def test_the_required_check_names_follow_from_the_ci_job() -> None:
    job = _load(CI_WORKFLOW)["jobs"]["validate-and-test"]
    name = job["name"]
    systems = job["strategy"]["matrix"]["os"]
    assert tuple(name.replace("${{ matrix.os }}", system) for system in systems) == REQUIRED_CHECKS


def test_a_dispatch_runs_the_same_single_job_under_the_same_concurrency() -> None:
    data = _load(CI_WORKFLOW)
    assert set(data["jobs"]) == {"validate-and-test"}
    assert data["concurrency"] == {
        "group": "ci-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    assert "workflow_dispatch" in _triggers(data)


def test_the_committed_trigger_set_is_dispatch_only() -> None:
    """After the proof the owner uncomments cron 37 6 * * 1 and expects schedule too."""
    assert set(_triggers(_bot())) == {"workflow_dispatch"}


def test_any_cron_is_off_minute() -> None:
    triggers = _triggers(_bot())
    if "schedule" in triggers:
        assert set(triggers) == {"schedule", "workflow_dispatch"}
        assert all(not entry["cron"].startswith("0 ") for entry in triggers["schedule"])


def test_permissions_are_exactly_the_three_writes() -> None:
    assert _bot()["permissions"] == {"contents": "write", "actions": "write", "issues": "write"}
    assert "permissions" not in _job()


def test_concurrency_queues_one_group() -> None:
    assert _bot()["concurrency"] == {"group": "registry-bot", "cancel-in-progress": False}


def test_the_job_timeout_covers_a_cold_run() -> None:
    timeout = _job()["timeout-minutes"]
    bump = _step("Bump pins")["timeout-minutes"]
    assert isinstance(timeout, int) and timeout >= 60
    assert isinstance(bump, int) and bump < timeout


def test_the_job_token_is_the_default_token() -> None:
    assert _job()["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert all("GH_TOKEN" not in step.get("env", {}) for step in _steps())
    assert "secrets." not in BOT_WORKFLOW.read_text()


def test_the_bump_step_runs_the_flag_directly() -> None:
    step = _step("Bump pins")
    assert step["id"] == "bump"
    run = step["run"]
    _index(
        run,
        "code=0",
        "uv run --isolated --no-dev python -m installer.verify_registry "
        "--write --bumps-only || code=$?",
        'case "$code" in 0|1|2) ;; *) echo "verify-registry exited $code" >&2; '
        'exit "$code" ;; esac',
    )
    assert "make " not in run
    assert all("--issue" not in run for run in _runs())


def test_the_state_cache_is_shared_with_the_drift_workflow() -> None:
    steps = _steps()
    restore = _step("Restore verify-registry state")
    bump = _step("Bump pins")
    save = _step("Save verify-registry state")
    assert restore["uses"].startswith("actions/cache/restore")
    assert save["uses"].startswith("actions/cache/save")
    assert steps.index(restore) < steps.index(bump) < steps.index(save)
    drift = _load(ROOT / ".github" / "workflows" / "verify-registry.yml")
    drift_restore = next(
        s
        for s in drift["jobs"]["verify"]["steps"]
        if s.get("uses", "").startswith("actions/cache/restore")
    )
    assert restore["with"]["path"] == save["with"]["path"] == drift_restore["with"]["path"]
    assert "${{ github.run_id }}" in save["with"]["key"]
    assert restore["with"]["restore-keys"].startswith("verify-registry-")
    assert save["if"] == "always()" and "if" not in restore


def test_no_run_step_interpolates_an_expression() -> None:
    assert all("${{" not in run for run in _runs())


def test_the_guard_separates_no_change_from_a_git_error() -> None:
    step = _step("Guard")
    assert step["id"] == "guard"
    assert _steps().index(_step("Bump pins")) < _steps().index(step)
    run = step["run"]
    _index(
        run,
        "code=0",
        "git diff --quiet -- installer/registry.toml || code=$?",
        'case "$code" in 0) changed=false ;; 1) changed=true ;; *) '
        'echo "git diff exited $code" >&2; exit "$code" ;; esac',
        'echo "changed=$changed" >> "$GITHUB_OUTPUT"',
    )
    assert "else" not in run and "if git diff" not in run


def test_every_publishing_step_is_guarded_by_the_changed_output() -> None:
    steps = _steps()
    names: set[str] = set()
    for step in steps:
        if any(verb in step.get("run", "") for verb in PUBLISH_VERBS):
            names.add(step["name"])
            assert steps.index(step) > steps.index(_step("Guard"))
            assert "steps.guard.outputs.changed == 'true'" in step["if"]
            if step["name"] not in SAME_EXEMPT:
                assert "steps.compare.outputs.same != 'true'" in step["if"]
    assert names == {
        "Upsert the tracking issue",
        "Publish the bot branch",
        "Dispatch CI on the bot branch",
        "Dispatch CI for an unchanged bot branch",
        "Report a failed push or CI dispatch",
        "Delete older bot branches",
    }


def test_compare_skips_only_an_identical_bot_branch_on_the_current_base() -> None:
    step = _step("Compare with the bot branch")
    assert step["id"] == "compare"
    assert "steps.guard.outputs.changed == 'true'" in step["if"]
    assert (
        _steps().index(_step("Guard"))
        < _steps().index(step)
        < _steps().index(_step("Publish the bot branch"))
    )
    run = step["run"]
    _index(
        run,
        'remote=$(git ls-remote --heads origin "refs/heads/$BRANCH")',
        "same=false",
        "expected=\n",
        'if [ -n "$remote" ]; then',
        'git fetch --no-tags origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"',
        'expected=$(git rev-parse "refs/remotes/origin/$BRANCH")',
        'if git diff --quiet "refs/remotes/origin/$BRANCH" -- installer/registry.toml && '
        '[ "$(git rev-parse "$expected^")" = "$(git rev-parse HEAD)" ]; then',
        "same=true",
        'echo "The bot branch already holds this change on the current base: nothing to publish."',
        "  fi",
        "\nfi",
        'echo "same=$same" >> "$GITHUB_OUTPUT"',
        'echo "expected=$expected" >> "$GITHUB_OUTPUT"',
    )
    lines = run.splitlines()
    assert lines.index("expected=") < lines.index('if [ -n "$remote" ]; then')
    assert all("||" not in line for line in lines if "git fetch" in line)
    assert not re.search(r"\|\|\s*true", run)
    assert "git commit" not in run and "git push" not in run


def test_publish_pushes_with_an_explicit_lease() -> None:
    step = _step("Publish the bot branch")
    assert step["id"] == "publish"
    assert step["env"]["EXPECTED"] == "${{ steps.compare.outputs.expected }}"
    run = step["run"]
    _index(
        run,
        'git config user.name "github-actions[bot]"',
        'git config user.email "41898282+github-actions[bot]@users.noreply.github.com"',
        "git add installer/registry.toml",
        'git commit -m "chore(registry): bump pinned releases"',
        'git push --force-with-lease="refs/heads/$BRANCH:$EXPECTED" origin '
        '"HEAD:refs/heads/$BRANCH"',
    )
    assert not any(
        text in run for text in ("git add -A", "git add .", "git commit -a", "git fetch")
    )
    assert run.count("git push") == 1 and re.search(r"--force(?!-with-lease)", run) is None


def test_the_dispatch_step_retries_once_and_names_the_bot_branch() -> None:
    branch = _step("Name the branch")
    assert "BRANCH=bot/registry-$(date -u +%F)" in branch["run"]
    assert '>> "$GITHUB_ENV"' in branch["run"]
    for name in (
        "Compare with the bot branch",
        "Publish the bot branch",
        "Dispatch CI on the bot branch",
        "Dispatch CI for an unchanged bot branch",
    ):
        assert _steps().index(branch) < _steps().index(_step(name))
    step = _step("Dispatch CI on the bot branch")
    assert step["id"] == "dispatch"
    assert _steps().index(_step("Publish the bot branch")) < _steps().index(step)
    run = step["run"]
    command = 'gh workflow run ci.yml --ref "$BRANCH"'
    assert next(line for line in run.splitlines() if line.strip()).startswith(command)
    assert run.count(command) == 2 and run.count("gh ") == 2
    _index(run, command, "||", "sleep 20", command + "\n")
    assert CI_WORKFLOW.name in run and "workflow_dispatch" in _triggers(_load(CI_WORKFLOW))


def test_an_unchanged_bot_branch_is_dispatched_unless_ci_ran_or_passed_for_its_head() -> None:
    step = _step("Dispatch CI for an unchanged bot branch")
    assert step["id"] == "redispatch"
    assert "steps.guard.outputs.changed == 'true'" in step["if"]
    assert "steps.compare.outputs.same == 'true'" in step["if"]
    assert _steps().index(_step("Compare with the bot branch")) < _steps().index(step)
    assert step["env"]["EXPECTED"] == "${{ steps.compare.outputs.expected }}"
    run = step["run"]
    command = 'gh workflow run ci.yml --ref "$BRANCH"'
    _index(
        run,
        """seen=$(gh run list --workflow ci.yml --branch "$BRANCH" """
        """--json headSha,status,conclusion --jq '.[] | select(.headSha == env.EXPECTED) """
        """| select(.status != "completed" or .conclusion == "success") | .headSha')""",
        'if [ -n "$seen" ]; then',
        'echo "CI is running or passed for $EXPECTED: nothing to dispatch."',
        "else",
        command,
        "sleep 20",
        command + "\n",
        "\nfi",
    )
    assert '.conclusion == "success"' in run and ".conclusion !=" not in run
    assert run.count(command) == 2
    assert not any(
        text in run for text in ("grep", "git commit", "git push", "gh issue", "gh label")
    )


def test_no_step_targets_the_default_branch() -> None:
    """Structural guard, not runtime control: the token could push elsewhere.

    Only the owner dispatches (T-33-11).
    """
    runs = _runs()
    assert any("git push" in run for run in runs)
    for run in runs:
        assert not MAIN_TARGET.search(run) and not NO_PR_OR_MERGE.search(run)
        for line in run.splitlines():
            if "git push" in line:
                assert "HEAD:refs/heads/$BRANCH" in line or "--delete" in line


def test_the_main_target_pattern_matches_what_it_must() -> None:
    for text in (
        "git push origin HEAD:main",
        "git push origin HEAD:refs/heads/main",
        "git push origin main",
        "git push origin x:main",
    ):
        assert MAIN_TARGET.search(text)
    for text in (
        "bot/registry-2026-11-21",
        "the domain",
        "refs/heads/maintenance",
        "git rev-parse origin/main",
        'git push --force-with-lease="refs/heads/$BRANCH:$EXPECTED" origin '
        '"HEAD:refs/heads/$BRANCH"',
        'git fetch --no-tags origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"',
    ):
        assert MAIN_TARGET.search(text) is None


def test_the_tracking_issue_is_upserted_before_the_commit_with_its_own_label() -> None:
    step = _step("Upsert the tracking issue")
    assert step["id"] == "issue"
    assert "steps.guard.outputs.changed == 'true'" in step["if"]
    assert "steps.compare.outputs.same != 'true'" in step["if"]
    assert (
        _steps().index(_step("Compare with the bot branch"))
        < _steps().index(step)
        < _steps().index(_step("Publish the bot branch"))
    )
    run = step["run"]
    _index(
        run,
        "gh label create registry-bot --force --description "
        '"Pins proposed by the registry update bot"',
        "number=$(gh issue list --label registry-bot --state open --limit 1 --json number "
        "--jq '.[0].number // empty')",
        "base=$(git rev-parse --short HEAD)",
        'body="',
        'if [ -n "$number" ]; then',
        'gh issue edit "$number" --body "$body"',
        "else",
        "url=$(gh issue create --title",
        'number="${url##*/}"',
        "\nfi\n",
        'case "$number" in',
        "*[!0-9]*)",
        "could not read the issue number",
        "exit 1",
        "esac",
        'echo "number=$number" >> "$GITHUB_OUTPUT"',
    )
    body = run.split('body="', 1)[1].split('"', 1)[0]
    for text in (
        "Branch: $BRANCH",
        "Base commit: $base",
        "close it by hand",
        "Older bot branches are replaced by the newest one",
        "certifies its bumped pins only",
        BOUNDARY_PHRASE,
        "write token",
        "both required checks",
        "exact commit",
    ):
        assert text in body
    assert not any(text in body for text in ("`", "'", "$("))
    assert all("registry-drift" not in text for text in _runs())


def test_the_commit_carries_the_closing_keyword_for_the_issue() -> None:
    step = _step("Publish the bot branch")
    assert step["env"]["ISSUE_NUMBER"] == "${{ steps.issue.outputs.number }}"
    assert any(
        "git commit" in line and '-m "Closes #$ISSUE_NUMBER"' in line
        for line in step["run"].splitlines()
    )


def test_a_failed_push_or_dispatch_is_reported_on_the_issue() -> None:
    step = _step("Report a failed push or CI dispatch")
    condition = step["if"]
    assert "failure()" in condition and "steps.guard.outputs.changed == 'true'" in condition
    for name in ("publish", "dispatch", "redispatch"):
        assert f"steps.{name}.outcome == 'failure'" in condition
        assert step["env"][f"{name.upper()}_OUTCOME"] == "${{ steps." + name + ".outcome }}"
    assert (
        _steps().index(_step("Dispatch CI for an unchanged bot branch"))
        < _steps().index(step)
        < _steps().index(_step("Delete older bot branches"))
    )
    run = step["run"]
    _index(
        run,
        'stage="CI dispatch"',
        'command="gh workflow run ci.yml --ref $BRANCH"',
        'if [ "$PUBLISH_OUTCOME" = "failure" ]; then',
        'stage="push"',
        'command="gh workflow run registry-bot.yml --ref $GITHUB_REF_NAME"',
        "; fi\n",
        "number=$(gh issue list --label registry-bot --state open --limit 1 --json number "
        "--jq '.[0].number // empty')",
        'if [ -n "$number" ]; then',
        'gh issue comment "$number" --body',
        "else",
        'no open registry-bot issue to comment on; run by hand: $command" >&2; fi',
    )
    assert "git push" not in run


def test_older_bot_branches_are_deleted_only_inside_the_bot_namespace() -> None:
    step = _step("Delete older bot branches")
    condition = step["if"]
    assert "steps.guard.outputs.changed == 'true'" in condition
    assert "steps.dispatch.outcome == 'success'" in condition
    assert "steps.redispatch.outcome == 'success'" in condition and "||" in condition
    assert "failure()" not in condition and "steps.compare.outputs.same" not in condition
    assert (
        _steps().index(_step("Report a failed push or CI dispatch"))
        < _steps().index(step)
        < _steps().index(_step("Save verify-registry state"))
    )
    run = step["run"]
    _index(
        run,
        "set -o pipefail",
        "listing=$(git ls-remote --heads origin 'refs/heads/bot/registry-*')",
        "while read -r sha ref; do",
        'case "$ref" in',
        '"refs/heads/$BRANCH") ;;',
        'refs/heads/bot/registry-*) git push --force-with-lease="$ref:$sha" '
        '--delete origin "$ref" < /dev/null',
        "could not delete",
        '*) echo "ignoring',
        "esac",
        'done <<< "$listing"',
    )
    assert "| while" not in run and run.count("git ls-remote") == 1 and run.count("git push") == 1
    assert set(re.findall(r"""refs/heads/[^\s"'*)]*""", run)) <= {
        "refs/heads/bot/registry-",
        "refs/heads/$BRANCH",
    }
    assert re.search(r"--force(?!-with-lease)", run) is None


def test_no_run_step_exposes_a_credential() -> None:
    for run in _runs():
        assert not any(
            text in run
            for text in ("secrets.", "GH_TOKEN", "GITHUB_TOKEN", "printenv", "set -x", "xtrace")
        )
    assert BOT_WORKFLOW.read_text().count("github.token") == 1


def _runbook() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    rest = text.split(f"== {title}\n", 1)[1]
    return rest.split("\n== ", 1)[0]


def test_the_runbook_has_the_part_one_and_two_commands() -> None:
    text = _runbook()
    for part in (
        'git ls-remote --heads origin "refs/heads/bot/registry-$DATE"',
        'git fetch origin "+refs/heads/bot/registry-$DATE:refs/remotes/origin/bot/registry-$DATE"',
        'SHA=$(git rev-parse "refs/remotes/origin/bot/registry-$DATE")',
        'git rev-parse "$SHA^"',
        'gh run list --workflow ci.yml --commit "$SHA" --json event,conclusion,headSha,status',
        "gh api repos/$REPO/commits/$SHA/check-runs",
        "gh api repos/$REPO/branches/main/protection "
        "--jq '.required_status_checks.checks[].context'",
        "gh issue list --label registry-bot --state open",
        "nothing to publish",
        "workflow_dispatch",
    ):
        assert part in text
    assert (
        sum("gh workflow run registry-bot.yml --ref main" in line for line in text.splitlines())
        == 2
    )
    assert "--candidate" not in text and "proof/registry-bot" not in text


def test_the_runbook_names_the_required_checks_exactly() -> None:
    text = _runbook()
    assert all(check in text for check in REQUIRED_CHECKS)


def test_the_runbook_never_targets_the_default_branch() -> None:
    text = _runbook()
    assert MAIN_TARGET.search(text) is None
    assert not any(part in text for part in ("sudo", "--no-verify", "SKIP=", "core.hooksPath"))
    for line in text.splitlines():
        if "git push" in line:
            assert re.search(r"\bmain\b", line) is None
            push = line.split("git push", 1)[1].split(";", 1)[0]
            assert re.search(r"--force(?!-with-lease)", push) is None


def test_every_ref_the_runbook_creates_is_deleted_by_its_cleanup() -> None:
    text = _runbook()
    writes = _section(text, "What this writes to the remote")
    cleanup = _section(text, "Cleanup")
    for ref, prefix in (
        ("bot/registry-$DATE", "refs/heads/bot/registry-"),
        ("proof/target-$DATE", "refs/heads/proof/"),
        ("landing/registry-$DATE", "refs/heads/landing/"),
    ):
        assert any(ref in line and "removed in Cleanup" in line for line in writes.splitlines())
        assert any(prefix in line and "case" not in line for line in cleanup.splitlines())


def test_the_runbook_preflight_stops_on_existing_bot_work() -> None:
    before = _section(_runbook(), "Before you start")
    for part in (
        'git ls-remote --heads origin "refs/heads/bot/registry-*"',
        "gh issue list --label registry-bot --state open --json number --jq length",
        'git ls-remote --heads origin "refs/heads/proof/*" "refs/heads/landing/*"',
    ):
        assert part in before
    assert any(line.startswith("STOP") for line in before.splitlines())
    pushes = [line for line in before.splitlines() if "git push" in line]
    assert len(pushes) == 1 and pushes[0].startswith("push_exact()")
    assert "gh workflow run" not in before


def test_the_runbook_cleanup_removes_the_whole_proof_namespace() -> None:
    text = _runbook()
    cleanup = _section(text, "Cleanup")
    _index(
        cleanup,
        "set -o pipefail",
        'listing=$(git ls-remote --heads origin "refs/heads/bot/registry-*" '
        '"refs/heads/proof/*" "refs/heads/landing/*")',
        'case "$ref" in',
        "refs/heads/bot/registry-*|refs/heads/proof/*|refs/heads/landing/*)",
        'git push --force-with-lease="$ref:$sha" --delete origin "$ref"',
        'done <<< "$listing"',
        "open=$(gh issue list --label registry-bot --state open --json number --jq '.[].number')",
        "for n in $open; do",
        'gh issue close "$n"',
    )
    assert "the preflight proved" in cleanup and "rollover" in cleanup
    assert "| while" not in text and text.count("gh issue close") == 1
    assert not any(
        "gh issue close" in line and ("NUMBER" in line or "$ISSUE" in line)
        for line in text.splitlines()
    )


def test_the_runbook_stops_without_drift_identifies_the_bot_commit_and_stops_at_midnight() -> None:
    text = _runbook()
    part1 = _section(text, "Part 1: run the bot on the default branch")
    part2 = _section(text, "Part 2: read the check names and rerun the same day")
    assert any(line.startswith("STOP") and "no drift" in line for line in part1.splitlines())
    assert "git log -1 --format" in part1 and 'git diff --stat "$BASE" "$SHA"' in part1
    assert any(line.startswith("STOP") and "push" in line for line in part2.splitlines())
    for part in (part1, part2):
        checks = [
            line for line in part.splitlines() if line.startswith('[ "$(date -u +%F)" = "$DATE" ]')
        ]
        assert checks and all("STOP" in line for line in checks)
    assert "re-export" not in text


def test_the_runbook_binds_its_evidence_to_run_ids() -> None:
    text = _runbook()
    for part in (
        "BEFORE=$(gh run list --workflow registry-bot.yml --event workflow_dispatch "
        "--limit 1 --json databaseId --jq '.[0].databaseId // 0')",
        "BOT_RUN=$(gh run list --workflow registry-bot.yml --event workflow_dispatch "
        "--limit 1 --json databaseId --jq '.[0].databaseId')",
        'gh run watch "$BOT_RUN" --exit-status',
        'RUN_ID=$(gh run list --workflow ci.yml --commit "$SHA" --event workflow_dispatch '
        "--json databaseId --jq '.[0].databaseId // empty')",
        'gh run watch "$RUN_ID" --exit-status',
        "gh run view \"$RUN_ID\" --json jobs --jq '.jobs[] | {name, conclusion}'",
        'gh run watch "$BOT_RUN2" --exit-status',
        'gh run view "$BOT_RUN2" --log | grep "nothing to publish"',
    ):
        assert part in text
    lines = text.splitlines()
    for line in lines:
        if "gh run watch" in line:
            assert "--exit-status" in line and any(
                name in line
                for name in ('"$BOT_RUN"', '"$BOT_RUN2"', '"$RUN_ID"', '"$LANDING_RUN"')
            )
        if "--limit 1" in line:
            assert line.startswith(("BEFORE=", "BOT_RUN=", "BOT_RUN2="))
        if line.startswith("[ ") and " || echo" in line:
            assert "STOP" in line
    for guard in (
        '"$BOT_RUN" -gt "$BEFORE"',
        '"$BOT_RUN2" -gt "$BEFORE"',
        '-n "$RUN_ID"',
        '"$N" -ge 1',
    ):
        assert any(line.startswith("[ ") and guard in line and " || echo" in line for line in lines)


def test_the_runbook_gates_the_protection_write_on_owner_approval_and_names_both_options() -> None:
    text = _runbook()
    for part in ("Option A", "Option B", "OWNER APPROVAL REQUIRED", "STOP"):
        assert part in text
    puts = [line for line in text.splitlines() if "-X PUT" in line]
    assert len(puts) == 1
    assert "OWNER APPROVAL REQUIRED" in puts[0] and "proof/target-$DATE" in puts[0]
    assert not any("-X" in line and "branches/main" in line for line in text.splitlines())


def test_the_runbook_removes_the_temporary_protection_and_reads_it_back() -> None:
    cleanup = _section(_runbook(), "Cleanup")
    deletes = [line for line in _runbook().splitlines() if "-X DELETE" in line]
    assert len(deletes) == 1
    assert "repos/$REPO/branches/proof/target-$DATE/protection" in deletes[0]
    _index(
        cleanup,
        deletes[0],
        "404",
        'listing=$(git ls-remote --heads origin "refs/heads/bot/registry-*" '
        '"refs/heads/proof/*" "refs/heads/landing/*")',
    )


def test_the_runbook_pushes_through_a_worktree_at_the_exact_commit() -> None:
    text = _runbook()
    before = _section(text, "Before you start")
    helper = next(line for line in before.splitlines() if line.startswith("push_exact() {"))
    for part in (
        'git worktree add --detach "$wt" "$1"',
        'git push origin "HEAD:$2"',
        'git worktree remove --force "$wt"',
    ):
        assert part in helper
    assert "push gate" in before
    assert [
        line for line in text.splitlines() if "git push" in line and "--delete" not in line
    ] == [helper]
    calls = [line for line in text.splitlines() if 'push_exact "' in line]
    assert len(calls) == 3
    assert all(
        re.fullmatch(r'WRITE {3}push_exact "\$(SHA|BASE)" "refs/heads/[^"]+"', line)
        for line in calls
    )
    _index(
        text,
        '"+refs/heads/bot/registry-$DATE:refs/remotes/origin/bot/registry-$DATE"',
        'WRITE   push_exact "$SHA"',
    )
    assert (
        'gh run list --workflow ci.yml --commit "$SHA" --json event,conclusion,headSha,status'
        in _section(text, "Part 3: the BOT-02 question")
    )


def test_the_runbook_records_the_dispatch_evidence_before_option_a_final_push() -> None:
    text = _runbook()
    final = 'WRITE   push_exact "$SHA" "refs/heads/proof/target-$DATE"'
    for evidence in (
        'gh run watch "$RUN_ID" --exit-status',
        'gh run view "$RUN_ID" --json jobs',
        "gh api repos/$REPO/commits/$SHA/check-runs",
        "gh api repos/$REPO/branches/proof/target-$DATE/protection --jq",
    ):
        _index(text, evidence, final)
    assert any(
        "BEFORE" in line and "ordinary" in line
        for line in _section(text, "Part 3: the BOT-02 question").splitlines()
    )


def test_the_runbook_keeps_option_b_unverified() -> None:
    text = _runbook().split("Option B", 1)[1].split("\n== ", 1)[0]
    for part in (
        "UNVERIFIED",
        'LANDING_RUN=$(gh run list --workflow ci.yml --branch "landing/registry-$DATE" '
        "--commit \"$SHA\" --event push --json databaseId --jq '.[0].databaseId // empty')",
        'gh run watch "$LANDING_RUN" --exit-status',
        "gh api repos/$REPO/commits/$SHA/check-runs",
        'push_exact "$SHA" "refs/heads/landing/registry-$DATE"',
    ):
        assert part in text


def test_the_runbook_states_what_it_does_not_prove_and_when_bot_02_passes() -> None:
    text = _runbook()
    keyword = [line for line in text.splitlines() if "Closes #" in line]
    assert len(keyword) == 1 and "NOT EXERCISED" in keyword[0]
    record = _section(text, "Record the result")
    assert "human_needed" in record and "blocked" in record
    assert all("accepted" in line for line in record.splitlines() if "passed" in line)
    assert "recorded owner decision" not in text


def test_the_workflow_and_the_runbook_agree_on_the_contract() -> None:
    text = _runbook()
    triggers = _triggers(_bot())
    assert set(triggers) in ({"workflow_dispatch"}, {"schedule", "workflow_dispatch"})
    if "schedule" in triggers:
        assert any(entry["cron"] == "37 6 * * 1" for entry in triggers["schedule"])
    else:
        assert 'cron: "37 6 * * 1"' in BOT_WORKFLOW.read_text()
    assert "37 6 * * 1" in text


def test_the_runbook_ends_with_the_cron_enabling_and_push_restriction_steps() -> None:
    last = _runbook().rsplit("== ", 1)[1]
    for part in (
        "37 6 * * 1",
        "registry-bot.yml",
        "test_the_committed_trigger_set_is_dispatch_only",
        "needs no edit",
        "push restriction",
    ):
        assert part in last


def test_the_header_names_the_trust_boundary() -> None:
    text = BOT_WORKFLOW.read_text()
    header = text.split("name: registry-bot", 1)[0]
    header = " ".join(line.lstrip("# ").strip() for line in header.splitlines())
    header = " ".join(header.split())
    assert "Only a user with write access can dispatch this workflow" in header
    assert BOUNDARY_PHRASE in header and "no push restriction" in header
    assert "keeps this bot off" not in text and "is the control" not in text
