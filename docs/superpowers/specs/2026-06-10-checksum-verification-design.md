# Design: sha256 checksum verification for github_release downloads

Date: 2026-06-10
Status: approved

## Problem

Every `github_release` download is installed without integrity verification: a
truncated transfer, corrupted cache, or tampered-with proxy response goes
straight into `~/.local/bin`. Most upstream releases publish sha256 checksums;
the installer ignores them. This is the catalog's notable security gap.

## Scope and honesty

This verifies **integrity, not authenticity**. The checksum file is fetched
from the same GitHub release as the asset, so a compromised release would ship
matching bad checksums. Signature verification (`.sig`/`.pem`, minisign,
cosign) is out of scope — it needs key management and new dependencies.
Integrity verification is still the standard first hardening step and catches
the realistic failure class (corruption, truncation, in-path tampering).

Scope is `github_release` methods only. The `tarball` kind has zero registry
entries today; declaring `checksum` on one is not supported (and a structural
test pins that `checksum` appears only on `github_release` methods).

## Decisions (user-confirmed)

| Decision | Choice |
|---|---|
| On mismatch (interactive) | Ask the user: retry / skip / continue via fallback |
| On mismatch (unattended `--yes` / bootstrap) | Hard-fail that tool, no fall-through; other tools continue; reported in summary |
| Tools without published checksums | Opt-in per registry method + visible `unverified` marker on download result lines |
| Coverage | Mechanism + full sweep: declare `checksum` for every registry tool whose release ships one, live-verified |
| Where verification runs | Python (`hashlib`) over Runner-downloaded temp files — Approach A |

## Architecture

### New pure module: `installer/checksums.py`

- `class ChecksumMismatch(Exception)` — carries tool/asset, expected and
  actual digests. Deliberately **not** a subclass of `ExecutorError`, so the
  engine's generic fall-through `except` cannot swallow it.
- `expected_sha256(text: str, asset: str) -> str | None` — pure parser over
  checksum-file content. Handles the three wild formats:
  - multi-line `<hash>  <name>` (including the `*<name>` binary marker),
  - single-line sidecar (`<hash>  <name>` or bare `<hash>`),
  - bare-hash files.
  Returns `None` when the asset has no entry.
- `sha256_file(path: Path) -> str` — streaming `hashlib.sha256` digest.

### Registry param

Optional `checksum` on `github_release` methods: an asset-name template
rendered exactly like `asset` (`{ver}`, `{arch.*}`), plus a new `{asset}`
token that expands to the already-rendered asset name (substituted before
`render_asset` runs):

```toml
checksum = "{asset}.sha256"               # sidecar (ripgrep, starship, ruff)
checksum = "{asset}.sha256sum"            # sidecar (deno)
checksum = "gitleaks_{ver}_checksums.txt" # multi-line file
checksum = "checksums.txt"                # multi-line file (lazygit, gum)
```

The checksum file URL is built the same way as the asset URL
(`releases/download/<tag>/<rendered-checksum-name>`). No model-layer change:
`checksum` rides in the generic `params` dict like `asset`/`member`.

### Verified flow in `download.py`

Only when `checksum` is declared. Tools without it keep today's byte-identical
commands (zero regression; existing argv-assertion tests untouched).

1. Python creates a temp dir (`tempfile.mkdtemp`); everything below is wrapped
   in `try/finally → shutil.rmtree`.
2. One Runner call curls **both** the asset and the checksum file into the
   temp dir (`curl -fsSL -o <tmp>/<asset> -- <url> && curl -fsSL -o
   <tmp>/<checkfile> -- <checksum-url>`).
3. Python reads the checksum file and looks up the expected hash for the
   rendered asset name. **Missing entry → `ExecutorError`** (registry/upstream
   drift; an ordinary failure that falls through to brew).
4. Python hashes the downloaded asset. **Digest differs → raise
   `ChecksumMismatch`** (the tampering/corruption signal; stops the ladder).
5. On match, the existing extraction runs from the verified temp file:
   `tar -xzf <tmp>/<asset>` / `unzip -q -o <tmp>/<asset> <member>`; `raw`
   assets are installed into the bin dir from the temp path and `chmod +x`-ed.
6. `install_download` returns `verified: bool` so the outcome can surface it.

The severity split in steps 3–4 is deliberate: an asset absent from the
checksums file is a metadata problem (upstream renamed something) and should
degrade like any method failure; a present-but-wrong hash is the actual
security signal and must not silently fall through.

### Engine policy (`engine.py`)

- `Status` gains `"checksum-mismatch"`; `InstallOutcome` gains
  `verified: bool = False`.
- `install_tool(..., checksum_policy: Literal["fail", "continue"] = "fail")`:
  - `"fail"` (default): on `ChecksumMismatch`, return
    `InstallOutcome(tool.id, "checksum-mismatch", errors=(exc,))`
    immediately — **no fall-through**. Other tools in the run are unaffected.
  - `"continue"`: the mismatch is appended to `errors` like any failure and
    the ladder proceeds (brew backstop). Only ever set by an explicit human
    choice.

### Interactive prompt (composition-root seam)

`app.run_wizard` accepts an `on_mismatch` callback (default: keep the
hard-fail outcome). `setup.py` supplies the real `questionary.select` with:

1. **Retry** — transient corruption is common; re-run `install_tool` once
   with the same (default) policy.
2. **Skip this tool** — keep the `checksum-mismatch` outcome.
3. **Continue via fallback** — re-run with `checksum_policy="continue"`;
   the download re-verifies, and if it still mismatches brew takes over.

Unattended (`--yes` / curl|sh bootstrap): the callback never fires; the
default hard-fail stands and the summary reports it. All questionary IO stays
in `setup.py` (out of coverage by design); the policy logic stays in tested
`installer/` code.

### UI markers (`render.py`)

- Download-method result lines: `sha256 ✓` when verified, `unverified` when no
  checksum is declared.
- Mismatch renders as a distinct error line naming expected vs actual digests
  (first 8 hex chars each).
- brew/native/script lines get **no** marker — those channels perform their
  own integrity checks, so labeling them `unverified` would mislead.

## Registry sweep

For each of the ~33 `github_release` tools, live-verify against the latest
release (`gh api repos/OWNER/REPO/releases/latest`):

1. Does a checksum asset exist?
2. Pick the template form (sidecar vs named file).
3. Download the actual checksum file once and confirm `expected_sha256` finds
   our asset's entry.

Known from sampling (2026-06-10): ripgrep/starship/ruff ship `.sha256`
sidecars; deno ships `.sha256sum` sidecars; fzf/gh/lazygit/just/gum/gitleaks
ship multi-line files; fd/delta/xh ship nothing (stay `unverified`). yq's
`checksums` file is a multi-algorithm oddball — if it does not parse cleanly,
yq stays unverified and the catalog says so (no silent caps).

The tool catalog doc gains a **verified** column. Registry count stays 47 —
this work adds no tools.

## Testing (TDD, 100% coverage maintained)

- `tests/test_checksums.py` — pure parser tests: multi-line, `*binary`
  marker, sidecar with/without filename, bare hash, CRLF, uppercase hex,
  asset-not-listed → `None`; `sha256_file` against fixture bytes.
- `download.py` verified flow — mocked Runner asserts exact argv as today;
  the stub additionally **writes fixture files** when it sees the curl argv,
  so Python's hashing runs against real temp files (offline, deterministic).
  Asserts: match → extraction proceeds from the temp path; mismatch →
  `ChecksumMismatch`; missing entry → `ExecutorError`; temp dir removed on
  every path (success, mismatch, runner failure).
- `engine` — `checksum-mismatch` halts the ladder; `checksum_policy=
  "continue"` falls through to brew; `verified` propagates to the outcome.
- `render` — verified/unverified markers and the mismatch error line.
- Registry structural test — `checksum` only on `github_release` methods.

## Out of scope / deferred

- Signature verification (`.sig`, minisign, cosign) — authenticity.
- `tarball`-kind checksum support (no registry entries exist).
- Checksums for `script`-kind installers (bun/pnpm/fnm pipe upstream scripts;
  a different problem class).
