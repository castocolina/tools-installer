# Phase 16 — TUI structural check (tmux, navigation-only)

Date: 2026-10-10. Host: real host (immutable Bazzite). Method: `uv run python setup.py` (no flags) in tmux
session `p16-ui` (200x60), driven only by arrow keys and the view keys `2`/`3`/`4`; assertions are
`tmux capture-pane -p` text matches. Never pressed: enter, `u`, `y`, `space`, `n`. Session killed at the end.

## Results

| Row | Decision | Result |
|-----|----------|--------|
| (1) groovy/gradle/maven/java Owner | D-02 | PASS |
| (2) springbootcli/sdkman versions | D-01 | PASS |
| (3) AI view skill packs | D-10 | PASS |
| (4) kitty selectable / alacritty dim + reason | D-07, D-16 | PASS (dim SGR not asserted, see note) |
| (5) execute preflight "already current" | D-17 | NOT DONE ON HOST by design; covered by pilot test |
| (6) mmdc Inst mark | D-18 | PASS (not dangling) |
| (7) Doctor guidance | D-22 | PASS |

## Evidence

### (1) Owner `Homebrew ≠ policy`, detail sentence (System view)
```
 [ ]  P1   gradle   runtime  both  ✓  9.6.1 -> 9.8.1   Homebrew ≠ policy
 [ ]  P1   java     runtime  both  ✓  26.0.1 -> 27     Homebrew ≠ policy
 [ ]  P1   maven    runtime  both  ✓  3.9.16 -> 3.10.0 Homebrew ≠ policy
 [ ]  P2   groovy   runtime  both  ✓  5.0.7 -> 6.0.0   Homebrew ≠ policy
detail bar (each): ... |  requires sdkman  |  managed by Homebrew  |  Homebrew owns this copy; the catalog's policy installs gradle via SDKMAN
```
All four rows are outdated (`->`), so no `u` was pressed (none was pressed anywhere).

### (2) No `no version` for the SDKMAN family
```
 [ ]  P1   sdkman         runtime  both  ✓  5.23.0 (no comparison)  own installer
 [ ]  P2   springbootcli  runtime  both  ✓  4.1.0 (no comparison)   SDKMAN
detail springbootcli: ... requires sdkman  |  managed by SDKMAN
detail sdkman: ... installed via own installer  |  latest version cannot be determined for this install method — pressing u re-runs the same install path ...
```

### (3) AI view after the System-view wait
```
 [ ]  P3   matt-pocock-skills       ai  human  ○                       (absent; also absent in 16-16 host proof)
 [ ]  P3   opengsd                  ai  human  ✓  no version  Claude Code +3
 [ ]  P3   ponytail                 ai  human  ✓  no version  Claude Code, Codex
 [ ]  P3   softaworks-agent-toolkit ai  human  ✓  no version  Claude Code, Codex
 [ ]  P3   superpowers              ai  human  ✓  no version  Claude Code, Pi
```
Inst is `✓` and Owner lists the hosts for all four. `no version` on pack rows is expected (packs have no
version); it is not the sdkman/springbootcli defect.

### (4) kitty / alacritty (User view)
```
      P3   alacritty  terminal human ○                                  Cross-platform OpenGL terminal emulator (not available: immutable host)
 [ ]  P3   kitty      terminal human ✓ 0.49.0 (no comparison) own installer  GPU-accelerated terminal emulator
alacritty detail: ... alacritty only declares native package-manager methods (dnf/apt/pacman), which this installer skips on an immutable (ostree) host.
kitty detail: ... installed via own installer  |  latest version cannot be determined ...
```
alacritty has no `[ ]` box (not selectable) and the full sentence. Note: the dim style is applied in
`installer/catalog_tui.py` `_row_cells`; plain-text capture cannot assert SGR dim, and with the cursor on the
row the cursor highlight overrides it. Selectability and text were verified, styling by code only.

### (5) Execute preflight
Not run on the host: the execute screen's enter would run `configure_path` on the real rc files. Covered by the
Textual pilot test `tests/test_execute_screen.py::test_current_only_selection_says_already_current_not_install_zero`
(asserts `"wezterm already current — nothing to do."` and no `Install 0 tools`); ran green on 2026-10-10.

### (6) mmdc
```
 [ ]  P2   mmdc  diagram  both  ✓  11.17.0 -> 12.0.0  Homebrew ≠ policy
detail: ... requires pnpm, puppeteer  |  managed by Homebrew  |  Homebrew owns this copy; the catalog's policy installs mmdc via pnpm
```
Inst is a green `✓`, not a red `!`: the shim is not dangling on this host. (Unrelated: `puppeteer` shows `!` and
`no version` in the AI view; it is a separate tool and was out of scope of this check.)

### (7) Doctor (Audit panel; enter NOT pressed)
```
│  /home/bazzite/.local/kitty.app/bin not on PATH ...
│  /home/bazzite/.local/bin duplicated on PATH ... 3 startup files add it without checking ...
│    → inside the 'my-kitty PATH' block; fix it in that tool, because that tool may regenerate the block; Press enter (apply) to guard it in place. A backup of the original is saved as .tools-installer.old first
```
Names the kitty block and offers the guard. Footer: `enter apply | r reinstall pnpm globals`.

## Host safety
sha256 of ~/.bashrc ~/.zshrc ~/.profile ~/.bash_profile ~/.myshellrc recorded before launch and after kill:
IDENTICAL (`diff` empty).
```
c59f1b27...f8222b  .bashrc
aa07cc3f...eb0627  .zshrc
0db8ea39...4a4651  .profile
6808eecd...ef1e9e  .bash_profile
4c5ba1ae...112bdf  .myshellrc
```
