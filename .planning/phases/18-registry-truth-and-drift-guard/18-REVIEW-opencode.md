### [HIGH] Registry writes are not bound to the checked snapshot
- `installer/verify_registry.py:1673-1681`
- The writer reloads the registry after verification, so its semantic guard validates a different document from the one checked.
- A maintainer changes a URL/member during the network checks → `--write` dates the unchecked entry; reordering methods can also apply candidate hashes to the wrong methods.
- Capture one snapshot for loading, checking and editing, and refuse the write if the file changed before replacement.

### [HIGH] Pinned GitHub API failures abort the drift report
- `installer/verify_registry.py:642`
- `_github_pin_mismatch` can raise `VersionError` outside any error-classification handler.
- Checking the shipped `drawio-desktop` entry while its release API is offline or rate-limited → an uncaught exception instead of an inconclusive report; previously confirmed drift never reaches issue reporting.
- Classify these failures through the existing release-error handling and continue checking pinned URLs without API metadata.

### [HIGH] Shared-URL failures lose target identities and permit false verification
- `installer/verify_registry.py:896-915`
- Propagating a URL-wide failure copies the first target’s entire `Finding`, replacing other targets’ tool IDs, members and platforms.
- Tools A and B share a checksum-failing archive, and B has another passing target → B’s failure becomes A’s finding and disappears during merging, leaving B in `passed_tools()`.
- Preserve each target’s identity when propagating failure status and reason. Assert that every affected target remains present and cannot be dated.

### [MEDIUM] Successful app repairs leave rollback remnants that undo the repair
- `installer/apps.py:101-107`
- `install_app` returns without removing the `.old` bundle created by the shared swap function.
- Repair replaces bundle A with working bundle B → A remains as `.old`; the next update restores A before downloading, and a subsequent network failure leaves A installed instead of B.
- Finalize successful swaps consistently for install and update, cleaning `.old` and surfacing cleanup failures.

### [MEDIUM] App installation fails across filesystems without trying fallbacks
- `installer/apps.py:160-191`
- The extracted bundle is moved from the system temporary directory with `os.replace`, which cannot cross filesystems.
- A macOS home directory on another volume, or a separate-volume `TMPDIR` → `EXDEV` escapes `install_tool`, aborting the batch instead of trying the cask fallback.
- Stage the bundle on the Applications filesystem before the atomic swap, and translate filesystem failures into `ExecutorError`.

### [MEDIUM] Non-UTF-8 smoke output aborts the install ladder
- `installer/run.py:87-102`
- Strict text decoding can raise `UnicodeDecodeError`, which neither the smoke helper nor the engine handles.
- A binary prints byte `0xff` and exits 127 → decoding raises before the exit status becomes `CommandError`, so installation aborts rather than falling through.
- Decode captured output with an explicit replacement policy while preserving the process exit code and loader diagnostics.

### [MEDIUM] Archive fixtures make checksum tests timing-dependent
- `tests/test_verify_registry.py:53,303`
- The gzip helpers embed the current timestamp, so identical fixture contents can produce different hashes.
- `_canned_difftastic_assets()` computes a digest just before a second boundary, then `_difftastic_download()` regenerates the archive afterward → a valid fixture reports checksum drift.
- Generate gzip fixtures with a fixed modification time, or reuse the exact bytes used to calculate their digests.

### [LOW] The unpinned-version regression assertion is ineffective
- `tests/test_verify_registry.py:2569-2573`
- The test checks only that the original fixture contains `"difftastic"` whenever the output contains a version key.
- A writer regression adds `version = "1"` to an unpinned method → the test still passes because `"difftastic"` is always in the fixture.
- Compare parsed method keys before and after writing, explicitly rejecting newly added `version` and `sha256` keys.

TOTAL: 8 findings (0 critical, 3 high, 4 medium, 1 low)
