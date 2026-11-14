# Troubleshooting

If something goes wrong, this page lists the common problems and fixes. If your
issue is not here, please open an issue at
<https://github.com/castocolina/tools-installer/issues>.

## A tool installed but the command is "not found"

The tool was installed into a userspace bin dir (usually `~/.local/bin`) that is
not on your `PATH` in the current shell.

1. Run the PATH doctor: `make run` then choose the doctor, or `uv run --isolated --no-dev setup.py --doctor`.
   It writes every bin dir into a managed block in `~/.myshellrc` and wires
   `source ~/.myshellrc` into your `~/.zshrc` / `~/.bashrc`.
2. Restart your shell, or run `. ~/.myshellrc` in the current one.
3. Re-check with `command -v <tool>`.

## "missing from PATH" persists after running the doctor

The doctor updates your shell rc files, but the current shell process keeps its
old `PATH` until you restart it (or `source ~/.myshellrc`). Open a new terminal
and re-run the doctor — the entry should now be present.

## A bin dir is reported as "does not exist"

A declared bin dir is missing on disk. This is usually harmless (no tool has been
installed there yet); it is created on first install. If a tool that should live
there is missing, re-run the installer for it.

## GitHub rate-limit / no network when resolving a version

`github_release` tools resolve their latest version from the GitHub API. On a
rate-limited or offline machine that lookup fails and the tool is reported as
`failed` in the summary (the run is not aborted). Retry later, or install that
tool via its native package manager / brew.

## Immutable / atomic distros (Bazzite, Silverblue)

The native package-manager step is skipped by default to avoid `rpm-ostree`
reboots. Tools install into userspace (`~/.local`) or via brew-linux instead.

## Permission denied writing to a bin dir

The installer never uses `sudo` for userspace installs. If a bin dir is not
writable, point the tool at a writable `bin_dir` (e.g. `~/.local/bin`) or fix the
directory's ownership.

## Homebrew is optional

Homebrew is never a prerequisite. It is offered as an optional package; an
official `.sh` installer or a release archive is always preferred when available.

## `pip` or `npm` prints a "banned" message

Earlier versions installed PATH shims and an alias block for `pip`, `pip3`, `npm`,
`npx` and `pnpm`. An interactive or CLI launch of this version (for example
`make doctor`) removes the ones it wrote and prints each removed path. Scheduled background jobs do not run this cleanup.

Then open a new shell, which drops both the old aliases and the cached command
paths. To fix the current shell instead, run `unalias pip pip3` and then `hash -r`
(`hash -r` alone only clears the command-path cache and leaves loaded aliases active).

If the launch printed a warning, act on the warning's start:

- A warning that starts `Could not check` names a shim in `~/.local/bin` or a shell rc
  file. The launch could not read that file, so it has not verified that the file is
  its own. Fix that file's permissions (or its directory's), then launch again. Do not
  delete the file because of this warning; the next launch reads it and removes only
  what carries the installer's marker.
- A warning that starts `Could not remove the retired pip/npm guard shim` names a shim
  the launch verified as its own but could not delete. Delete that file yourself, or
  make its directory writable, then launch again.
- A warning that starts `Could not remove the retired guard alias block from` names a
  shell rc file such as `~/.bashrc`, `~/.zshrc` or `~/.myshellrc`. Fix that file's
  permissions, or open it and delete only the lines from `# >>> tools-installer ban >>>`
  through `# <<< tools-installer ban <<<`, then launch again. Do not delete the rc file
  itself: it holds your own shell configuration.

The launch leaves without a message anything it does not recognize as its own (a
symlink, an unmarked file, a shim over 8 KiB, an rc file over 1 MiB or not valid
UTF-8) and any file that changed or became unreadable after its first read; the next
launch checks again. So if `pip` still prints the old message in a new shell and no
launch warned, run `type pip` to see which file or alias answers. That file is yours
to remove.
