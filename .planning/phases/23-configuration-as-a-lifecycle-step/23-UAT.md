---
phase: 23-configuration-as-a-lifecycle-step
status: issues_found
tested_at: 2026-11-07T10:07:00Z
environment: >-
  Disposable podman container ti-uat-23 (registry.fedoraproject.org/fedora:latest, Fedora 44, amd64),
  built like scripts/container-e2e-verify.sh bootstrap (dnf prereqs + tmux, user tester with the
  e2e sudoers entry, Homebrew-on-Linux + uv bootstrapped, host gh token streamed to
  ~/.github-token and exported as GITHUB_TOKEN), repo copied with `git archive a30bb2f`, scratch
  HOME /home/tester. zsh was not preinstalled: the installer plans it as `manual`, so the UAT ran
  that command as the container's root (see Setup). TUI driven with tmux at 80x20 with NO_COLOR=1;
  evidence is `tmux capture-pane -p`. Container removed with `podman rm -f ti-uat-23`; `podman ps -a`
  afterwards listed only unrelated containers and the parallel tools-installer-e2e one. Nothing
  ran on the developer host except podman, git archive and reading the repo.
source: [23-UI-SPEC.md (with the 2026-11-06/07 amendments), 23-VERIFICATION.md human_verification, 23-REVIEW-FIX.md]
---

# Phase 23 — Container UAT

Five of the six behaviours pass. Test 2 fails on one point: in the TUI, the shell-init question
selects **yes** by default (F-1). Everything else in that test works. Five findings are recorded
below (two medium, three low) and returned for triage, not fixed here.

## Setup

- Bootstrap as in `container-e2e-verify.sh` (dnf `@development-tools … nodejs chromium` + `tmux`,
  `useradd tester`, sudoers entry, Homebrew + uv, `uv sync`).
  - One UAT-harness slip was fixed inside the container before any test: the bootstrap had
    appended `.bash_profile` into `.bashrc`, and that recursion crashed `su -`. The product was
    not involved.
- Legacy alias blocks planted in `~/.myshellrc` before the first launch (test 4).
- Headless `setup.py --categories shell --yes` (starship, direnv, gum installed). zsh plans as
  `manual — needs sudo (never run here); you run: `sudo dnf install zsh``.
  - The UAT then ran `dnf install -y zsh` as the container's root, standing in for the user.
    The zsh brew method is never reached on Fedora.
- Headless `setup.py --categories terminal --yes` (kitty, wezterm).
- Disposable agent configs created **before** any agent install, with copies saved in
  `~/.uat-orig/`:
  - `~/.claude/settings.json`: JSON with unrelated keys and the user's own
    `"defaultMode": "acceptEdits"`.
  - `~/.codex/config.toml`: comments plus a `[profiles.fast]` table.
  - `~/.config/opencode/opencode.jsonc`: `//` and `/* */` comments.
  - `~/.cursor/cli-config.json`: `"approvalMode": "unrestricted"`, already set by the user.
- TUI installs:
  - zsh RECONFIGURE.
  - zoxide + fzf.
  - direnv reinstall.
  - claude, codex, opencode, cursor-agent, with auto-approve + attribution off turned on.
  - codegraph.
  - claude again, with no options.

## Results

| # | Test | Result |
|---|------|--------|
| 1 | Run options in the execute review at 80x20 (`space` toggles; pi note; plan-row and post-start refusals); headless `--yes` sets none and says so | PASS |
| 2 | Shell-init prompt: default no; yes writes the managed block; `bash -n`/`zsh -n`; removing the tool removes its block | FAIL (F-1: the TUI default is yes; the rest passes) |
| 3 | Agent settings: only documented keys added; Policies off reverts; `● [yours]` refuses; uninstall reverts; byte-for-byte back where the user did not edit | PASS |
| 4 | Legacy alias strip: TUI and headless notices, blocks gone, nothing written to agent settings, second launch silent | PASS |
| 5 | zsh / SHELL: managed `~/.zshenv` block, `Shell:` lines (TUI report + notice, CLI after report); uninstall never writes `~/.zshenv`; zsh removal strips it | PASS |
| 6 | Uninstall confirmation: settings revert lines, `reverts only keys …` pseudo-row, codegraph unregister line (TUI + CLI) | PASS |

## Evidence

### 1. Run options

The review with claude, codex, opencode, cursor-agent, pi (+pnpm) and vscode, after `End`. Every
row was toggled with `space`:

```
▊ run options — off unless you turn them on with space                         ▎
▊ [x] auto-approve agents — claude, codex, opencode, cursor-agent: no          ▎
▊     permission prompts                                                       ▎
▊     pi: nothing written; its approvals come only from extensions             ▎
▊ [x] attribution off — claude, cursor-agent: no agent credit in commits/PRs   ▎
▊     no documented key: codex, opencode, pi (nothing written for them)        ▎
▊     cursor-agent: its CLI ignores the commit opt-out (as of 2026-10-04)      ▎
▊ [x] VS Code lean mode — telemetry, experiments, minimap, auto-detect off     ▎
▊     zsh terminal; update.mode not written on Linux (this installer updates   ▎
▊     it)                                                                      ▎
▊ [x] VS Code built-in AI off — chat.disableAIFeatures                         ▎
▊ [x] VS Code extension auto-update off — security fixes only on demand        ▎
 enter start · space option · up/down move · esc cancel
```

- A second `space` turned the last row back to `[ ]`.
- Moving up skips the disabled heading.
- Without pi in the plan, the pi note is gone and the no-key note reads `codex, opencode`.
- The zsh RECONFIGURE review shows only the Linux option:
  `[ ] SHELL=zsh for desktop apps — ~/.config/environment.d (log in again)`.
- `space` on a plan row: `space toggles run options only; plan rows change with r.`
- `space` after `enter`: `A run option is set before start; it cannot change now.`
- A zoxide + fzf plan has no trigger. It showed no heading, and the keys line stayed
  `enter start · up/down move · esc cancel`.

Headless `--yes`:

```
Install plan — 2 will install, 1 manual
○ kitty      will install — not installed
○ wezterm    will install — not installed
Run options left off (--yes never turns them on); change them in Policies.
…
Shell init left off (--yes): starship, direnv. Turn it on in Policies.   (shell-category run)
```

- The shell-category run had no option trigger: zsh was `manual`, not runnable. It printed no
  `Run options left off` line, as the spec requires.
- No environment.d file was written by `--yes`. The one on disk came from the earlier TUI
  opt-in.

### 2. Shell-init prompt

```
 fzf Turn on fzf shell init? It adds one guarded block to ~/.myshellrc that
 fzf adds ctrl+r history search, ctrl+t file picker and alt+c. It stays off
     unless you choose yes; Policies can change it later.
    ╭──────────────────────────────────────────────────────────────────────╮
    │Yes, turn it on                                                       │
    │No, leave it off                                                      │
 Run paused on a question for fzf; answer the prompt to continue.
```

- **fzf: `enter` with no navigation → block written** (F-1).
- zoxide: yes.
- direnv (`r` reinstall): `No, leave it off` → no block, no handoff line.

The report showed `fzf — after install:` / `zoxide — after install:` and
`  Shell init on: open a new terminal to use it.`

```
> # >>> tools-installer tweak:zoxide >>>
> if command -v zoxide >/dev/null; then
>   if [ -n "$ZSH_VERSION" ]; then eval "$(zoxide init zsh)"
>   elif [ -n "$BASH_VERSION" ]; then eval "$(zoxide init bash)"; fi
> fi
> # <<< tools-installer tweak:zoxide <<<
BASH_N_OK
ZSH_N_OK
z is a function            (bash -ic)
z: function / __zoxide_z: function, 4 fzf bindkeys   (zsh -ic)
```

Removing zoxide in Uninstall:

```
          │  Remove 1 tool(s)?                                       │
          │  This deletes installed artifacts and is not undoable.   │
          │  zoxide: turns off its shell init in ~/.myshellrc        │
          │  enter remove · esc cancel                               │
 1 removed
 Shell init turned off for zoxide.
```

Afterwards only the fzf block remains, and `bash -n` / `zsh -n` still pass. The CLI sweep later
printed `fzf: turns off its shell init in ~/.myshellrc` and `Shell init turned off for fzf.`, and
left no `tweak:` marker.

### 3. Agent settings

Run report after installing the four agents with both options on:

```
 Agent and editor settings
 codex — ~/.codex/config.toml:
   wrote approval_policy
   wrote sandbox_mode
 claude — ~/.claude/settings.json:
   set by you: permissions.defaultMode = "acceptEdits" (left as is)
   wrote skipDangerousModePermissionPrompt
   wrote attribution.commit
   wrote attribution.pr
 opencode — ~/.config/opencode/opencode.jsonc:
   wrote permission
 cursor-agent — ~/.cursor/cli-config.json:
   already set: approvalMode
   replaced CLI default: attribution.attributeCommitsToAgent = true
   replaced CLI default: attribution.attributePRsToAgent = true
   revert restores the replaced defaults
 cursor-agent: the Cursor CLI ignores the commit opt-out (as of 2026-10-04)
 codex, opencode: no documented attribution key; nothing written
```

`diff -u` against the originals shows only the documented keys:

```
claude:   +  "attribution": {"pr": "", "commit": ""},
          +  "skipDangerousModePermissionPrompt": true,
codex:    +approval_policy = "never"
          +sandbox_mode = "danger-full-access"        (top level, before [profiles.fast]; tomllib parses it)
opencode: +  "permission": "allow",                   (both comments kept)
```

- The cursor-agent CLI itself rewrote `cli-config.json` during its install. It added
  `permissions`, `display`, `sandbox` and others, with `attribution …: true`.
- The installer then changed only the two attribution values to `false`.

Policies (rows in order; all four alias rows gone):

```
 ● [on]     fzf shell init                fzf
 ● [on]     claude auto-approve           claude              agent settings:
 ● [on]     claude attribution off        claude              agent settings:
 ● [on]     codex auto-approve            codex               agent settings:
 ● [on]     opencode auto-approve         opencode            agent settings:
 ● [yours]  cursor-agent auto-approve     cursor-agent        agent settings:
 ● [on]     cursor-agent attribution off  cursor-agent        agent settings:
 ○ [off]    VS Code lean mode             missing: vscode     editor settings:
 ● [on]     SHELL for desktop apps        zsh                 desktop session:
```

```
 Already this way: approvalMode (not written, so space never removes them).
 cursor-agent auto-approve: you set these keys yourself; edit
 ~/.cursor/cli-config.json to change them.                    (file cmp-identical after)
 Set by you: permissions.defaultMode = "acceptEdits" (left as is).
 claude auto-approve disabled.
 ~/.claude/settings.json: removed skipDangerousModePermissionPrompt
 claude attribution off disabled.
 ~/.claude/settings.json: removed attribution.pr, attribution.commit
 opencode auto-approve disabled.
 ~/.config/opencode/opencode.jsonc: removed permission
 codex auto-approve disabled.  /  codex auto-approve enabled.   (off, then on again)
```

After the Policies toggles, `cmp` reported `CLAUDE_BYTE_IDENTICAL`, `OPENCODE_BYTE_IDENTICAL` and
`CODEX_BYTE_IDENTICAL` (codex checked before it was re-enabled).

Next, a user edit (`sandbox_mode = "workspace-write"` by hand), then Uninstall of the four
agents:

```
          │  codex: removes approval_policy, sandbox_mode from       │
          │    ~/.codex/config.toml                                  │
          │  cursor-agent: removes                                   │
          │    attribution.attributeCommitsToAgent,                  │
          │    attribution.attributePRsToAgent from                  │
          │    ~/.cursor/cli-config.json                             │
 4 removed
 Settings reverted for codex, cursor-agent.
 Kept settings you changed since this installer wrote them: codex.
```

Final state against the originals:

```
=== .claude/settings.json            BYTE_IDENTICAL
=== .config/opencode/opencode.jsonc  BYTE_IDENTICAL
=== .codex/config.toml               3a4 > sandbox_mode = "workspace-write"   (the user's own edit, kept)
=== .cursor/cli-config.json          vs the CLI-rewritten file: attribution values back to true (the replaced CLI defaults)
```

### 4. Legacy alias strip

First TUI launch, before the link-mode choice, with `claude-skip` and `cursor-agent-model`
blocks planted:

```
 Removed the claude-skip alias; turn on claude auto-approve in Policies.
 cursor-agent-model alias removed: pick the model with /model in cursor-agent.
```

- `diff` against the planted rc shows only the two blocks removed. The user lines `FOO`
  and `ll` are kept.
- `~/.claude`, `~/.cursor`, `~/.codex` and `~/.config/opencode` did not exist afterwards.
- The second launch printed no alias line.

Headless run (with `codex-skip` and `opencode-auto` planted):

```
Removed the codex-skip alias; turn on codex auto-approve in Policies.
Removed the opencode-auto alias; turn on opencode auto-approve in Policies.
Install plan — 3 will install, …
```

The rc had no `tweak:` marker left, and no agent directory was created.

### 5. zsh / SHELL

After the user ran `sudo dnf install zsh` (here, root in the container), the System view showed:

```
 [ ]  P1   zsh              shell    human  ≈       5.9     dnf             Fe
 ≈ needs configuration — ~/.zshenv does not export SHELL as zsh · managed by
 dnf — this installer will not update it · …
```

```
 Install plan — 1 will reconfigure
▊ ≈ zsh  will reconfigure — ~/.zshenv does not export SHELL as zsh             ▎
▊        to configure: export SHELL=/usr/bin/zsh in ~/.zshenv                  ▎
 Summary — 1 reconfigured
 Shell
 ~/.zshenv now exports SHELL; new terminals start with it.
   SHELL=/usr/bin/zsh
```

```
# >>> tools-installer shell >>>$
export SHELL=/usr/bin/zsh$
# <<< tools-installer shell <<<$
~/.config/environment.d/52-tools-installer-desktop-shell.conf: SHELL=/usr/bin/zsh   (desktop-shell option on)
```

Post-run TUI notice: `~/.zshenv` was emptied by hand, then the zoxide + fzf run, then close:

```
 Shell: ~/.zshenv now exports SHELL=/usr/bin/zsh; new terminals start with it
```

The CLI prints its line after the run report (terminal category):
`Shell: kitty, wezterm now start zsh`. The kitty region holds `shell /usr/bin/zsh -l` and
`env SHELL=/usr/bin/zsh`.

Uninstall never writes `~/.zshenv`:

- `~/.zshenv` was emptied while zsh was still present.
- TUI removal of wezterm, then `setup.py --uninstall --yes` (full sweep): after both,
  `stat` reads `0 2026-11-07 10:05:13.350764934` (size 0, mtime unchanged).

zsh removal strips the block:

- The block was restored under a user line, then zsh removed with `dnf remove zsh`. zsh is
  dnf-owned, so the installer never removes it itself.
- The next run (`--categories text --yes`) printed:

```
Terminal shell synchronization warning: zsh is no longer present; reverted zshenv, kitty, wezterm
export EDITOR=vim  # mine$
$
```

### 6. Uninstall confirmation, settings revert and hook unregister

codegraph with present hosts. The install report:
`codegraph: registered for claude, codex, cursor-agent, opencode`. The receipt records
`"hooks": {"codegraph-mcp-register": ["claude", "codex", "cursor", "opencode"]}`.

Uninstall rows:

```
 installed by this installer: receipt matches — unregisters it from claude,
 codex, cursor-agent, opencode first
 [ ]  agent/editor settings              env       shell config   keys this in…
 reverts only keys that still hold this installer's value:
 ~/.claude/settings.json
 This row has no config to delete.            (c on the pseudo-row)
```

```
          │  Remove 1 tool(s), the agent/editor settings?            │
          │  This deletes installed artifacts and is not undoable.   │
          │  codegraph: runs codegraph uninstall --target            │
          │    claude,codex,opencode,cursor --location global --yes  │
          │    --keep-cli                                            │
          │  claude: removes attribution.commit, attribution.pr      │
          │    from ~/.claude/settings.json                          │
 1 removed
 Unregistered from agent hosts: claude, codex, cursor-agent, opencode.
 Settings reverted for claude.
```

CLI `--uninstall` preview (answered `n`):

```
codegraph: runs codegraph uninstall --target claude,codex,opencode,cursor --location global --yes --keep-cli
fzf: turns off its shell init in ~/.myshellrc
claude: removes attribution.commit, attribution.pr from ~/.claude/settings.json
Agent and editor settings this installer wrote (reverted):
  ~/.claude/settings.json: attribution.commit, attribution.pr
```

After the removal:

- `~/.claude/settings.json` is byte-identical to the user's original.
- codex `config.toml` matches its pre-codegraph copy.
- No `codegraph` string is left in `~/.claude.json`, the opencode file or the cursor files.
- Binary, opt dir and receipt are gone.

## Findings (not fixed; for triage)

**F-1 (medium) — the TUI shell-init modal selects "Yes" by default.**

- Steps: stage fzf in the TUI, press `enter` to start, then press `enter` on the
  `Turn on fzf shell init? …` modal without moving.
- Expected: default no. The SPEC says shell init is off unless the user says yes, and the
  headless prompt and `SensitivePrompt.default` are `False`. "It stays off unless you choose
  yes".
- Actual: `# >>> tools-installer tweak:fzf >>>` is written to `~/.myshellrc` and the report says
  `Shell init on: open a new terminal to use it.`
- Source: `SensitiveActionScreen.compose` (`installer/execute_screen.py`) yields `opt-yes` first,
  and the `ListView` starts on index 0. The prompt's `default` is never consulted.
- The same holds for `set_login_shell`, a pre-existing Phase 13 surface.

**F-2 (medium) — codegraph registration writes a Claude prompt hook and a `CLAUDE.md`
despite `--no-permissions`.**

- Steps: with `~/.claude` present, install codegraph.
- Expected: per `_codegraph_register`'s docstring (`installer/postinstall.py:112-118`),
  `--no-permissions` limits the call to MCP registration, without codegraph's auto-allow list and
  UserPromptSubmit hook.
- Actual: `~/.claude/settings.json` gains
  `"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "codegraph prompt-hook"}]}]}`,
  and `~/.claude/CLAUDE.md` (806 bytes) is created. Both mtimes are 09:59:36, the codegraph
  install. A no-option claude reinstall at 10:01 wrote nothing.
- codegraph's own uninstall removes both, so the file came back byte-identical.
- While codegraph is installed, a hook the installer says it avoids runs on every Claude
  prompt.

**F-3 (low, copy) — the removal preview promises to remove a key the revert will keep.**

- Steps: install codex with auto-approve, change `sandbox_mode` by hand, then open Uninstall
  for codex (TUI or CLI).
- Actual preview: `codex: removes approval_policy, sandbox_mode from ~/.codex/config.toml`.
- The revert then keeps `sandbox_mode` and reports
  `Kept settings you changed since this installer wrote them: codex.`
- The preview lists the ledger entries without checking that they still hold this installer's
  value. The pseudo-row's own detail promises exactly that check:
  `reverts only keys that still hold this installer's value`.

**F-4 (low, copy) — the desktop SHELL conf carries the cache-redirect header.**
`~/.config/environment.d/52-tools-installer-desktop-shell.conf` starts with
`# tools-installer: cache-redirect`, followed by the correct desktop-shell comment lines. If the
header is only the shared ownership marker of `write_linux_redirect`, it misnames this file.

**F-5 (low, cosmetic) — block strips leave blank-line residue.**

- `apply_block` writes a blank separator before each block, and `strip_block` removes only the
  marker-to-marker lines.
- Stripping the two legacy alias blocks left three consecutive blank lines in `~/.myshellrc`.
- Stripping the `~/.zshenv` block left a trailing blank line after the user's line.
- Repeated on/off cycles grow the gaps.

**Observations (outside Phase 23 or already known):**

- **opencode bin dir.** opencode's removal leaves an empty `~/.opencode/bin`. The next PATH
  wiring adds it to the managed block, and the audit then reports
  `/home/tester/.opencode/bin not on PATH`. The `~/.opencode` / `~/.config/opencode` markers also
  keep opencode "present", so codegraph registered for opencode, codex and cursor after their CLIs
  were removed. That is the documented `register_hooks` shortcut.
- **80x20 Policies.** While a two-line status is shown, the Policies table has no visible row.
  This is the known 80x20 layout todo.
- **cursor-agent CLI rewrites.** The cursor-agent CLI rewrites `~/.cursor/cli-config.json` at
  install (about 30 default keys), so that file cannot return to the user's hand-written bytes.
  The installer only replaced and restored the two attribution defaults, as ledger Q5 intends.
- **Uninstall confirm default.** The CLI `--uninstall` confirm defaults to `(Y/n)`. That is a
  Phase 22 surface.
- **zsh on Fedora.** The zsh method order (`dnf` first) means Fedora always gets the `manual`
  dnf command. The brew method is never a fallback.

## Not exercised / human-only

- **VS Code settings writes.** Lean mode, AI off and ext-update off were not written because
  VS Code was not installed: only their option rows and toggles were checked. The integrated
  terminal opening zsh needs the real app.
- **pi.** pi needs an interactive `host_setup`. Only its review note was checked.
- **Real desktop terminals.** A real kitty / WezTerm / Konsole launch (`echo $SHELL` in a new
  window) and a real desktop login for `environment.d` need a desktop.
- **Colour.** True-colour look of `[x]`, `● [yours]`, `≈` and the warn-coloured `Shell:`
  notice; this run used NO_COLOR=1.
- **macOS.** bash 3.2 parsing of the six bundles, `update.mode = none`, terminal sync skipped.
- **Not in this brief.** starship + Oh-My-Zsh theme handoff, the tealdeer cache step,
  unparsable-file (O7) states and the DRIFT state.

## Fixes

Applied on main after the UAT, each test-first in one commit with its test; `make validate` and
`make test` passed on every commit's tree.

| Finding | Status | Commit |
|---------|--------|--------|
| F-1 shell-init modal defaults to yes | Fixed: `SensitiveActionScreen` starts on the prompt's declared `default` (shell init: no; login shell: yes) | 18ab7f2 |
| F-2 codegraph writes a Claude prompt hook and `CLAUDE.md` | Fixed (disclosure): docstring and registry comment corrected; the Agent-host hooks section adds `  claude: codegraph also adds a prompt hook and ~/.claude/CLAUDE.md` when codegraph registers for claude. codegraph has no flag to skip them; registration is unchanged | 1647b8a |
| F-3 removal preview promises a changed key | Fixed: a shared `key_held` check backs the revert and `ledger_preview`; the preview lists only keys still holding this installer's value and adds `<agent>: keeps <keys>, changed since this installer wrote it`; the CLI reverted-settings listing shows only held keys | 8fe4a27 |
| F-4 desktop SHELL conf carries the cache-redirect header | Fixed: the conf writes `# tools-installer: desktop-shell`; ownership accepts both headers, so confs already on disk stay owned | c478d82 |
| F-5 blank-line residue after a block strip | Residual: dropping the separator in the shared `strip_block` breaks the existing byte-exact `test_remove_rc_redirect_strips_only_the_block`, which pins the separator that stays (`"export EDITOR=vim\n\n"`). Per the triage rule it is left as is | none |
| O-1 blocking launch read of `~/.myshellrc` | Fixed: `bundle_marker_present` (behind the policy probes and omz's default theme) uses `read_capped`, so a FIFO or oversize file reads as no marker | 98c274d |
| O-2 CLI Shell lines unsanitized | Fixed: `render_shell_section` passes both lines through `sanitize_log_line` | 68566c2 |

Not covered: a codegraph claude registration reached through a RECONFIGURE row (not a fresh
install or a new-host sweep) shows only its row detail `registered for claude`, without the F-2
disclosure line.
