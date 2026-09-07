---
phase: 07-system-user-tier-catalog-expansion
plan: 01
subsystem: registry
tags: [zsh, oh-my-zsh, registry, tier-3-verification, bazzite, keep-zshrc]

requires:
  - phase: 06-sdkman-hardening-registry-authoring-guidelines
    provides: D-01 dated verification comments and the sdkman detect_path/script precedent
provides:
  - zsh as a verified tier=system catalog entry (dnf/apt/pacman/brew, podman-shaped)
  - oh-my-zsh as a verified tier=system catalog entry (script + KEEP_ZSHRC=yes + requires zsh and git)
  - three-phase Tier-3 proof of install.sh's git prerequisite, .zshrc preservation, and fresh-user template
  - has_brew=False Bazzite boundary naming the existing two-run brew bootstrap
affects:
  - 07-02-PLAN.md (gnu-bash / Apple Containers, same registry.toml)
  - REQ-system-tier-shell-container-entries
  - REQ-linux-bazzite-shell-parity

actuals:
  tokens: 4000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - Immutable-Linux-falls-to-brew four-method shape reused from podman
    - detect_path + env-prefixed script install reused from sdkman/brew
    - requires drag-in of an already-catalogued user-tier tool (git) into a system-tier install

key-files:
  created:
    - .planning/phases/07-system-user-tier-catalog-expansion/07-01-SUMMARY.md
  modified:
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "oh-my-zsh is safe as kind=script only with RUNZSH=no CHSH=no KEEP_ZSHRC=yes set explicitly; OVERWRITE_CONFIRMATION=no means skip the prompt and overwrite, not don't overwrite."
  - "requires = [zsh, git] because install.sh's setup_ohmyzsh() hard-requires git (command_exists git) and clones entirely via git — there is no non-git code path."
  - "CHSH=no is a Bazzite correctness requirement (ublue-os/bazzite#4159), never a style preference."
  - "cmd = zsh needs no false-positive guard: macOS system zsh since Catalina genuinely satisfies Oh-My-Zsh."
  - "Unpinned master/HEAD install.sh is accepted, matching the brew entry's Homebrew/install/HEAD/install.sh precedent."
  - "Fresh immutable Linux with has_brew=False correctly resolves zsh/podman to no method; the bootstrap is this registry's existing unconditional brew script method, then a fresh re-run."

patterns-established:
  - "Pattern 1 reuse: four-method native+brew with no os/arch restriction; immutable skip is generic resolver behavior."
  - "Pattern 2 reuse: detect_path for a non-PATH marker; cmd=omz will not resolve via which."
  - "Registry comments stay concise (load-bearing finding + SUMMARY pointer); the investigation transcript lives here."

requirements-completed:
  - REQ-system-tier-shell-container-entries
  - REQ-linux-bazzite-shell-parity

coverage:
  - id: D1
    description: zsh and oh-my-zsh exist as verified tier=system registry entries with dated comments
    requirement: REQ-system-tier-shell-container-entries
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_oh_my_zsh_requires_zsh_and_sets_safe_env
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_zsh_entry_records_the_podman_pattern_reuse
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_oh_my_zsh_entry_records_the_keep_zshrc_finding
        status: pass
    human_judgment: false
  - id: D2
    description: oh-my-zsh requires zsh and git in deps-first order; KEEP_ZSHRC env is set
    requirement: REQ-system-tier-shell-container-entries
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_selecting_oh_my_zsh_drags_in_zsh_and_git_in_deps_first_order
        status: pass
    human_judgment: false
  - id: D3
    description: Bazzite zsh/podman brew-only parity, plus honest has_brew=False empty-method boundary
    requirement: REQ-linux-bazzite-shell-parity
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_bazzite_zsh_and_podman_both_resolve_brew_only_no_new_entry
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_fresh_bazzite_without_brew_has_no_method_for_zsh_or_podman_yet
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_zsh_resolves_across_platforms_with_immutable_brew_fallback
        status: pass
    human_judgment: false
  - id: D4
    description: Three-phase Tier-3 container proof of git prerequisite, .zshrc preservation, and fresh-user template
    requirement: REQ-system-tier-shell-container-entries
    verification:
      - kind: other
        ref: docker run --rm ubuntu:24.04 with captured _script pipeline (phases 1-3 in this SUMMARY)
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-06
status: complete
---

# Phase 7 Plan 01: zsh + oh-my-zsh system-tier entries

**Verified `zsh` and `oh-my-zsh` catalog entries, with KEEP_ZSHRC=yes proven against a real filesystem and `requires = ["zsh", "git"]` proven both in the resolver and in a disposable ubuntu:24.04 container.**

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-09-06
- **Tasks:** 2
- **Files modified:** 2 production + this SUMMARY

## Accomplishments

- `zsh` and `oh-my-zsh` ship as `tier="system"` registry entries. `zsh` reuses `podman`'s four-method shape (dnf/apt/pacman/brew). `oh-my-zsh` is a `kind="script"` install with `env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }`, `detect_path = "~/.oh-my-zsh/oh-my-zsh.sh"`, and `requires = ["zsh", "git"]`.
- A three-phase Tier-3 container run (colima + docker, `ubuntu:24.04`, captured `_script` pipeline, no `-i`/`-t`, no `< /dev/null`) proved: (1) undeclared git dependency is real, (2) a pre-existing `.zshrc` survives byte-identical with no backup and `CHSH=no` held, (3) a fresh user gets a template `.zshrc` with `source $ZSH/oh-my-zsh.sh` and a single-line `plugins=(git)` array compatible with `installer/omz.py::_PLUGINS_LINE`.
- Seven new registry tests pin resolution shapes, env/requires/detect_path, comment locality, Bazzite `podman` reuse, and the `has_brew=False` fresh-machine boundary. System-tier tripwire moved 22 → 24. Floor-check ids include `zsh` and `oh-my-zsh`.

## Task Commits

1. **Task 1: `zsh` + `oh-my-zsh` registry entries, Tier-3 verification, dated comments** - `86fbd32` (feat)
2. **Task 2: Bazzite system-tier bootstrap floor check and installable-entries floor update** - `b97a0e5` (test)

**Plan metadata:** this SUMMARY commit.

## Files Created/Modified

- `installer/registry.toml` — `zsh` and `oh-my-zsh` `[[tool]]` blocks with `# Verified 2026-09-06` comments
- `tests/test_registry.py` — seven new tests, system-tier count 24, floor-check ids

## Decisions Made

Followed the plan. Extended narrative that the registry comments deliberately omit lives below.

### Why `requires = ["zsh", "git"]`, not `["zsh"]` alone

`install.sh`'s `setup_ohmyzsh()` hard-requires git:

```
command_exists git || { fmt_error "git is not installed"; exit 1; }
```

then clones the framework entirely via `git init` / `git remote add origin` / `git fetch --depth=1 origin` / `git checkout -b`. There is no non-git code path. `git` is already a real catalog tool (`id = "git"`, `tier = "user"`) with dnf/apt/pacman/brew methods; `requires = ["zsh"]` alone would never drag it in. Cross-AI review (codex, cycle 1) found the first draft's Tier-3 container had been manually installing `git` before the tested pipeline, hiding the gap.

Phase 1 of the container run (zsh + curl + ca-certificates only, no git) reproduces that failure. Phase 2 installs exactly the catalog-equivalent order (`apt-get install zsh git curl ca-certificates`) and succeeds.

### Why the three env vars must be explicit

`install.sh`'s non-TTY auto-detection sets `RUNZSH=no` / `CHSH=no` / `OVERWRITE_CONFIRMATION=no` but leaves `KEEP_ZSHRC` at its unsafe default `no`. `OVERWRITE_CONFIRMATION=no` means "skip the prompt and overwrite," not "don't overwrite." A bare `kind="script"` entry would silently back up and replace a user's `.zshrc` on every unattended run. `CHSH=no` is additionally a Bazzite correctness requirement: `ublue-os/bazzite`#4159 ties `chsh`-to-zsh to KDE/SDDM login failures there — never relax it.

`detect_path` short-circuits a second run to `ALREADY_INSTALLED` (same protection `sdkman` already relies on), so `install.sh`'s own non-idempotency is never reached through this project's normal flow.

### Mutable HEAD revision

The install URL points at `ohmyzsh/ohmyzsh/master/tools/install.sh`. That unpinned `master`/`HEAD` risk is accepted, citing the existing `brew` entry's own unpinned `Homebrew/install/HEAD/install.sh` as this project's already-accepted precedent for every `kind="script"` entry. Re-check the KEEP_ZSHRC finding if `install.sh`'s version/logic changes materially.

### Fresh Bazzite without Homebrew

`zsh`/`oh-my-zsh` have no method on `Platform(os="fedora", immutable=True, has_brew=False)` because Homebrew is not yet installed, not because Bazzite is unsupported. Both `zsh` and `podman` resolve to `[]`; selecting `oh-my-zsh` yields `result.order == ()` with a warning that names `zsh` as not available. The fix is running this installer once with only the registry's existing, unconditional `brew` `kind="script"` Linux method selected (it applies regardless of `has_brew`), then re-running the installer in a fresh process, which re-probes `has_brew=True` and unblocks `zsh`/`oh-my-zsh`. This is how every brew-only Linux entry already requires two runs on a truly bare machine — a pre-existing property of the static per-run `Platform` snapshot (`installer/platform.py::detect`, `setup.py::main`), not something these two entries change.

### macOS system zsh is not a false positive

Unlike `gnu-bash` (07-02-PLAN.md), `cmd = "zsh"` needs no false-positive guard. macOS has shipped `zsh` as its default login shell since Catalina, and that system zsh is a real, sufficiently modern build that genuinely satisfies Oh-My-Zsh's own `command_exists zsh` prerequisite check. `is_installed` reporting "already satisfied" on a stock Mac is correct.

## Captured runner-generated pipeline

Once the `oh-my-zsh` entry existed, `_script(method, captured.append)` produced this `sh -c` payload (host `_path_prefix()` PATH export included, then dropped inside the container as specified):

```
PATH=<host-de-shimmed-PATH>; export PATH; curl -fsSL -- https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | CHSH=no KEEP_ZSHRC=yes RUNZSH=no sh
```

Container runs used the captured string from `curl -fsSL --` onward, verbatim:

```
curl -fsSL -- https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | CHSH=no KEEP_ZSHRC=yes RUNZSH=no sh
```

Env-key order is `CHSH`, `KEEP_ZSHRC`, `RUNZSH` because `_env_prefix` sorts by key. No `< /dev/null` anywhere; outer `docker run --rm ubuntu:24.04 sh -c '...'` had no `-i`/`-t`.

## Tier-3 container transcript

All three phases: disposable `ubuntu:24.04`, `--rm`, no `-i`/`-t`. Image digest `sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517`.

### Phase 1 — undeclared git dependency is real

Pre-installed: `zsh curl ca-certificates` only (deliberately no `git`).

```
Selecting previously unselected package zsh-common.
Unpacking zsh-common (5.9-6ubuntu2) ...
Selecting previously unselected package zsh.
Unpacking zsh (5.9-6ubuntu2) ...
Setting up zsh-common (5.9-6ubuntu2) ...
Setting up zsh (5.9-6ubuntu2) ...
===== PHASE 1: pipeline without git =====
Error: git is not installed
Cloning Oh My Zsh...
EXIT_CODE=1
```

Non-zero exit. Output contains the literal `git is not installed` (`install.sh`'s own `fmt_error` from `setup_ohmyzsh()`'s `command_exists git` guard).

### Phase 2 — catalog-equivalent order, pre-existing `.zshrc`

Pre-installed via the real Linux apt methods: `zsh git curl ca-certificates`. Distinctive `.zshrc` written first, copied aside.

```
Selecting previously unselected package git.
Unpacking git (1:2.43.0-1ubuntu7.3) ...
Selecting previously unselected package zsh-common.
Unpacking zsh-common (5.9-6ubuntu2) ...
Selecting previously unselected package zsh.
Unpacking zsh (5.9-6ubuntu2) ...
Setting up zsh-common (5.9-6ubuntu2) ...
Setting up git-man (1:2.43.0-1ubuntu7.3) ...
Setting up zsh (5.9-6ubuntu2) ...
Setting up git (1:2.43.0-1ubuntu7.3) ...
Setting up curl (8.5.0-2ubuntu10.13) ...
===== PHASE 2: pre-existing .zshrc =====
BEFORE_ZSHRC:
# my custom marker
export MY_CUSTOM_VAR=1
LOGIN_SHELL_BEFORE=/bin/bash
Cloning Oh My Zsh...
From https://github.com/ohmyzsh/ohmyzsh
 * [new branch]      add-docker-compose-config -> origin/add-docker-compose-config
 * [new branch]      bugfix/rr-poetry-env-local-venv-dir -> origin/bugfix/rr-poetry-env-local-venv-dir
 * [new branch]      copilot/docker-plugin-load-fix -> origin/copilot/docker-plugin-load-fix
 * [new branch]      copilot/fix-per-directory-history-regression -> origin/copilot/fix-per-directory-history-regression
 * [new branch]      feat/appsignal-cli-plugin -> origin/feat/appsignal-cli-plugin
 * [new branch]      feat/shopify-plugin    -> origin/feat/shopify-plugin
 * [new branch]      feat/systemd-edit-full -> origin/feat/systemd-edit-full
 * [new branch]      fix/agnoster-conda-env-prompt -> origin/fix/agnoster-conda-env-prompt
 * [new branch]      fix/common-aliases-open-command -> origin/fix/common-aliases-open-command
 * [new branch]      fix/duplicate-alias-definitions -> origin/fix/duplicate-alias-definitions
 * [new branch]      fix/emacs-nw-no-wait   -> origin/fix/emacs-nw-no-wait
 * [new branch]      fix/installer-backup-history -> origin/fix/installer-backup-history
 * [new branch]      fix/jonathan-fillbar-locale -> origin/fix/jonathan-fillbar-locale
 * [new branch]      fix/ssh-agent-honor-existing -> origin/fix/ssh-agent-honor-existing
 * [new branch]      fix/termsupport-terminfo-title -> origin/fix/termsupport-terminfo-title
 * [new branch]      fix/vagrant-suspend-rdp-completion -> origin/fix/vagrant-suspend-rdp-completion
 * [new branch]      master                 -> origin/master
 * [new branch]      rr-13813-introduce-cooldown-feature -> origin/rr-13813-introduce-cooldown-feature
 * [new branch]      task/rr-14045-omz-plugin-create -> origin/task/rr-14045-omz-plugin-create
 * [new branch]      update/plugins/gradle/e7c881db -> origin/update/plugins/gradle/e7c881db
Already on 'master'
branch 'master' set up to track 'origin/master'.
/

Looking for an existing zsh config...
Found /root/.zshrc. Keeping...
         __                                     __
  ____  / /_     ____ ___  __  __   ____  _____/ /_
 / __ \/ __ \   / __ `__ \/ / / /  /_  / / ___/ __ \
/ /_/ / / / /  / / / / / / /_/ /    / /_(__  ) / / /
\____/_/ /_/  /_/ /_/ /_/\__, /    /___/____/_/ /_/
                        /____/                       ....is now installed!


Before you scream Oh My Zsh! look over the `.zshrc` file to select plugins, themes, and options.

• Follow us on X: https://x.com/ohmyzsh
• Join our Discord community: https://discord.gg/ohmyzsh
• Get stickers, t-shirts, coffee mugs and more: https://commitgoods.com/collections/oh-my-zsh

Run zsh to try it out.
EXIT_CODE=0
===== DIFF =====
DIFF_EXIT=0
===== BACKUP =====
BACKUP=absent
===== DETECT_PATH =====
DETECT_PATH=present
LOGIN_SHELL_AFTER=/bin/bash
```

`diff /tmp/zshrc.before ~/.zshrc` showed no difference (`DIFF_EXIT=0`). `test -f ~/.zshrc.pre-oh-my-zsh` was false. `test -f ~/.oh-my-zsh/oh-my-zsh.sh` was true. Login shell stayed `/bin/bash` (`CHSH=no` held). `Found /root/.zshrc. Keeping...` is the vendor confirmation that `KEEP_ZSHRC=yes` took effect.

### Phase 3 — fresh user, no pre-existing `.zshrc`

Same packages as Phase 2. Confirmed `~/.zshrc` did not exist before the pipeline.

```
===== PHASE 3: fresh user, no .zshrc =====
PREEXISTING_ZSHRC=no
Cloning Oh My Zsh...
From https://github.com/ohmyzsh/ohmyzsh
 * [new branch]      add-docker-compose-config -> origin/add-docker-compose-config
 * [new branch]      bugfix/rr-poetry-env-local-venv-dir -> origin/bugfix/rr-poetry-env-local-venv-dir
 * [new branch]      copilot/docker-plugin-load-fix -> origin/copilot/docker-plugin-load-fix
 * [new branch]      copilot/fix-per-directory-history-regression -> origin/copilot/fix-per-directory-history-regression
 * [new branch]      feat/appsignal-cli-plugin -> origin/feat/appsignal-cli-plugin
 * [new branch]      feat/shopify-plugin    -> origin/feat/shopify-plugin
 * [new branch]      feat/systemd-edit-full -> origin/feat/systemd-edit-full
 * [new branch]      fix/agnoster-conda-env-prompt -> origin/fix/agnoster-conda-env-prompt
 * [new branch]      fix/common-aliases-open-command -> origin/fix/common-aliases-open-command
 * [new branch]      fix/duplicate-alias-definitions -> origin/fix/duplicate-alias-definitions
 * [new branch]      fix/emacs-nw-no-wait   -> origin/fix/emacs-nw-no-wait
 * [new branch]      fix/installer-backup-history -> origin/fix/installer-backup-history
 * [new branch]      fix/jonathan-fillbar-locale -> origin/fix/jonathan-fillbar-locale
 * [new branch]      fix/ssh-agent-honor-existing -> origin/fix/ssh-agent-honor-existing
 * [new branch]      fix/termsupport-terminfo-title -> origin/fix/termsupport-terminfo-title
 * [new branch]      fix/vagrant-suspend-rdp-completion -> origin/fix/vagrant-suspend-rdp-completion
 * [new branch]      master                 -> origin/master
 * [new branch]      rr-13813-introduce-cooldown-feature -> origin/rr-13813-introduce-cooldown-feature
 * [new branch]      task/rr-14045-omz-plugin-create -> origin/task/rr-14045-omz-plugin-create
 * [new branch]      update/plugins/gradle/e7c881db -> origin/update/plugins/gradle/e7c881db
Already on 'master'
branch 'master' set up to track 'origin/master'.
/

Looking for an existing zsh config...
Using the Oh My Zsh template file and adding it to /root/.zshrc.

         __                                     __
  ____  / /_     ____ ___  __  __   ____  _____/ /_
 / __ \/ __ \   / __ `__ \/ / / /  /_  / / ___/ __ \
/ /_/ / / / /  / / / / / / /_/ /    / /_(__  ) / / /
\____/_/ /_/  /_/ /_/ /_/\__, /    /___/____/_/ /_/
                        /____/                       ....is now installed!


Before you scream Oh My Zsh! look over the `.zshrc` file to select plugins, themes, and options.

• Follow us on X: https://x.com/ohmyzsh
• Join our Discord community: https://discord.gg/ohmyzsh
• Get stickers, t-shirts, coffee mugs and more: https://commitgoods.com/collections/oh-my-zsh

Run zsh to try it out.
EXIT_CODE=0
===== ZSHRC EXISTS =====
ZSHRC=present
===== ZSHRC CONTENTS =====
# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time Oh My Zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="robbyrussell"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(git)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='nvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch $(uname -m)"

# Set personal aliases, overriding those provided by Oh My Zsh libs,
# plugins, and themes. Aliases can be placed here, though Oh My Zsh
# users are encouraged to define aliases within a top-level file in
# the $ZSH_CUSTOM folder, with .zsh extension. Examples:
# - $ZSH_CUSTOM/aliases.zsh
# - $ZSH_CUSTOM/macos.zsh
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
===== DETECT_PATH =====
DETECT_PATH=present
```

Exit 0. `~/.zshrc` created from the default template. It sources Oh-My-Zsh (`source $ZSH/oh-my-zsh.sh`) and contains a single-line `plugins=(git)` array matching `installer/omz.py::_PLUGINS_LINE`. `~/.oh-my-zsh/oh-my-zsh.sh` present.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `uv run pytest` via rtk was sandbox-rejected as an `external_directory` permission request; validation used `make validate` and `make test` as specified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 07-02-PLAN.md (`gnu-bash` + Apple Containers). Same-file dependency on `installer/registry.toml` / `tests/test_registry.py`; sequential wave 2. Partial SC#1 (shell/shell-framework half) and SC#3 are satisfied; `gnu-bash` and Apple Containers remain 07-02.

---
*Phase: 07-system-user-tier-catalog-expansion*
*Completed: 2026-09-06*
