---
phase: 25-lean
status: complete
tested_at: 2026-11-15
environment: >-
  Disposable container `ti-uat-25-fedora` (Fedora 44 from the already-present `registry.fedoraproject.org/fedora:44`,
  `--init`, user `tester`, repo copied with `git archive HEAD` = efbb30db, uv installed, `uv sync` done, no sudo
  used). The wizard ran as `uv run --isolated --no-dev setup.py` through `podman exec -it` in one herdr tab
  (252x69, the default size) and in tmux inside the container at exactly 80x20 with `NO_COLOR=1`. Nothing ran on
  the host. The container was removed afterwards; no image was pulled (`podman images` identical before and after).
source: [25-SPEC.md, 25-VERIFICATION.md, scratchpad/uat/80x20-after2 (captures at 1cc6953e, before phase 25)]
---

# Phase 25 - Agent-run UAT

Three tests. The question is whether anything visible changed except what phase 25 intended: ten new modules
from the `wizard_app.py` split, `installer/compose.py`, the retired `host_setup` kind and the retired
sensitive-action screens, and the capped Execute run log.

## Results

| # | Test | Result |
|---|------|--------|
| 1 | Every view, unchanged (80x20 and default herdr size) | pass |
| 2 | A real install and removal through the TUI (yq) | pass |
| 3 | The CLI routes still wire through compose.py | pass |

Agent-run UAT (2026-11-15, HEAD efbb30db): all three tests ran in `ti-uat-25-fedora`. Captures are under
`/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/25/`
(`t80/` for 80x20, `herdr/` for the default size, `11-yq-receipt.txt`, `16-after-uninstall-state.txt`, `17-cli.txt`,
`jev.out`, `setup.log`, `images-before.txt`, `images-after.txt`). Host-only gaps that remain: macOS (not
covered by this container), a real systemd user manager (the container has none, so Schedules shows "n/a"
exactly as in the baseline), and the owner's real host files. The sudo-needing `jq` (dnf) route was avoided on
purpose; `yq` installs from a GitHub release in the tester's home.

## Tests

### 1. Every view, unchanged

Steps: start the container and the wizard at both sizes. At each size capture System, User, AI, Doctor (down, end,
home), Uninstall, Policies (toggle one row, then toggle it back) and Schedules. Compare the 80x20 set with
`scratchpad/uat/80x20-after2/` (HEAD 1cc6953e, before phase 25).

Expected: same content, layout, key hints and behaviour. Tab bar, badge and footer stay whole; no screen-level
scrollbar.

- Result: pass
- Notes: agent-run 2026-11-15 in `registry.fedoraproject.org/fedora:44`. Script `scratchpad/rv25-t80.sh` is the
  baseline's own driver (fresh HOME, first-run link-mode modal answered with Enter).
  - 80x20, NO_COLOR=1: 20 captures in `uat/25/t80/` (`00-start-system` ... `07b-schedules-down`). A `diff` of every
    file against `uat/80x20-after2/` reports all 20 byte-identical: same tab bar, badge, table, detail text, footer
    key hints, `[LIVE]`/`[STAGED]` badges, Policies row `○ [off]` to `● [on]` and back to `○ [off]` (Countdown
    helper), Doctor body, Schedules `n/a` rows. The only block glyphs are the inner table scrollbars, as in the
    baseline.
  - Default herdr size (252x69): `uat/25/herdr/01-system` ... `07b-schedules-down`. Every screen has the tab bar
    (`[1] System ... [7] Schedules`), the badge line, and the footer (`... | 1-7 views | ^p nav | esc back | q quit`)
    whole. The two files that contain block glyphs (`02-user`, `05-uninstall`) have them at mid-screen rows
    (the table's own scrollbar), none at the screen edge. Policies: Countdown helper toggled `off` to `on`
    (`06c`, `06e`) and back to `off` (`06g`, `06h`). The Doctor panel (PATH Doctor report, centred, fits the
    screen) is identical for top, Down, End and Home (`04`, `04b`-`04d`): nothing to scroll at 69 rows, so the
    scroll behaviour is proven by the identical 80x20 set. Note: `herdr pane send-keys` rejects `End` and `Home`
    by name; those two keys went in as `send-text` escape sequences (`ESC [ F`, `ESC [ H`).
  - jev (laya, advisory): T1-80x20 `open-real` conf 0.09, T1-herdr `resolved` conf 0.07. Both `needs_fallback`,
    so I decided: the files are byte-identical, so `resolved`. Recorded as laya noise.

### 2. A real install and removal through the TUI

Steps: stage `yq` in the User view, press enter (Install plan), enter (Execute), capture the run log, return to the
catalog, then remove it from Uninstall.

Expected: install succeeds with a receipt or owner shown; Execute shows no sensitive-action prompt; the tool is
removed and its receipt cleared.

- Result: pass
- Notes: agent-run 2026-11-15 in the same container, herdr pane default size.
  - Stage: `08-stage-yq` shows `[x] P0 yq`, detail "not installed". (The first space staged `jq` because the
    cursor sat one row up; I unmarked it and marked `yq` before pressing enter, since `jq` needs dnf and sudo.)
  - Install plan: `09-after-enter-1` "Install plan - 1 will install", `yq will install - not installed`, hints
    "enter start | up/down move | esc cancel".
  - Run log: `10-execute-1` "-- yq -- / yq | -- trying github_release -- / running"; `10-execute-3` and
    `10-execute-6` "Summary - 1 installed / yq installed / yq: sha256 ok / PATH configured in
    /home/tester/.myshellrc / PATH audit: PATH looks healthy / Done. enter or esc returns to the catalog."
    `grep -il sensitive uat/25/herdr/*.txt` finds no file: no sensitive-action prompt anywhere in Execute.
  - Receipt and owner: `11-yq-receipt.txt` has `receipts/yq.json` with method `github_release`, artifact
    `/home/tester/.local/bin/yq`, `smoke: ok`, release `v4.54.3`; `yq --version` prints `v4.54.3`. The User view
    (`12-user-after-install`) shows yq Health `ok`, Ver `v4.54.3`, Owner `GitHub release`.
  - Removal: `13-uninstall-list` lists yq under "removable here (1)", installed via `installer`, path
    `/home/tester/.local/bin/yq`; the detail line says "installed by this installer: receipt matches".
    `14-uninstall-confirm` shows the modal "Remove 1 tool(s)? This deletes installed artifacts and is not undoable.
    enter remove | esc cancel". After enter, `15-uninstall-result` has no "removable here" group and yq moved to
    "nothing to do". `16-after-uninstall-state.txt`: `receipts/` is empty, `~/.local/bin` holds only uv and uvx,
    `command -v yq` finds nothing.
  - jev (laya, advisory): T2-install-remove `open-trivial` conf 0.08, `needs_fallback`. Own decision: `resolved`.
    No defect found; the summary line names "sha256" and the PATH wiring, and the receipt and owner appear in
    the catalog and on disk.

### 3. The CLI routes still wire through compose.py

Steps: inside the container as tester, run `uv run --isolated --no-dev setup.py --doctor` and
`setup.py --uninstall --yes`. Then a unit-style probe loads scratch copies of the registry that declare a retired
key and a retired method kind.

Expected: both CLI routes run to completion with their normal output. A retired
`default_enabled_sensitive_actions` key fails with the retired-key error.

- Result: pass
- Notes: agent-run 2026-11-15; output in `uat/25/17-cli.txt`, scripts `scratchpad/rv25-cli.sh` and
  `scratchpad/rv25-probe.py`.
  - `--doctor`: exit 0 with the normal PATH Doctor report (a "/home/tester/.local/bin duplicated on PATH" finding,
    which the report itself explains as an inherited entry; my harness exported PATH before the login shell
    added it, so it is a harness artefact and not a product issue).
  - `--uninstall --yes`: exit 0, "Nothing to uninstall: no tools-installer artifacts found." plus the
    "Not removed (tools-installer cannot prove it installed these)" list (uv, uvx). That is its normal output at this
    state, because test 2 already removed yq; the real removal path was proven in test 2.
  - Probe: the shipped registry loads 86 tools. A scratch copy with `default_enabled_sensitive_actions = []`
    fails with `ValueError: tool 'uv': default_enabled_sensitive_actions was retired in Phase 25 (no action has
    asked since 23.2); remove the key`. A scratch copy with `kind = "host_setup"` fails with `ValueError: tool 'rg':
    unknown method kind 'host_setup'`.
  - jev (laya, advisory): T3-cli-routes `open-real` conf 0.15, `needs_fallback`. Own decision: `resolved`; both
    exits are 0 with the expected output and both retired shapes are rejected.

## Observations (not issues)

- `installer/execute_screen.py` is 1063 lines, `installer/app.py` 1327 and `installer/compose.py` 934. None is a
  `wizard_app.py` split module (those are all at most 793 lines), the first two predate the phase (1005 and 1333
  lines at 572d30fd), and the spec sets no cap for `compose.py`. jev laya said `open-real` at conf 0.10
  (`needs_fallback`); own decision: `resolved`, informational only.
- `herdr pane send-keys` cannot name `End`/`Home`; a harness limit, not a product one.

## Issues

None.
