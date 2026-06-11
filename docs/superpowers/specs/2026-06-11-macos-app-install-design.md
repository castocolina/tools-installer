# macOS GUI App Install (`.app` from zip) — Design

Date: 2026-06-11 (Plan 6c)
Status: approved

## Goal

Install macOS GUI apps into `~/Applications` (never `/Applications`, zero sudo) with
their CLI symlinked into `~/.local/bin`, per the PRD's location policy. First batch:
Visual Studio Code and Sublime Text — both zip-distributed, both with a real CLI.

## Decisions (user-approved)

1. **Apps**: VS Code + Sublime Text.
2. **`.dmg` support is deferred** (YAGNI): both apps ship `.zip`; the
   `hdiutil attach/copy/detach` lifecycle gets built when a `.dmg`-only app joins
   the catalog (e.g. Ghostty).
3. **Detection**: installed = the `.app` bundle exists in `~/Applications` **or**
   `/Applications`, **or** the CLI resolves on PATH. A drag-installed system copy
   counts as installed and is never duplicated or touched.
4. **Fallback**: Homebrew cask rung running
   `brew install --cask --appdir=<home>/Applications <cask>` so the
   never-`/Applications` rule holds on the fallback too.
5. **Sublime versioning**: pin the build number in the registry URL. GUI apps
   self-update after first launch, so the pin only affects the initial install;
   bumping is a one-line registry edit.
6. **Approach A**: new `app` method kind in a focused module (`installer/apps.py`)
   plus a one-line `cask` executor in `executors.py` — not a generalization of
   `download.py` (the `.app` flow uses `ditto`, no chmod, bundle-dir artifacts and
   different uninstall paths) and not registry-only `script` blobs (no detection,
   no uninstall, untestable).

## Live-verified facts (2026-06-11)

- VS Code `https://update.code.visualstudio.com/latest/darwin-arm64/stable` → 302 to
  a commit-pinned CDN zip `VSCode-darwin-arm64.zip` (~238 MB). Intel channel is
  `latest/darwin/stable` → `VSCode-darwin.zip` (~247 MB). The universal zip is
  ~358 MB (≈120 MB more per download and ~2× on disk forever) → arch-split URLs win.
  The `latest/...` alias is stable; the redirect target changes per release — never
  pin the final URL.
- VS Code zip top-level entry: `Visual Studio Code.app/` (name contains spaces).
  CLI present at `Contents/Resources/app/bin/code`.
- Sublime ships **one universal mac zip**:
  `https://download.sublimetext.com/sublime_text_build_4200_mac.zip` (~40 MB,
  build 4200 current). Top-level entry: `Sublime Text.app/`. CLI present at
  `Contents/SharedSupport/bin/subl`. The download page builds URLs in JS, so the
  literal URL is not scrapable from HTML — pinning the build is the honest option.
- Brew casks exist: `visual-studio-code`, `sublime-text`.

## Mechanism

### New method kind: `app` (module `installer/apps.py`)

Params:

- `url` — verbatim download URL (no `{ver}`/arch templating; arch handled by the
  method-level `arch` filter below).
- `app` — exact bundle name, e.g. `"Visual Studio Code.app"`.
- `cli` — optional bundle-relative path to the CLI binary, e.g.
  `"Contents/Resources/app/bin/code"`. The symlink name is the path's basename.

Install flow (argv through the injected Runner, like every executor):

1. One `sh -c` pipeline:
   `tmp=$(mktemp -d)` + `trap 'rm -rf "$tmp"' EXIT`
   `&& curl -fsSL -o "$tmp/app.zip" -- <url>`
   `&& ditto -x -k "$tmp/app.zip" "$tmp/x"`
   `&& mv "$tmp/x/<App>.app" <home>/Applications/`
   All interpolated values shlex-quoted. Extract-then-move keeps `~/Applications`
   free of partial bundles on any failure. `ditto -x -k` is the canonical macOS
   extractor for `.app` zips: it preserves the extended attributes and framework
   symlinks that Info-ZIP `unzip` can mangle in Electron-style bundles.
2. `~/Applications` is created first via the existing `ensure_dir`.
3. If `cli` is set:
   `ln -sf <home>/Applications/<App>.app/<cli> ~/.local/bin/<basename(cli)>`
   (bin dir via the existing `locations.bin_dir(None)` + `ensure_dir`).

The engine routes kind `app` to `apps.install_app` (same pattern as
`download.DOWNLOAD_KINDS`); it returns no verified flag semantics — apps are never
checksum-verified (see Error handling).

### New executor: `cask` (in `executors.py`)

One-liner like `_brew`:
`["brew", "install", "--cask", f"--appdir={Path.home() / 'Applications'}", <cask>]`.
Required param: `cask`.

### Resolver

- `app` → rank 20 (userspace download tier), applies unconditionally (the registry's
  `os`/`arch` filters scope it).
- `cask` → rank 40 (brew tier), applies only when
  `platform.os == "macos" and platform.has_brew`.

### New generic `arch` method filter

`Method` gains `arch: tuple[str, ...] = ()` mirroring the existing `os` filter
exactly: same list-required parse validation in `load_tools` (a bare string would
silently iterate per-character), same single check in `resolve._applies` against
`platform.arch` (normalized values: `"amd64"`, `"arm64"`). Motivation: VS Code's arch-split
URLs. The filter is generic and immediately reusable for existing Intel-mac asset
gaps (dust/jless/broot are currently brew-backstopped at the OS level).

### Detection (`status.is_installed`)

`shutil.which(tool.cmd)` **or**, for any `app`-kind method on the tool, the bundle
exists at `~/Applications/<app>` or `/Applications/<app>`. The Applications roots
are injectable for tests (default `(Path.home() / "Applications", Path("/Applications"))`).

## Registry entries (47 → 49 tools, new category `editor`)

```toml
[[tool]]
id = "vscode"
name = "Visual Studio Code"
category = "editor"
cmd = "code"
desc = "Microsoft's extensible code editor"

  [[tool.method]]
  kind = "app"
  os = ["macos"]
  arch = ["arm64"]
  url = "https://update.code.visualstudio.com/latest/darwin-arm64/stable"
  app = "Visual Studio Code.app"
  cli = "Contents/Resources/app/bin/code"

  [[tool.method]]
  kind = "app"
  os = ["macos"]
  arch = ["amd64"]
  url = "https://update.code.visualstudio.com/latest/darwin/stable"
  app = "Visual Studio Code.app"
  cli = "Contents/Resources/app/bin/code"

  [[tool.method]]
  kind = "cask"
  os = ["macos"]
  cask = "visual-studio-code"

[[tool]]
id = "sublime"
name = "Sublime Text"
category = "editor"
cmd = "subl"
desc = "Fast proprietary text editor"

  [[tool.method]]
  kind = "app"
  os = ["macos"]
  url = "https://download.sublimetext.com/sublime_text_build_4200_mac.zip"
  app = "Sublime Text.app"
  cli = "Contents/SharedSupport/bin/subl"

  [[tool.method]]
  kind = "cask"
  os = ["macos"]
  cask = "sublime-text"
```

On Linux both tools resolve to zero applicable methods → the existing `no-method`
outcome (same precedent as gitui on a brew-less Mac). Linux methods (VS Code
tar.gz, Sublime tarball) are a future batch.

## Uninstall

`plan_uninstall` learns `app`-kind methods: plans `~/Applications/<app>` and
`~/.local/bin/<basename(cli)>` (when `cli` is set), with the same exists-or-dangling
filter and the same defensive basename guard against `""`/`"."`/`".."` for both the
bundle name and the cli basename. It **never** plans `/Applications` paths.
Cask-installed apps are left alone, consistent with brew-installed CLIs today.

## Error handling

- Missing/empty `url` or `app` → `ExecutorError` via the existing `require_str`
  (ordinary fall-through to the cask rung).
- curl/ditto/mv failure → non-zero exit breaks the `&&` chain → `CommandError` →
  ordinary fall-through.
- No checksum support for `app`: neither vendor publishes digests for these zips
  (VS Code's update API exposes hashes, but consuming it is future work alongside
  signature verification). App installs simply never appear in the post-install
  verification panel, which iterates `DOWNLOAD_KINDS` only.
- Gatekeeper note: `curl` does not set `com.apple.quarantine`, so installed apps
  launch without the "downloaded from the internet" dialog — identical to
  `brew install --cask` behavior. Documented, intentional.

## Testing

All offline, argv-mock style, 100% coverage gate unchanged:

- `apps.py`: exact `sh -c` pipeline argv (quoting of space-laden bundle names),
  cli-symlink argv, no-cli case, missing-param errors.
- `executors.py`: cask argv including the `--appdir` flag.
- `resolve.py`: arch filter in/out, cask applicability (macos+brew only), ranks.
- `model.py`: `arch` parse + list-required validation error.
- `status.py`: bundle-exists detection with `tmp_path`-faked Applications roots;
  PATH-only detection unchanged for non-app tools.
- `uninstall.py`: app planning (bundle + cli link), `/Applications` never planned,
  basename guards.
- `test_registry.py`: structural tests for the two new tools (kinds, os/arch
  scoping, cask names, category).
- README catalog rows for both tools.

## Out of scope (deferred)

- `.dmg` mounting (`hdiutil`) — until a `.dmg`-only app is added.
- Linux install methods for VS Code / Sublime.
- Checksum/signature verification of app zips (VS Code update API hashes noted).
- Quarantine-xattr opt-in.
