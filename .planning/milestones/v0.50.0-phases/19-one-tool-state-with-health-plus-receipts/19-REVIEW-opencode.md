# Phase 19 code review (opencode, gpt-6.1-sol)

## Findings

### F1 [HIGH] A proven raw file can become a recursive directory deletion
- File: installer/uninstall.py:411–417; installer/uninstall.py:387–394
- Problem: `remove_proven` reduces the verified artifacts to paths, losing their authorized types. If a raw binary is replaced with a directory after verification, `remove_paths` discovers the new type and calls `rmtree`, deleting contents that the file receipt never authorized. Verification of other artifacts widens this race window.
- Fix: Preserve the proven artifact type through deletion. File/link authorization must permit only unlinking, never recursive deletion. Revalidate each artifact immediately before its operation.

### F2 [HIGH] Publication during Status grouping can crash the catalog
- File: installer/catalog_tui.py:103–113; installer/tool_browser.py:198–207
- Problem: Each health bucket independently calls the live state reader. If publication changes a tool from CHECKING to OK between those buckets, the same tool enters both groups. The browser then inserts its row key twice, raising Textual’s `DuplicateKey`. An in-memory reproduction produced both groups for one tool.
- Fix: Capture the states used for a rebuild once, then reuse their health values for grouping and cells. Add a regression test that publishes while Status grouping runs.

### F3 [HIGH] Stale skill-cache answers produce a fresh green check
- File: installer/version_status.py:1175–1186
- Problem: Cached host answers marked `stale=True` still determine presence and health. A cached `"present"` answer therefore becomes an OK state stamped with the current generation before the current skill probe finishes. After invalidation, a removed or disabled pack can again display `✓` while its verification is pending. The stale note does not satisfy the phase’s prohibition on stale green checks.
- Fix: Keep stale host answers informational; publish CHECKING until the current-generation probe supplies fresh answers. Update the tests that currently expect OK from seeded answers.

### F4 [MEDIUM] An invalid receipt path escapes the fail-closed reader
- File: installer/receipts.py:398–406; installer/receipts.py:346–368
- Problem: An absolute artifact path containing JSON-escaped NUL is accepted by `_read_artifact`. Its subsequent `lstat` raises `ValueError`, which `matches` does not catch. This aborts refresh or uninstall instead of treating the receipt as corrupt. The failure was reproduced without filesystem mutation.
- Fix: Reject NUL-containing paths during receipt decoding and make filesystem validation fail closed on invalid-path errors.

### F5 [MEDIUM] The rehash memo reuses proof against a different digest
- File: installer/receipts.py:359–365
- Problem: The memo stores a comparison result keyed only by path, size and mtime—not the expected receipt digest. After a receipt rewrite, restoring an older binary with preserved timestamps can reuse a successful comparison against the previous digest. The changed binary then appears healthy and removable; only deletion-time rehashing rejects it.
- Fix: Include the expected digest in the memo key, or cache the observed digest and compare it with each receipt’s digest.

### F6 [MEDIUM] The skill worker can overwrite newer state without sequence gating
- File: installer/version_status.py:1018–1046
- Problem: `refresh_skills` scans outside the publication lock, then rebuilds whichever state currently exists using that state’s sequence number. A newer full pass can publish an updated project-pack report between those operations; the older skill scan then overwrites it while retaining the newer sequence. An in-memory reproduction replaced a newer “installed in 1 repo” OK state with stale global-leftover facts.
- Fix: Apply sequence ordering to skill-worker publication too, or prevent that worker from rebuilding project facts already owned by the full refresh pass.

### F7 [MEDIUM] Terminal warnings disappear from tool health
- File: installer/version_status.py:1268–1284
- Problem: `_terminal_facts` consumes only `TerminalShellResult.drifted`, discarding `warnings`. For example, an unsupported WezTerm return shape produces a warning and no drift entry, so the terminal can display OK without any “not checked” explanation even though its shell configuration could not be assessed.
- Fix: Convert terminal warnings into the corresponding row’s unchecked notes. Keep an inconclusive check distinct from confirmed absence of drift.

### F8 [MEDIUM] A special file can block skill refresh indefinitely
- File: installer/skill_lifecycle.py:793–798
- Problem: `_installed_project_paths` opens `installed_plugins.json` without checking its type. If that path is a FIFO without a writer, opening it blocks indefinitely before the byte cap helps. This strands the skill worker while it holds the shared skill-pass lock.
- Fix: Open nonblocking, verify with `fstat` that the opened object is a regular file, then perform the capped read. Treat other types as unreadable metadata.

### F9 [LOW] Receipt tests break when the interpreter path contains spaces
- File: tests/test_container_e2e_receipts.py:224–231; tests/test_container_e2e_receipts.py:270
- Problem: `_uv_stub` interpolates `sys.executable` into an unquoted shell `exec`. A checkout or uv interpreter path containing spaces is split into multiple arguments, breaking the test despite correct receipt behavior. The workspace assignment is also interpolated without quoting.
- Fix: Shell-quote both paths with `shlex.quote`.

## Summary

**CRITICAL: 0 · HIGH: 3 · MEDIUM: 5 · LOW: 1**

The three most important fixes:
1. Preserve artifact types through deletion to prevent unauthorized recursive removal.
2. Snapshot rendering inputs so concurrent publication cannot create duplicate catalog rows.
3. Keep stale skill-cache answers from producing current-generation green checks.

Not run: the full test suite, installs, or containers. No files were changed; F1 remains a data-loss risk.
