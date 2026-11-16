# Ponytail review — Phase 18 (`git diff 22e6c5e..HEAD -- . ':(exclude).planning'`)

**What this change does:** It closes the registry schema (with a closed key set per kind, plus required `verified` dates and `version`/`sha256` pins), verifies every download against a checksum file, a pinned sha256 or the GitHub API digest, and runs each new binary once ("smoke run") before linking it. It adds `installer/verify_registry.py`: a read-only drift checker that probes every release asset for every os/arch, can bump pins with `--write`, and runs weekly in CI to open or update one GitHub issue. It also covers `--no-dev` launch, macOS stub detection, version parser fixes and the audit data fixes.

Assumed load: one maintainer or one weekly CI job running against ~90 tools and ~170 rendered assets, with GitHub API limits (60/h without auth, 1000/h with the Actions token). The installer side is one user and one process.

Counts: **HIGH 0 · MEDIUM 5 · LOW 14**. Lean: about **-230 lines** possible, about 150 of them in `verify_registry.py`.

---

## Should fix

### 1. [MEDIUM] Failed release reads are not cached, so a slow GitHub API can stop the weekly job before it reports (`installer/verify_registry.py:1583`, `:577-590`, `:358-384`)
- **What this is:** `default_probe` wraps `resolve_github_release` in `functools.cache`. `_collect_targets` asks for the release once per os/arch platform (up to 8 per method).
- **Problem:** `functools.cache` does not store exceptions, so a repo whose read fails is fetched again for every platform. `seen_release_errors` removes duplicate *findings*, not duplicate *requests*. Example: the API hangs, and `urlopen_fetch` waits its 10 s timeout on each of the ~170 rendered targets. That is about 28 minutes, more than the 25-minute step timeout in `.github/workflows/verify-registry.yml`. The job is killed, and the "inconclusive" report from L-18-05/L-18-15 is never printed. Even with a fast rate-limit 403, each repo still costs up to 8 extra calls.
- **Fix:** Store failures the same way `head_once` already does. In `tracked_release`, keep a `dict[str, Release | VersionError]` and raise the stored error when the repo is asked for again. That is about 6 lines, and it also makes the "no HTTP response" counters count once per repo.
- **If we skip it:** A slow GitHub API turns the weekly run into a timeout with no report instead of an "inconclusive" one.

### 2. [MEDIUM] Newer-stable check hides release-read errors for pinned app/tarball tools (`installer/verify_registry.py:305-308`)
- **What this is:** `_newer_stable_findings` reads `/releases/latest` for each pinned `app`/`tarball` URL on GitHub to report a newer stable release.
- **Problem:** `except VersionError: continue` adds no finding and no note. Example: a 404 (the upstream has no "latest" release any more) or a 5xx for jgraph/drawio-desktop. The tool's own asset checks still pass, so `passed_tools()` includes it, `--write` dates it as verified, and nobody hears that the newer-stable check never ran. The `github_release` path reports this same error through `_release_read_finding` (a 404 counts as drift).
- **Fix:** `except VersionError as exc: findings.append(_release_read_finding(tool.id, repo, exc)); continue`. One line, using the existing helper.
- **If we skip it:** Pinned tools can stop getting bump alerts without any signal, and still get a fresh `verified` date.

### 3. [MEDIUM] `install_app` leaves `<App>.app.old` behind when it replaces an existing bundle (`installer/apps.py:107`, `:117-128`, `:189-211`)
- **What this is:** Install and update now share `_stage_and_swap_app`, which moves the live bundle to `.old`, swaps in the new one and validates it.
- **Problem:** Only `update_app` deletes `.old` afterwards. A `repair=True` install of an existing draw.io bundle returns with `~/Applications/draw.io.app.old` still on disk. On the next run, `recover_update_remnants` treats any `.old` as an unfinished update and restores it over the just-repaired bundle (`atomic.py:78-105`). Until then, Finder and Spotlight show a second copy of the app. The download path does not have this problem, because `_replace_archive` removes `.old` itself.
- **Fix:** Move the `.old` cleanup (the 7 lines in `update_app`) to the end of `_stage_and_swap_app` and return the warnings from there. Then `update_app` becomes a one-line wrapper, and install and update stay identical, the same way `_replace_archive` works.
- **If we skip it:** Repaired apps leave a stale bundle that the next run treats as a crashed update.

### 4. [MEDIUM] 18 near-identical `Finding(...)` blocks and 3 copies of the HTTP-error ladder in `check_registry` (`installer/verify_registry.py:640-891`)
- **What this is:** The main check loop.
- **Problem:** Each outcome repeats `tool_id=target.tool_id, url=target.url, member=target.member, platforms=target.platforms` in 7–8 lines. That happens 18 times. The "HTTPError 404/410 → drift asset missing, other HTTPError → inconclusive, URLError/Timeout/OSError → inconclusive" ladder is also copied for HEAD (:656-685), the checksum sidecar (:706-735) and the asset download (:798-829). A change to the outage rules (L-18-10/15) must be made in 3 places.
- **Fix:** Add `def _f(t, status, reason, sha256=None) -> Finding` and `def _transport_finding(t, exc, asset) -> Finding` (the ladder, returning drift or inconclusive). Each `except` branch becomes `findings[key] = _transport_finding(target, exc, name); continue`. About **-100 lines**, and behavior stays the same.
- **If we skip it:** The core of the drift checker stays about 250 lines longer than needed, and the three error ladders will drift apart.

### 5. [MEDIUM] Two release resolvers that must agree: `ExecContext.resolve_tag` and an optional `resolve_release` (`installer/download.py:53-54`, `:111-114`; `installer/versions.py:404-415`)
- **What this is:** `resolve_target` uses `ctx.resolve_release` when it is set. Otherwise it builds `Release(ctx.resolve_tag(repo), {})`.
- **Problem:** All three production builders (`engine.py:188`, `update.py:332`, `verify_registry.py:364`) already pass `resolve_release`, and `release_resolver()` already contains the same "no digests" fallback. So the `None` branch only serves tests, and the result is two fallbacks for one rule. A new caller that forgets `resolve_release` silently gets no digests, so every install reads "unverified", and no test fails.
- **Fix:** Make `resolve_release: ReleaseResolver` required and drop `resolve_tag` from `ExecContext`. Delete the fallback in `resolve_target` and the `resolve_tag=lambda …` in `verify_registry.py:367`. The two test constructors pass `release_resolver(fake)`. About -6 lines, and one source of truth.
- **If we skip it:** Digest verification depends on every caller remembering an optional field.

---

## Nice to have / lean

### 6. [LOW] Dead parameter `_full_verify` (`installer/verify_registry.py:561`, `:687-696`)
No caller or test passes it. Delete the parameter and its 10-line branch.

### 7. [LOW] Dead `except` clause in `tracked_download` (`installer/verify_registry.py:617-618`)
`except (URLError, TimeoutError, OSError): raise` does nothing. Delete 2 lines.

### 8. [LOW] Dead, silent `except ValueError: continue` (`installer/verify_registry.py:396-397`)
`resolve_target` already wraps every `render_asset`/`arch_tokens` `ValueError` as `ExecutorError`. If a `ValueError` ever did get here, the target would vanish with no finding and the tool could still be dated. Delete it so an unexpected error fails loudly.

### 9. [LOW] Rebuilding `_TargetIdentity` field by field to add one platform (`installer/verify_registry.py:417-434`)
`dataclasses.replace` is already imported. Use `grouped[key] = replace(existing, platforms=tuple(sorted((*existing.platforms, plat))))`. -14 lines. The `identity_key` closure (:605) also duplicates the grouping key built at :408-415, so one `_identity(t)` helper can serve both.

### 10. [LOW] Download cache: duplicate unpack and a 404 that is re-downloaded (`installer/verify_registry.py:781-837`)
`actual_hash, listings = url_download_cache[...]` runs both in the `else:` (:831) and again at :837, so the `else` is dead. The `url_wide` check (:833) runs *after* the download attempt. A URL whose GET returned 404 is never put in `url_download_cache`, so every other target on that URL (another member or strip) downloads it again. Move `if target.url in url_wide: …; continue` above the download and drop the `else`. Related: `listings` is keyed by archive mode per URL, but only the first target's mode is ever listed. A second target on the same URL with a different `archive` gets `None`, so `names = []`, and it is reported as a false "member missing". Store a plain `list[str] | BaseException` per URL, or key the cache by `(url, archive)`.

### 11. [LOW] `_header_get` re-implements case-insensitive header lookup (`installer/verify_registry.py:232-243`)
`HTTPError.headers` is an `email.message.Message`, whose `.get` already ignores case, and the tests build it that way. Replace the 12 lines with `headers = error.headers; remaining = headers.get(...) if headers else None`.

### 12. [LOW] Bump planning reads the tag back out of a human-readable reason (`installer/verify_registry.py:1117`, `:1161-1181`)
`_auto_bump_candidate` regex-parses `"newer stable release X (pinned …)"` to recover the tag that `_newer_stable_findings` already had. Add `latest_tag: str | None = None` to `Finding`, set it at :311-318, and delete `_NEWER_STABLE_RE`. Rewording the message can then no longer break auto-bumps.

### 13. [LOW] App member and "unverified" rule written three times (`installer/verify_registry.py:207-215`, `:399-403`, `:1217-1227`)
`_resolve_app_target` and `_pinned_finding_member` both derive `app/cli`. `_collect_targets` then special-cases "app URL without `{ver}`" as unverified, because `_resolve_app_target` never sets `unverified_reason`, unlike `download.resolve_target` for tarballs. Set `unverified_reason=None if pin else apps._UNVERIFIED_REASON` in `_resolve_app_target`. Make `_pinned_finding_member` call `_resolve_app_target(_method_at_version(m, v)).member` for apps. Delete the special case. About -15 lines.

### 14. [LOW] Re-checking what `load_tools` already guarantees (`verify_registry.py:1120-1142`, `:293-298`; `apps.py:93-99`; `executors.py:55-62`)
The loader (`model.py:730-750`, `:830-845`) already enforces three things. A URL with `{ver}` has a non-empty `version` and a 64-hex `sha256`. A URL without `{ver}` has neither. `smoke_argv` is a non-empty list of strings. So `_is_pinned_method` reduces to `kind in ("app","tarball") and "{ver}" in url`. `_pinned_version` reduces to one lookup. The raising branch of `apps._declared_sha256` is dead, and `method_smoke_argv` reduces to `tuple(method.params.get("smoke_argv", ("--version",)))`. About -15 lines.

### 15. [LOW] Same merge, sort and dedupe in two places (`installer/verify_registry.py:912-919`, `:1298-1305`)
Extract `_merge_findings(iterable) -> tuple[Finding, ...]`. -8 lines.

### 16. [LOW] `main` housekeeping (`installer/verify_registry.py:1645`, `:1655`, `:1657-1658`, `:1662-1668`, `:1595-1602`)
`import sys` appears twice inside the function, so move it to the top of the module. `_persist_state` is `functools.partial(_save_state, state_path)`. `_parse_explicit_candidates([])` already returns `{}`, so the `if args.candidate … else explicit = {}` branch is redundant. `probe.download`'s read loop is `shutil.copyfileobj(resp, handle)`. Also, `_plan_bumps` → `_build_bump_edits` can raise `RegistryWriteError` outside the `try` at :1676, which gives a traceback instead of the clean exit 64. Move `_plan_bumps` inside that `try`.

### 17. [LOW] Unreachable fallback in `smoke_binary` (`installer/executors.py:103-109`)
No alternative in `_LOADER_ERROR` contains a newline, so if the whole stderr matches, some single line matches too. The final `raise` after the loop cannot run. Keep only the loop: -3 lines.

### 18. [LOW] Small duplicates outside `verify_registry.py`
- `engine.py:218-227`: the two `leftover` strings differ only in their tail. Build the tail with `f"remove it with `{removal}`" if removal else "remove it with that installer's own uninstaller"`. -5 lines.
- `download.py:211-235`: `target.checksum is not None or target.sha256 is not None` appears three times (also at :256). Add a `DownloadTarget.verified` property. `resolve_target`'s two tarball `return`s (:152-164) can become one with `unverified_reason=None if pin else "…"`.
- `version_status.py:194-198`: `VersionCacheEntry(latest_version=None, checked_at=None).digests` just means `{}`. `version_cache.py:50-51`: `_empty_digest_map` can be `field(default_factory=dict)`.
- `ownership.py:1446-1451`: `_NATIVE_KIND_TO_OWNER` restates the existing rule `_KIND_TO_OWNER.get(kind, kind.replace("_", "-"))` (`ownership.py:1315`). Reuse that expression. `_REMOVAL_COMMANDS.get` already returns `None` for unknown owners. -6 lines.

### 19. [LOW] Registry writer header detection is redundant (`installer/verify_registry.py:959-968`)
`_SUBTABLE_HEADER_RE` is fully covered by the following `startswith("[[")` check, apart from `[tool.x]`. Use `s.startswith("[") and s != "[[tool]]"`. -4 lines. The tool-level region loop in `_region_for_edit` (:1058-1065) also re-scans for the first sub-header. The rest of the writer (the semantic re-parse guard) is the locked D-09 design and is fine.

---

## Checked and fine (decisions, not findings)
- The `version_cache` digests are write-only until Phase 19 (D-05 locked). The `actions/cache` Thursday refresh is L-18-07. The per-target state save (`on_verified`) supports resuming after a timeout. `code_span` is required by L-18-17.
- Smoke-before-link is correct: `_replace_raw` unlinks the staged file, and `_replace_archive` removes `.new` before any swap. `_undo_*_swap` now drops a link it created when there was no prior target.
- The tests are behaviour-level, not private-helper tests. Nothing to cut there.

Verdict: fix 1, 2 and 3 first. 4 and 5 are the biggest simplification wins.
Lean: -230 lines possible.
Not checked: I did not run make validate or make test (per instruction). I did not read the `.claude/*.md` doc diffs or `registry.toml` data line by line. I did not run anything on macOS.
