# Troubleshooting

If something goes wrong, this page lists the common problems and fixes. If your
issue is not here, please open an issue at
<https://github.com/castocolina/tools-installer/issues>.

## A tool installed but the command is "not found"

The tool was installed into a userspace bin dir (usually `~/.local/bin`) that is
not on your `PATH` in the current shell.

1. Run the PATH doctor: `make run` then choose the doctor, or `uv run setup.py --doctor`.
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
