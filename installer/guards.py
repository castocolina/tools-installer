"""Environment policy: PATH shims and aliases for banned and redirected commands.

Two removable, idempotent layers steer callers to the managed toolchain:
1. PATH shims in the managed bin dir (~/.local/bin) — tiny POSIX-sh executables.
   Hard-block shims print the sanctioned tool and exit non-zero. Redirect shims
   exec into the managed equivalent, preserving the real exit code and streams.
   They catch ANY caller that resolves via PATH: you, an agent, a script, a
   non-interactive shell.
2. Interactive-shell aliases — a faster path for interactive use, written as a
   marker-delimited block (reusing shellrc's block machinery). A redirect alias
   performs the redirect; a ban alias prints a message and fails.

Neither layer is hermetic: `python -m pip install` bypasses the pip shim, and a
real npm/pip earlier on PATH wins. guard_path_warning flags the PATH-order case.
A subprocess this installer spawns would inherit the shimmed PATH and hit its
own guards from the inside; `shell_path` demotes the shim dir for the shells
executors.py opens, the way `real_pnpm` resolves an absolute path for the two
direct Python call sites.

pip and pip3 stay hard-blocked because `uv pip` is not an argv-compatible drop-in
for two of the six subcommands this shim would intercept — `uninstall` cascades
to transitive dependencies pip leaves in place, and `compile` requires an
explicit output file and applies a different extras-stripping default — so a
blanket redirect would change behaviour silently. See
https://docs.astral.sh/uv/pip/compatibility/ and
.planning/phases/04-package-manager-redirect-policy/04-RESEARCH.md Pitfall 1.
"""

import os
import shlex
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import installer.locations
from installer.shellrc import apply_block, strip_block

BANNED: dict[str, str] = {
    "npm": "pnpm (local) or volta install <pkg> (global)",
    "pip": "uv (uv pip install / uv add)",
    "pip3": "uv (uv pip install / uv add)",
    "npx": "pnpm (pnpm dlx <pkg>)",
}


@dataclass(frozen=True)
class Redirect:
    target: str
    args: tuple[str, ...]
    label: str


REDIRECTED: dict[str, Redirect] = {
    "npx": Redirect(target="pnpm", args=("dlx",), label="redirected to pnpm dlx"),
}
GLOBAL_SUBCOMMANDS: tuple[str, ...] = ("install", "add", "i")


@dataclass(frozen=True)
class GlobalRedirect:
    passthrough: str | None
    label: str


VOLTA: str = "volta"
# Options that consume no following token AND whose loss cannot change what gets
# installed or how. Two independent conditions, both required, because a
# whitelisted option is not forwarded to volta — it is DROPPED:
#
# 1. Valueless. This is deliberately a whitelist of BOOLEANS rather than a table
#    of value-taking options: an option this list is missing degrades to the
#    wrapper's fallback (npm's hard block, pnpm's pass-through), while a
#    value-taking option a blocklist missed would hand its VALUE to
#    `volta install` as a package name.
# 2. Inert for a global install. `volta install` has no way to forward an
#    option, so an option that survives only as an assumption is an option the
#    wrapper silently overrides. --ignore-scripts, --force, --offline and
#    --prefer-offline all fail this: volta runs a real `npm install --global`
#    with install scripts enabled, resolution unforced and the network
#    available, so dropping them inverts a decision the user typed. They are
#    absent on purpose and reach the `--*) known=0` arm, which degrades.
#
# Being incomplete is therefore safe by construction, which is what keeps this
# out of 04-RESEARCH.md's "Don't Hand-Roll" territory. Being over-complete is
# not, which is why membership is argued per entry rather than assumed.
BOOLEAN_LONG_OPTIONS: tuple[str, ...] = (
    "--global",
    "--save",
    "--save-dev",
    "--save-exact",
    "--save-prod",
    "--save-optional",
    "--no-save",
    "--recursive",
    "--workspace-root",
    "--silent",
    "--verbose",
)
# Short flags that are boolean in BOTH npm and pnpm, so a cluster built only
# from them (-gD) carries no value. `w`, `C` and `F` are excluded on purpose:
# npm's -w and -C, and pnpm's -C and -F, all take one.
BOOLEAN_SHORT_FLAGS: str = "gDEPOSB"
GLOBAL_REDIRECTED: dict[str, GlobalRedirect] = {
    "npm": GlobalRedirect(
        passthrough=None,
        label="global installs redirected to volta install, other npm use blocked",
    ),
    "pnpm": GlobalRedirect(
        passthrough="pnpm",
        label="global adds redirected to volta install",
    ),
}
EXIT_CODE = 127  # non-zero so the caller sees a hard failure
SHIM_SENTINEL = "# tools-installer-ban-shim"
REDIRECT_SENTINEL: str = "# tools-installer-redirect-shim"
BAN_BEGIN = "# >>> tools-installer ban >>>"
BAN_END = "# <<< tools-installer ban <<<"
PathLookup = Callable[[str, str], str | None]


def ban_body(name: str) -> str:
    """The two lines that explain the ban and exit non-zero (no shebang, no sentinel).

    Shared by the stand-alone hard-block shim and by the global-redirect
    wrapper's fallback, so the two bodies cannot drift apart. Raises rather than
    KeyError-ing so a future BANNED-less name fails with an explanation instead
    of a bare dict miss from inside a shim generator.
    """
    hint = BANNED.get(name)
    if hint is None:
        raise ValueError(f"'{name}' has no BANNED hint to build a hard block from")
    return (
        f"echo \"tools-installer: '{name}' is banned on this machine — use {hint}.\" >&2\n"
        f"exit {EXIT_CODE}\n"
    )


def shim_script(name: str) -> str:
    """A 4-line POSIX-sh shim that explains the ban and exits non-zero."""
    return f"#!/bin/sh\n{SHIM_SENTINEL}\n{ban_body(name)}"


def redirect_shim_script(name: str, target_path: str) -> str:
    """POSIX-sh shim that execs into the redirect target, preserving exit code."""
    spec = REDIRECTED[name]
    quoted_args = " ".join(shlex.quote(arg) for arg in spec.args)
    return f'#!/bin/sh\n{REDIRECT_SENTINEL}\nexec {shlex.quote(target_path)} {quoted_args} "$@"\n'


def global_redirect_shim_script(name: str, *, volta_path: str, passthrough_path: str | None) -> str:
    """Argv-conditional wrapper: global install/add/i execs volta, else fallback.

    The wrapper redirects only argv it fully understands. Every option token is
    matched against BOOLEAN_LONG_OPTIONS / BOOLEAN_SHORT_FLAGS — the attached
    `--opt=value` form by its NAME, against the same whitelist, because
    consuming no following token makes the form parseable but does not make the
    option droppable; anything else clears the `known` flag and the volta branch
    is skipped entirely.
    Without that flag the wrapper would treat a separated option value as a
    package name — `npm i -g --loglevel warn typescript` would run
    `volta install warn typescript`, installing a real, unrelated package from
    the public registry through the very path that trades pnpm's gated
    postinstalls for volta's ungated `npm install --global`.

    Four shapes therefore degrade instead of redirecting: a value-taking option
    anywhere in argv (before the subcommand it also corrupts subcommand
    detection: `npm --prefix <path> install -g <pkg>`), a short cluster
    carrying an attached value (`pnpm -Cmy-gadget add x`, whose `g` would
    otherwise flip is_global and turn a workspace-scoped add into a global
    install), a boolean given nopt's explicit-value form (`--ignore-scripts
    false <pkg>`, whose `false` is a value and not a package name), and an
    option whose effect volta cannot honour (`--ignore-scripts`, `--force`,
    `--offline`, `--prefer-offline`: see BOOLEAN_LONG_OPTIONS — redirecting
    those would run the install under weaker rules than the user asked for).
    npm degrades to its hard block — safe, the user sees the ban
    message and retypes. pnpm degrades to an un-redirected pass-through to real
    pnpm: a genuine redirect bypass, but no security loss, since the install
    still runs under pnpm's gated-postinstall model.
    """
    spec = GLOBAL_REDIRECTED[name]
    volta = shlex.quote(volta_path)
    subcmds = "|".join(GLOBAL_SUBCOMMANDS)
    if spec.passthrough is not None:
        if passthrough_path is None:
            raise ValueError(
                "a pass-through wrapper with no resolved real binary must not be generated"
            )
        fallback = f'exec {shlex.quote(passthrough_path)} "$@"\n'
    else:
        fallback = ban_body(name)
    long_booleans = "|".join(name for name in BOOLEAN_LONG_OPTIONS if name != "--global")
    # Five structural rules the body depends on:
    # 1. The first loop only READS "$@"; the second loop rewrites it with the
    #    standard POSIX rotate idiom (take $1, shift, append the keepers).
    #    Because the rotate loop mangles "$@", the branch it lives in always
    #    ends in an exec or an exit — control never reaches the fallback with
    #    a rewritten argv.
    # 2. The first non-flag token is the subcommand and is dropped; every
    #    later non-flag token is a package name and is kept. Every flag,
    #    -g/--global included, is dropped, because volta install takes bare
    #    package names.
    # 3. `known` is the guard that makes rule 2 sound: the rewrite may only
    #    assume "non-flag token = package name" when every option in argv is a
    #    whitelisted boolean. One unrecognised option clears it and the whole
    #    volta branch is skipped. The attached --opt=value form is checked
    #    against the SAME whitelist, on its name alone: consuming no following
    #    token is what makes the form parseable, not what makes the option
    #    droppable. A blanket accept there let `--registry=https://internal`
    #    vanish and re-resolved the package from the public registry — a
    #    dependency-confusion setup built by the tool meant to prevent one —
    #    and did the same to `--prefix=`. `--global=` is excluded on purpose
    #    (long_booleans drops it): its value is what decides global-ness, and
    #    the loop cannot read a value it is only allowed to see the name of.
    # 4. A POSIX case pattern matches a WHOLE token, so -g|--global alone never
    #    fires for a packed cluster like -gD. -*[!<booleans>]* catches a cluster
    #    holding anything but known boolean letters — an attached short value
    #    (-Cmy-gadget) included — and -*g* then flips is_global for what is left.
    #    A token beginning with -- is consumed by the arms above it, so
    #    --filter=-g cannot reach either.
    # 5. npm's option parser (nopt) accepts an explicit value for a Boolean
    #    option — `--save-dev false` is the flag set to false, not the flag
    #    followed by a package named `false`. The whitelist consumes the option
    #    but cannot consume its value, so a bare true/false token anywhere in
    #    argv clears `known` and the whole volta branch is skipped. Degrading
    #    also costs nothing real: `volta install true` is the only alternative
    #    reading, and it is never what the user meant.
    return (
        "#!/bin/sh\n"
        f"{REDIRECT_SENTINEL}\n"
        "subcmd=''\n"
        "is_global=0\n"
        "known=1\n"
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        f'    --*=*) case "${{arg%%=*}}" in {long_booleans}) ;; *) known=0 ;; esac ;;\n'
        "    -g|--global) is_global=1 ;;\n"
        f"    {long_booleans}) ;;\n"
        "    --*) known=0 ;;\n"
        f"    -*[!{BOOLEAN_SHORT_FLAGS}]*) known=0 ;;\n"
        "    -*g*) is_global=1 ;;\n"
        "    -*) ;;\n"
        "    true|false) known=0 ;;\n"
        '    *) if [ -z "$subcmd" ]; then subcmd="$arg"; fi ;;\n'
        "  esac\n"
        "done\n"
        'if [ "$is_global" -eq 1 ] && [ "$known" -eq 1 ]; then\n'
        '  case "$subcmd" in\n'
        f"    {subcmds})\n"
        "      argc=$#\n"
        "      seen=0\n"
        '      while [ "$argc" -gt 0 ]; do\n'
        '        arg="$1"\n'
        "        shift\n"
        "        argc=$((argc - 1))\n"
        '        case "$arg" in\n'
        "          -*) ;;\n"
        '          *) if [ "$seen" -eq 0 ]; then seen=1; else set -- "$@" "$arg"; fi ;;\n'
        "        esac\n"
        "      done\n"
        '      if [ "$#" -gt 0 ]; then\n'
        f'        exec {volta} install "$@"\n'
        "      fi\n"
        '      echo "tools-installer: a global install needs a package name." >&2\n'
        f"      exit {EXIT_CODE}\n"
        "      ;;\n"
        "  esac\n"
        "fi\n"
        f"{fallback}"
    )


def is_our_shim(path: Path) -> bool:
    """True only for a readable file carrying our sentinel; never a real binary."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
    return SHIM_SENTINEL in text or REDIRECT_SENTINEL in text


def which_in_path(name: str, path: str) -> str | None:
    return shutil.which(name, path=path)


def real_binary(
    name: str,
    *,
    shim_dir: Path,
    path_value: str,
    lookup: PathLookup = which_in_path,
) -> str | None:
    """Resolve `name` from PATH, never the managed shim.

    Re-resolving the target through the live PATH is how a shim finds itself
    (04-RESEARCH Pitfall 3), so a sentinel-carrying result is refused. The
    sentinel — not the directory — is the guard: the shim dir IS the managed bin
    dir (~/.local/bin), and a pnpm installed there (`npm i -g pnpm` with
    prefix=~/.local, or `corepack enable --install-directory ~/.local/bin`) must
    stay resolvable. Excluding the whole directory made those setups report
    "pnpm not found" while `pnpm --version` worked fine.

    The directory is dropped only for the retry, once our own shim has actually
    won the lookup.
    """
    found = lookup(name, path_value)
    if found is None or is_our_shim(Path(found)):
        rest = [entry for entry in path_value.split(os.pathsep) if entry and entry != str(shim_dir)]
        found = lookup(name, os.pathsep.join(rest))
    if found is None or is_our_shim(Path(found)):
        return None
    return found


def real_pnpm(
    *,
    shim_dir: Path | None = None,
    path_value: str | None = None,
    lookup: PathLookup = which_in_path,
) -> str | None:
    """Resolve real pnpm, never this installer's wrapper.

    installer/run.py::run_command is subprocess.run(cmd), which resolves a
    bare program name through the live PATH, so once this installer owns a
    pnpm entry in the managed bin dir every internal invocation must carry
    an absolute path or it will call our own wrapper instead of pnpm.
    """
    if shim_dir is None:
        shim_dir = installer.locations.bin_dir(None)
    if path_value is None:
        path_value = os.environ.get("PATH", "")
    return real_binary("pnpm", shim_dir=shim_dir, path_value=path_value, lookup=lookup)


def shell_path(
    *,
    shim_dir: Path | None = None,
    path_value: str | None = None,
) -> str:
    """PATH for a shell this installer spawns, with the managed bin dir demoted last.

    real_pnpm closes the two direct Python call sites, but executors._script and
    executors._sdkman hand a command line to `sh -c`/`bash -c` and the child
    inherits this process's PATH — whose FIRST entry is the managed bin dir when
    the ban is active. A vendor install script's own `npm`/`npx` call would then
    hit our hard-block shim and exit 127, and its `pnpm add -g` would be
    rewritten to `volta install`, all inside an install the user explicitly
    asked this installer to perform.

    Demoting rather than dropping the directory is deliberate: it is also the
    managed bin dir, so a script that legitimately needs a tool installed there
    still finds it, while any real npm/pnpm elsewhere on PATH now wins.
    """
    if shim_dir is None:
        shim_dir = installer.locations.bin_dir(None)
    if path_value is None:
        path_value = os.environ.get("PATH", "")
    target = str(shim_dir)
    entries = [entry for entry in path_value.split(os.pathsep) if entry]
    rest = [entry for entry in entries if entry != target]
    if len(rest) == len(entries):
        return os.pathsep.join(entries)
    return os.pathsep.join([*rest, target])


def install_redirect_shims(
    shim_dir: Path,
    *,
    path_value: str,
    lookup: PathLookup = which_in_path,
) -> dict[str, str]:
    """Write redirect shims into shim_dir (mode 0o755). Idempotent.

    Never overwrites a real binary already living there (sentinel check).
    When the redirect target is unresolvable, writes the hard-block body
    instead of a shim that execs into a missing command.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    for name, spec in REDIRECTED.items():
        target = shim_dir / name
        if target.exists() and not is_our_shim(target):
            results[name] = "skipped (real binary here)"
            continue
        had = target.exists()
        resolved = real_binary(spec.target, shim_dir=shim_dir, path_value=path_value, lookup=lookup)
        if resolved is None:
            target.write_text(shim_script(name))
            target.chmod(0o755)
            results[name] = "blocked (pnpm not found)"
            continue
        target.write_text(redirect_shim_script(name, resolved))
        target.chmod(0o755)
        results[name] = "refreshed" if had else "created"
    return results


def install_global_redirect_shims(
    shim_dir: Path,
    *,
    path_value: str,
    lookup: PathLookup = which_in_path,
) -> dict[str, str]:
    """Write argv-conditional global-redirect shims, gated on volta.

    The redirect is enabled only when volta resolves, mirroring how
    omz_plugins_policy gates on omz_present — a missing target degrades to
    the existing behaviour, never to a broken command (R-02).
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    volta_path = real_binary(VOLTA, shim_dir=shim_dir, path_value=path_value, lookup=lookup)
    results: dict[str, str] = {}
    for name, spec in GLOBAL_REDIRECTED.items():
        target = shim_dir / name
        if target.exists() and not is_our_shim(target):
            results[name] = "skipped (real binary here)"
            continue
        if volta_path is None:
            if spec.passthrough is None:
                # Write the block rather than assume install_shims ran first:
                # both production callers do call it, but nothing enforces that,
                # and reporting a block that is not on disk is a lie. The body is
                # byte-identical to install_shims', so writing it twice is
                # idempotent.
                target.write_text(shim_script(name))
                target.chmod(0o755)
                results[name] = "blocked (volta not found)"
                continue
            if target.exists() and is_our_shim(target):
                target.unlink()
                results[name] = "removed (volta not found)"
            else:
                results[name] = "absent (volta not found)"
            continue
        passthrough_path: str | None = None
        if spec.passthrough is not None:
            passthrough_path = real_binary(
                spec.passthrough, shim_dir=shim_dir, path_value=path_value, lookup=lookup
            )
            if passthrough_path is None:
                if target.exists() and is_our_shim(target):
                    target.unlink()
                    results[name] = "removed (real pnpm not found)"
                else:
                    results[name] = "skipped (real pnpm not found)"
                continue
        had = target.exists()
        target.write_text(
            global_redirect_shim_script(
                name, volta_path=volta_path, passthrough_path=passthrough_path
            )
        )
        target.chmod(0o755)
        results[name] = "refreshed" if had else "created"
    return results


def install_shims(shim_dir: Path) -> dict[str, str]:
    """Write npm/pip/pip3 shims into shim_dir (mode 0o755). Idempotent.

    Never overwrites a real binary already living there (sentinel check).
    Returns {name: 'created' | 'refreshed' | 'skipped (real binary here)'}.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    for name in BANNED:
        target = shim_dir / name
        if target.exists() and not is_our_shim(target):
            results[name] = "skipped (real binary here)"
            continue
        had = target.exists()
        target.write_text(shim_script(name))
        target.chmod(0o755)
        results[name] = "refreshed" if had else "created"
    return results


def guarded_names() -> tuple[str, ...]:
    """Every command name this installer shims, ban and redirect alike.

    Deduplicated because a name may appear in both dicts (its redirect body
    supersedes its hard-block body on disk).
    """
    return tuple(dict.fromkeys((*BANNED, *REDIRECTED, *GLOBAL_REDIRECTED)))


def remove_shims(shim_dir: Path) -> dict[str, str]:
    """Remove only the shims we created. Returns {name: 'removed' | 'absent'}.

    One remover covers both bodies, so a redirect can never outlive the
    policy's teardown (SC#1).
    """
    results: dict[str, str] = {}
    for name in guarded_names():
        target = shim_dir / name
        if target.exists() and is_our_shim(target):
            target.unlink()
            results[name] = "removed"
        else:
            results[name] = "absent"
    return results


def guard_status(shim_dir: Path) -> dict[str, bool]:
    """{name: our shim is installed}."""
    return {name: is_our_shim(shim_dir / name) for name in guarded_names()}


def guard_label(name: str) -> str:
    """Per-command doctor text: redirect label, or 'blocked'."""
    if name in GLOBAL_REDIRECTED:
        return GLOBAL_REDIRECTED[name].label
    if name in REDIRECTED:
        return REDIRECTED[name].label
    return "blocked"


def ban_alias_block() -> str:
    """Marker-delimited alias block (no trailing newline, like shellrc blocks).

    An interactive redirect alias must perform the redirect, not warn about it —
    a redirect is meant to be transparent. The alias names the target by PATH
    name while the installed shim bakes the real_binary-resolved absolute path,
    so in an interactive shell the alias resolves the target through the user's
    own PATH. That is intended — an alias must keep working after the target
    moves — and it stays harmless after plan 04-03 wraps pnpm, because dlx is
    not one of GLOBAL_SUBCOMMANDS and therefore never reaches the volta branch.

    Names in GLOBAL_REDIRECTED are skipped: a one-line alias cannot reproduce
    the argv branch, so an npm alias would claim the command is blocked while
    the PATH shim was redirecting its global form, and any pnpm alias risks
    breaking a sanctioned tool in interactive shells. For these two, the PATH
    shim is the only layer.
    """
    lines = [BAN_BEGIN]
    for name, hint in BANNED.items():
        if name in GLOBAL_REDIRECTED:
            continue
        if name in REDIRECTED:
            spec = REDIRECTED[name]
            tokens = " ".join((spec.target, *spec.args))
            lines.append(f"alias {name}='{tokens}'")
            continue
        lines.append(
            f"""alias {name}='echo "tools-installer: {name} is banned — use {hint}." >&2; false'"""
        )
    lines.append(BAN_END)
    return "\n".join(lines)


def write_ban_aliases(rc_path: Path) -> None:
    """Idempotently write the alias block into rc_path, preserving the rest."""
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, ban_alias_block(), begin=BAN_BEGIN, end=BAN_END))


def remove_ban_aliases(rc_path: Path) -> None:
    """Strip the alias block from rc_path. A missing file or absent block is a no-op."""
    if not rc_path.exists():
        return
    original = rc_path.read_text()
    stripped = strip_block(original, BAN_BEGIN, BAN_END)
    if stripped != original:
        rc_path.write_text(stripped)


def guard_path_warning(
    shim_dir: Path,
    path_value: str,
    which: Callable[[str], str | None],
) -> str | None:
    """Warn when the shims can't take effect: shim_dir missing from PATH, or a
    real npm/pip/pip3 resolving before it. Returns None when the order is sound.

    `which` is injected (shutil.which in production) so the check is testable.
    """
    target = str(shim_dir)
    path_dirs = path_value.split(os.pathsep)
    if target not in path_dirs:
        return (
            f"{target} is not on PATH — add it (early) so the ban applies to "
            "non-interactive callers."
        )
    shim_index = path_dirs.index(target)
    for name in guarded_names():
        if not is_our_shim(shim_dir / name):
            continue
        real = which(name)
        if real and not is_our_shim(Path(real)):
            real_dir = str(Path(real).parent)
            if real_dir in path_dirs and path_dirs.index(real_dir) < shim_index:
                return (
                    f"A real '{name}' at {real} resolves before {target}; "
                    f"put {target} earlier on PATH."
                )
    return None


def exec_targets(text: str) -> tuple[str, ...]:
    """The absolute paths a shim body execs into, parsed from its `exec` lines."""
    targets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("exec "):
            continue
        try:
            words = shlex.split(stripped)
        except ValueError:  # an unbalanced quote is not a target we can read
            continue
        if len(words) > 1:
            targets.append(words[1])
    return tuple(targets)


def _stale_target_message(name: str, text: str) -> str | None:
    """Warn when a live redirect body points at a target that is no longer runnable.

    status.is_installed is `shutil.which(cmd) is not None`, so once the wrapper
    sits in the managed bin dir the catalog reads `pnpm` as installed forever —
    dependencies that require it resolve as satisfied, and running it prints a
    raw `exec: <path>: not found`. The sentinel cannot see that; the baked path
    can.
    """
    missing = [target for target in exec_targets(text) if not os.access(target, os.X_OK)]
    if not missing:
        return None
    return f"'{name}' redirects to {missing[0]}, which no longer exists; re-apply the policy."


def guard_redirect_warning(shim_dir: Path) -> str | None:
    """Warn when a redirect on disk is not doing what its label claims.

    Three degradations are reported: a name installed as a hard block because
    its target was unresolvable at apply time, a pass-through name left
    un-redirected (distinguishing "no real binary" from "a foreign binary
    already occupies the shim dir" — the two reach the same on-disk state by
    different routes and need different remedies), and a live redirect whose
    baked target has since disappeared. Returns None when every redirect on disk
    is live.
    """
    messages: list[str] = []
    for name, spec in REDIRECTED.items():
        path = shim_dir / name
        if not is_our_shim(path):
            continue
        text = path.read_text()
        if REDIRECT_SENTINEL not in text:
            messages.append(
                f"'{name}' is hard-blocked because '{spec.target}' was not "
                "resolvable when the policy was applied; install "
                f"{spec.target} and re-apply."
            )
            continue
        stale = _stale_target_message(name, text)
        if stale is not None:
            messages.append(stale)
    npm_path = shim_dir / "npm"
    npm_redirect_live = is_our_shim(npm_path) and REDIRECT_SENTINEL in npm_path.read_text()
    for name, spec in GLOBAL_REDIRECTED.items():
        path = shim_dir / name
        if is_our_shim(path):
            text = path.read_text()
            if REDIRECT_SENTINEL not in text:
                messages.append(
                    f"'{name}' is hard-blocked because '{VOLTA}' was not "
                    "resolvable when the policy was applied; install "
                    f"{VOLTA} and re-apply."
                )
                continue
            stale = _stale_target_message(name, text)
            if stale is not None:
                messages.append(stale)
            continue
        if spec.passthrough is None or not npm_redirect_live:
            continue
        if path.exists():
            # install_global_redirect_shims reached this state via
            # "skipped (real binary here)", not via an unresolvable pnpm:
            # telling the user pnpm could not be found while it sits in the
            # directory being inspected sends them after a remedy that can
            # never change anything.
            messages.append(
                f"'{name}' is not redirected because a non-managed '{name}' already "
                f"occupies {shim_dir}; move it aside and re-apply."
            )
            continue
        messages.append(
            f"'{name}' is not redirected because a real '{spec.passthrough}' "
            "was not resolvable when the policy was applied; install "
            f"{spec.passthrough} and re-apply."
        )
    return " ".join(messages) if messages else None
