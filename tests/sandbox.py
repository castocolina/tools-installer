"""The unit-test subprocess allowlist: pure functions, judged by resolved real path.

A test may start only a program that sits under pytest's base temp dir, a reviewed
checkout script (`CHECKOUT_SCRIPTS`), or an allowlisted interpreter or utility.
`tests/conftest.py` wires `check_launch` into its Popen guard; nothing here runs a process
or reads the host beyond `os.path.realpath`, `shutil.which` and `Path.exists`.

Messages carry program names, paths and script text only, never environment values.
"""

import contextlib
import json
import os
import re
import shlex
import shutil
import socket
import sys
from collections.abc import Callable, Generator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

CHECKOUT = Path(os.path.realpath(__file__)).parent.parent
LINUXBREW_PREFIX = Path("/home/linuxbrew/.linuxbrew")
# The prefix as written and as it resolves (`/var/home/...` on an atomic host).
_LINUXBREW_ROOTS = (LINUXBREW_PREFIX, Path(os.path.realpath(LINUXBREW_PREFIX)))

UTILITY_NAMES = ("stdbuf", "systemd-environment-d-generator")
# A utility that runs the rest of its argv: its options are skipped and the command is checked.
PREFIX_UTILITIES = frozenset({"stdbuf"})
_SHELL_NAMES = frozenset({"sh", "bash", "zsh", "dash"})
_GENERATOR_FILE = "30-systemd-environment-d-generator"
_GENERATOR_DIRS = (
    Path("/usr/lib/systemd/user-environment-generators"),
    Path("/lib/systemd/user-environment-generators"),
    Path("/usr/libexec/systemd/user-environment-generators"),
)
# Real toolchain and network names that may never be allowlisted: a test that needs one
# plants a fake under tmp_path instead.
FORBIDDEN_PROGRAM_NAMES: frozenset[str] = frozenset(
    {
        "uv",
        "uvx",
        "pip",
        "pip3",
        "python3",
        "curl",
        "wget",
        "gh",
        "git",
        "claude",
        "codex",
        "opencode",
        "cursor-agent",
        "copilot",
        "brew",
        "node",
        "npm",
        "npx",
        "pnpm",
        "corepack",
        "volta",
        "bun",
        "yarn",
        "cargo",
        "rustup",
        "go",
        "docker",
        "podman",
        "flatpak",
        "dnf",
        "apt",
        "systemctl",
        "launchctl",
    }
)


@dataclass(frozen=True)
class LaunchPolicy:
    """What a test may launch; every path is a resolved real path."""

    allowed_root: Path
    checkout: Path
    interpreters: frozenset[Path]
    utilities: frozenset[Path]


def _real(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.realpath(path))


def build_launch_policy(
    allowed_root: Path, *, path_value: str, checkout: Path = CHECKOUT
) -> LaunchPolicy:
    """Name the interpreters and utilities by realpath; runs no process."""
    interpreters = {_real(sys.executable)}
    for name in ("sh", "bash", "zsh"):
        found = shutil.which(name, path=path_value)
        if found is not None:
            interpreters.add(_real(found))
    if Path("/bin/sh").exists():
        interpreters.add(_real("/bin/sh"))
    utilities: set[Path] = set()
    for name in UTILITY_NAMES:
        found = shutil.which(name, path=path_value)
        if found is not None:
            utilities.add(_real(found))
    for directory in _GENERATOR_DIRS:
        generator = directory / _GENERATOR_FILE
        if generator.is_file() and os.access(generator, os.X_OK):
            utilities.add(_real(generator))
    return LaunchPolicy(
        allowed_root=allowed_root,
        checkout=checkout,
        interpreters=frozenset(interpreters),
        utilities=frozenset(utilities),
    )


def _refuse_argv() -> AssertionError:
    return AssertionError("the guard needs a non-empty argv list")


def _text(item: object) -> str:
    """A str or PathLike[str] as text; anything else (bytes included) is refused."""
    if not isinstance(item, (str, os.PathLike)):
        raise _refuse_argv()
    text = cast(object, os.fspath(cast(str | os.PathLike[str], item)))
    if not isinstance(text, str):
        raise _refuse_argv()
    return text


def _argv(args: object, shell: bool) -> list[str]:
    if shell and isinstance(args, str):
        return ["/bin/sh", "-c", args]
    if not isinstance(args, (list, tuple)):
        raise _refuse_argv()
    items = [_text(item) for item in cast(Sequence[object], args)]
    if not items:
        raise _refuse_argv()
    # `shell=True` with a list: subprocess runs `/bin/sh -c <first> <rest as $0...>`.
    return ["/bin/sh", "-c", *items] if shell else items


# The checkout files a test may run or source (D-20, narrowed by review C-06), each with the
# toolchain names it may reach: on the child's PATH each must resolve to a fake under the base
# temp or to nothing. The guard cannot see inside the child, so every other checkout file
# (setup.py, the container scripts, any new script) is refused until it is reviewed in here.
CHECKOUT_SCRIPTS: Mapping[str, tuple[str, ...]] = {
    "install.sh": ("curl", "wget", "git", "uv"),
    "scripts/prune-user-tmpdir.sh": (),
    "scripts/prune-tmp-linux.sh": (),
    "scripts/lib/prune-tmp-common.sh": (),
}


def _search(program: str, env: Mapping[str, str] | None, base: Path) -> str | None:
    """The program the exec layer would find: a PATH-less env means os.defpath, and an empty
    or relative entry is relative to the child's cwd."""
    search = os.pathsep.join(str(base / entry) for entry in os.get_exec_path(env))
    return shutil.which(program, path=search)


def _checkout_refusal(
    path: Path, env: Mapping[str, str] | None, base: Path, policy: LaunchPolicy
) -> AssertionError | None:
    """None when `path` is a reviewed checkout file whose toolchain the child cannot reach."""
    relative = path.relative_to(policy.checkout).as_posix()
    names = CHECKOUT_SCRIPTS.get(relative)
    if names is None:
        return AssertionError(
            f"the suite tried to run the checkout file {relative}, which no test may run; "
            "copy what the test needs under tmp_path instead"
        )
    for name in names:
        found = _search(name, env, base)
        if found is not None and not _real(found).is_relative_to(policy.allowed_root):
            return _host_refusal(name, _real(found))
    return None


def _check_file(
    path: Path, env: Mapping[str, str] | None, base: Path, policy: LaunchPolicy
) -> AssertionError | None:
    """None when a script file may run: it sits under the base temp, or it is a reviewed
    checkout file with its toolchain faked; else the refusal to raise."""
    if path.is_relative_to(policy.allowed_root):
        return None
    if path.is_relative_to(policy.checkout):
        return _checkout_refusal(path, env, base, policy)
    return _host_refusal(path.name, path)


def _in_linuxbrew(path: Path) -> bool:
    return any(path.is_relative_to(root) for root in _LINUXBREW_ROOTS)


def _host_refusal(name: str, resolved: Path) -> AssertionError:
    return AssertionError(
        f"the suite tried to run the host's {name} at {resolved}; "
        "plant a fake under tmp_path instead"
    )


def _skip_prefix_options(rest: Sequence[str]) -> Sequence[str]:
    """Drop stdbuf's own options (`-oL`, `-o L`, `--output=L`, `--`); refuse an unknown one."""
    index = 0
    while index < len(rest):
        word = rest[index]
        if word == "--":
            return rest[index + 1 :]
        if word in ("-i", "-o", "-e", "--input", "--output", "--error"):
            index += 2
        elif word.startswith(("-i", "-o", "-e", "--input=", "--output=", "--error=")):
            index += 1
        elif word.startswith("-"):
            raise AssertionError(f"the guard does not know the stdbuf option {word}")
        else:
            break
    return rest[index:]


# --- shell scripts: every command word is checked (D-18) ---

# Only builtins that neither run nor rebind a command: a builtin's arguments are never checked.
# Never `time`, `noglob`, `nocorrect` (the parser skips them and checks the next word), nor
# `eval`, `exec`, `trap`, `emulate`, `autoload`, `hash`, `alias` (each runs or rebinds a command).
SHELL_BUILTINS: frozenset[str] = frozenset(
    {
        "echo",
        "printf",
        "test",
        "[",
        "true",
        "false",
        "cd",
        "export",
        "unset",
        "set",
        "exit",
        "return",
        ".",
        "source",
        "command",
        "type",
        "local",
        "shift",
        ":",
        "unalias",
        "read",
        "wait",
        "typeset",
        "declare",
        "readonly",
        "print",
        "whence",
        "setopt",
        "unsetopt",
        "builtin",
    }
)
# Words that run or rebind a command the parser never sees, and compound keywords it skips.
_REFUSED_WORDS = frozenset(
    {"eval", "trap", "emulate", "autoload", "hash", "case", "select", "function", "coproc", "[["}
)
_SKIPPED_KEYWORDS = frozenset(
    {"{", "}", "(", ")", "!", "if", "then", "elif", "else", "fi", "while", "until", "do", "done"}
)
_OPENERS = frozenset({"{", "(", "if", "while", "until"})
_CLOSERS = frozenset({"}", ")", "fi", "done"})
_PRECOMMAND_WORDS = frozenset({"noglob", "nocorrect"})
_DECLARERS = frozenset({"export", "declare", "typeset", "local", "readonly"})
_OPERATOR_CHARS = frozenset(";&|()<>\n")
_OPERATORS = ("&&", "||", ";;", ">>", "<<", ">&", "<&", "&>", ">|")
_SEPARATORS = frozenset({";", "&", "|", "&&", "||", ";;", "\n"})
_REDIRECTIONS = frozenset({"<", ">", ">>", "<<", "<&", ">&", "&>", ">|"})
_UNPARSEABLE_TEXT = ("$(", "`", "<(", ">(")
_PATH_ASSIGNMENT = re.compile(r"^(PATH|path)\+?=")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_FUNCTION_NAMES = re.compile(
    r"^\s*(?:([A-Za-z_][\w.-]*)\s*\(\s*\)|function\s+([A-Za-z_][\w.-]*))", re.MULTILINE
)
_PATH_REASON = "assigns PATH; pass the PATH through env= instead"


def _tokens(script: str) -> list[str]:
    """Words and single operators; ValueError on an unclosed quote."""
    lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    # With `#` as a comment char a comment would swallow the newline and hide the next command.
    lexer.commenters = ""
    tokens: list[str] = []
    for token in lexer:
        if not set(token) <= _OPERATOR_CHARS:
            tokens.append(token)
            continue
        # the lexer glues adjacent operator characters (`;(`, `);`, `()`): split them
        position = 0
        while position < len(token):
            operator = next((op for op in _OPERATORS if token.startswith(op, position)), None)
            operator = operator or token[position]
            tokens.append(operator)
            position += len(operator)
    return tokens


def _is_operator(token: str) -> bool:
    return bool(token) and set(token) <= _OPERATOR_CHARS


def _without_redirections(words: Sequence[str]) -> list[str]:
    """Drop redirection operators with their targets and the fd words before them."""
    kept: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        following = words[index + 1 : index + 2]
        if word in _REDIRECTIONS:
            index += 2
        elif word.isdigit() and following and following[0] in _REDIRECTIONS:
            index += 1
        else:
            kept.append(word)
            index += 1
    return kept


class _ScriptChecker:
    def __init__(
        self, script: str, env: Mapping[str, str] | None, cwd: object, policy: LaunchPolicy
    ) -> None:
        self.script = script
        self.env = env
        self.cwd = cwd
        self.policy = policy
        self.functions: set[str] = set()
        # How deep the parser is inside `{ }`, `( )`, `if`, `while`, `until` and `for` bodies.
        self.depth = 0

    def refuse(self, reason: str) -> AssertionError:
        return AssertionError(
            f"the suite tried to run a shell script the guard cannot check ({reason}); "
            f"move it into a file under tmp_path and run it as bash <file>: {self.script!r:.200}"
        )

    def launch(self, argv: list[str], *, missing_ok: bool) -> None:
        check_launch(argv, env=self.env, cwd=self.cwd, policy=self.policy, missing_ok=missing_ok)

    def run(self) -> None:
        if not self.script.strip():
            raise self.refuse("the script is empty")
        if any(text in self.script for text in _UNPARSEABLE_TEXT):
            raise self.refuse("it uses command or process substitution")
        try:
            tokens = _tokens(self.script)
        except ValueError as error:
            raise self.refuse(f"it does not parse: {error}") from error
        command: list[str] = []
        for token in [*tokens, "\n"]:
            if token not in _SEPARATORS:
                command.append(token)
            elif command:
                self.command(command)
                command = []

    def command(self, words: list[str]) -> None:
        index = 0
        while index < len(words):
            word = words[index]
            following = words[index + 1 : index + 2]
            if word in _REDIRECTIONS:
                index += 2
            elif word.isdigit() and following and following[0] in _REDIRECTIONS:
                # `2>&1`: an fd; the lexer cannot tell `2>x` from `2 >x`, so the word is also
                # checked as a program that may not be a host one
                self.launch([word], missing_ok=True)
                index += 1
            elif _PATH_ASSIGNMENT.match(word):
                raise self.refuse(_PATH_REASON)
            elif _ASSIGNMENT.match(word):
                index += 1
            elif words[index + 1 : index + 3] == ["(", ")"] and not _is_operator(word):
                # `name ( )`: a function counts from here on, and only when defined at the top
                # level; a nested or conditional one may never run, so its name stays unknown
                if self.depth == 0:
                    self.functions.add(word)
                index += 3
            elif word in _SKIPPED_KEYWORDS:
                self.depth += (word in _OPENERS) - (word in _CLOSERS)
                index += 1
            elif word == "time":
                index += 2 if words[index + 1 : index + 2] == ["-p"] else 1
            elif word in _PRECOMMAND_WORDS:
                self.launch([word], missing_ok=True)
                index += 1
            else:
                self.word(word, words[index + 1 :])
                return

    def word(self, word: str, rest: list[str]) -> None:
        if word in _REFUSED_WORDS:
            raise self.refuse(f"{word} can run a command the guard cannot see")
        if word == "for":
            self.depth += 1  # closed by its `done`
            return
        if _PATH_ASSIGNMENT.match(word):
            raise self.refuse(_PATH_REASON)
        if word in ("command", "builtin", "exec"):
            if word == "command" and rest[:1] in (["-v"], ["-V"]):
                return
            self.command(rest)
        elif word == "alias":
            if any("=" in argument for argument in rest):
                raise self.refuse("an alias definition rebinds a command")
        elif word in _DECLARERS:
            if any(_PATH_ASSIGNMENT.match(argument) for argument in rest):
                raise self.refuse(_PATH_REASON)
        elif word in (".", "source"):
            self.source(_without_redirections(rest))
        elif word not in self.functions and word not in SHELL_BUILTINS:
            self.launch([word, *_without_redirections(rest)], missing_ok=False)

    def source(self, arguments: list[str]) -> None:
        if not arguments:
            raise self.refuse("source has no file")
        base = Path(self.cwd if isinstance(self.cwd, (str, Path)) else os.getcwd())
        target = _real(base / arguments[0])
        refusal = _check_file(target, self.env, base, self.policy)
        if refusal is not None:
            if target.is_relative_to(self.policy.checkout):
                raise refusal
            raise self.refuse(f"it sources {target}, outside tmp_path and the checkout scripts")
        if target.is_relative_to(self.policy.checkout):
            try:
                text = target.read_text()
            except (OSError, UnicodeDecodeError):
                return
            for match in _FUNCTION_NAMES.finditer(text):
                self.functions.add(match.group(1) or match.group(2))


def check_script(
    script: str, *, env: Mapping[str, str] | None, cwd: object, policy: LaunchPolicy
) -> None:
    """Check every command word of an `sh -c` script, strictly and function-aware."""
    _ScriptChecker(script, env, cwd, policy).run()


# Long options that change no file the shell reads before its script.
_KNOWN_LONG_SHELL_OPTIONS = frozenset({"--norc", "--noprofile", "--posix", "--noediting"})


def check_shell_args(
    rest: Sequence[str],
    *,
    env: Mapping[str, str] | None,
    cwd: object,
    policy: LaunchPolicy,
) -> None:
    """Check what an allowlisted shell is asked to run (its argv after the program)."""
    index = 0
    no_exec = False
    command = False
    while index < len(rest):
        word = rest[index]
        if word == "--":
            index += 1
            break
        if word.startswith("--"):
            # `--rcfile`/`--init-file` and any option the guard does not know may run a file
            if word not in _KNOWN_LONG_SHELL_OPTIONS:
                raise AssertionError(f"the guard does not allow the shell option {word}")
            index += 1
        elif word.startswith("-") and len(word) > 1:
            cluster = word[1:]
            if "s" in cluster:
                raise AssertionError(
                    "the suite tried to run a shell script from stdin (-s); "
                    "move it into a file under tmp_path and run it as bash <file>"
                )
            no_exec = no_exec or "n" in cluster
            command = command or "c" in cluster
            # a cluster ending in `o` takes the option name as the next word
            index += 2 if cluster.endswith("o") else 1
        else:
            break
    if no_exec:
        return
    remaining = rest[index:]
    if not remaining:
        raise AssertionError(
            "the suite tried to run a shell with no script; "
            "move the script into a file under tmp_path and run it as bash <file>"
        )
    if command:
        check_script(remaining[0], env=env, cwd=cwd, policy=policy)
        return
    base = Path(cwd if isinstance(cwd, (str, Path)) else os.getcwd())
    refusal = _check_file(_real(base / remaining[0]), env, base, policy)
    if refusal is not None:
        raise refusal


def check_launch(
    args: object,
    *,
    env: Mapping[str, str] | None,
    cwd: object,
    policy: LaunchPolicy,
    shell: bool = False,
    executable: object = None,
    missing_ok: bool = True,
) -> None:
    """Raise AssertionError unless the launch is on the allowlist (judged by real path)."""
    argv = _argv(args, shell)
    program = argv[0]
    if executable is not None:
        program = _text(executable)
    name = Path(program).name
    base = Path(cwd if isinstance(cwd, (str, Path)) else os.getcwd())
    if os.sep in program:
        literal: Path | None = Path(os.path.abspath(base / program))
    else:
        found = _search(program, env, base)
        literal = Path(found) if found is not None else None
    resolved = _real(literal) if literal is not None else None

    # 1. a member (by real path) is allowed itself; the rest of its argv is still checked
    if resolved is not None and resolved in policy.utilities | policy.interpreters:
        rest = argv[1:]
        if resolved in policy.utilities and resolved.name in PREFIX_UTILITIES:
            command = _skip_prefix_options(rest)
            if not command:
                raise AssertionError(f"{name} needs a command")
            check_launch(command, env=env, cwd=cwd, policy=policy, missing_ok=missing_ok)
        elif resolved in policy.interpreters and (
            name in _SHELL_NAMES or resolved != _real(sys.executable)
        ):
            # Every interpreter but the running Python is a shell, whatever its realpath is
            # named (`bash5.2`, a busybox), and so is anything invoked by a shell name.
            check_shell_args(rest, env=env, cwd=cwd, policy=policy)
        return
    # 2. the linuxbrew prefix is refused on every host, whether or not the binary exists
    if (literal is not None and _in_linuxbrew(literal)) or (
        resolved is not None and _in_linuxbrew(resolved)
    ):
        raise _host_refusal(name, resolved if resolved is not None else Path(program))
    # 3. nothing can run: Popen raises FileNotFoundError, which some tests exercise on purpose
    if resolved is None or not resolved.exists():
        if missing_ok:
            return
        raise AssertionError(
            f"the suite tried to run {name}, which exists nowhere; "
            "plant a fake under tmp_path instead"
        )
    # 4. the base temp and the reviewed checkout files; 5. anything else is a host program
    refusal = _check_file(resolved, env, base, policy)
    if refusal is not None:
        raise refusal


# --- the refusal registry: a refusal that production code catches must still fail the test ---

# Process-wide, so a refusal raised in a Textual worker thread is recorded too; appends are
# atomic under the GIL. The wired guards record, then raise; the pure checks above do not.
_REFUSALS: list[str] = []


def record_refusal(message: str) -> None:
    _REFUSALS.append(message)


def take_refusals() -> tuple[str, ...]:
    """Return the recorded refusals and forget exactly those."""
    taken = tuple(_REFUSALS)
    del _REFUSALS[: len(taken)]
    return taken


def fail_on_refusals() -> None:
    """Fail the running test when any refusal was recorded, even one the code under test caught."""
    taken = take_refusals()
    if taken:
        pytest.fail(
            f"{len(taken)} launch refusal(s) in this test; the first: {taken[0]}\n"
            "a broad except in the code under test caught a guard refusal; "
            "plant a fake under tmp_path instead",
            pytrace=False,
        )


@contextlib.contextmanager
def refused(match: str) -> Generator[None]:
    """Expect a wired refusal matching `match` in the block and consume exactly those entries."""
    start = len(_REFUSALS)
    try:
        yield
    except AssertionError as error:
        if re.search(match, str(error)) is None:
            raise
    else:
        pytest.fail(f"expected a launch refusal matching {match!r}; none was raised", pytrace=False)
    block = _REFUSALS[start:]
    if not any(re.search(match, message) for message in block):
        pytest.fail(f"no launch refusal matching {match!r} was recorded", pytrace=False)
    _REFUSALS[start:] = [message for message in block if re.search(match, message) is None]


# --- the socket guard: no internet socket and no name lookup in a test (SPEC R8, D-22) ---

INTERNET_FAMILIES = frozenset({socket.AF_INET, socket.AF_INET6})


def nodeid_of(request: pytest.FixtureRequest) -> str:
    """The running test's node id; pytest leaves `FixtureRequest.node` untyped."""
    return str(cast(Any, request).node.nodeid)


def guarded_socket_init(
    original: Callable[..., None], describe: Callable[[], str]
) -> Callable[..., None]:
    """A `socket.socket.__init__` replacement that refuses internet families.

    `*args` rather than named parameters: the socket signature has a `type` parameter and callers
    pass any of the four by keyword. The default family (no fileno) is AF_INET; a fileno with no
    family is a descriptor that already exists (socketpair, fromfd), so it passes.
    """

    def init(self: socket.socket, *args: Any, **kwargs: Any) -> None:
        family = kwargs.get("family", args[0] if args else -1)
        fileno = kwargs.get("fileno", args[3] if len(args) > 3 else None)
        if family == -1 and fileno is None:
            family = socket.AF_INET
        if family in INTERNET_FAMILIES:
            message = (
                f"the test {describe()} tried to open an internet socket "
                f"({getattr(family, 'name', family)}); fake the network call instead"
            )
            record_refusal(message)
            raise AssertionError(message)
        original(self, *args, **kwargs)

    return init


# Every resolver entry point: each is its own C function, and getfqdn calls gethostbyaddr.
NAME_LOOKUPS = (
    "getaddrinfo",
    "gethostbyname",
    "gethostbyname_ex",
    "gethostbyaddr",
    "getnameinfo",
    "getfqdn",
)


def guarded_name_lookup(describe: Callable[[], str]) -> Callable[..., NoReturn]:
    """A replacement for each of NAME_LOOKUPS: no DNS query leaves the host."""

    def lookup(host: object = "", *_args: Any, **_kwargs: Any) -> NoReturn:
        message = f"the test {describe()} tried to resolve {host!r}; fake the network call instead"
        record_refusal(message)
        raise AssertionError(message)

    return lookup


# --- the os launchers: the same allowlist as subprocess.Popen (SPEC R6, D-21) ---

# Names the base temp for tests/child_guard/sitecustomize.py, which guards Python children.
CHILD_GUARD_ROOT_ENV = "TOOLS_INSTALLER_TEST_ALLOWED_ROOT"

# execl*/spawnl* are pure-Python wrappers over these (through module globals), so they are covered.
GUARDED_OS_FUNCTIONS = (
    "system",
    "execv",
    "execve",
    "execvp",
    "execvpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "posix_spawn",
    "posix_spawnp",
)


def guarded_os_call(
    name: str,
    original: Callable[..., Any],
    check: Callable[[list[str], Mapping[str, str] | None], None],
) -> Callable[..., Any]:
    """Wrap an os launcher: build its argv (command, path and arguments through `os.fsdecode`),
    `check` it, record a refusal before re-raising, then call `original` with the untouched
    arguments. The check is pure, so a Popen that already passed may pass again at `posix_spawn`."""
    first = 1 if name.startswith("spawn") else 0  # spawn* takes a mode before the path
    has_env = name.endswith("e") or name.startswith("posix_spawn")
    needed = 1 if name == "system" else first + (3 if has_env else 2)

    def call(*args: Any, **kwargs: Any) -> Any:
        try:
            if len(args) < needed:
                raise AssertionError(f"the guard needs os.{name} called with positional arguments")
            if name == "system":
                argv = ["/bin/sh", "-c", os.fsdecode(args[0])]
            else:
                argv = [os.fsdecode(args[first]), *(os.fsdecode(a) for a in args[first + 1][1:])]
            # subprocess passes env=None to os.posix_spawn to inherit the environment
            raw_env = args[first + 2] if has_env else None
            env = (
                None
                if raw_env is None
                else {os.fsdecode(k): os.fsdecode(v) for k, v in raw_env.items()}
            )
            check(argv, env)
        except AssertionError as refusal:
            record_refusal(str(refusal))
            raise
        return original(*args, **kwargs)

    return call


# --- the test PATH and environment (23.1 D-16, D-17): applied before collection ---

RUN_USER = Path("/run/user")
# Stash names start with TOOLS_INSTALLER_TEST_, which no cleared prefix matches; values are paths.
OVERRIDES_STASH = "TOOLS_INSTALLER_TEST_HOME_OVERRIDES"
INTERPRETER_DIR_STASH = "TOOLS_INSTALLER_TEST_INTERPRETER_DIR"
HOST_ZSH_STASH = "TOOLS_INSTALLER_TEST_HOST_ZSH"
HOME_OVERRIDE_NAMES = ("UV_TOOL_DIR", "PNPM_HOME", "VOLTA_HOME")
CLEARED_ENV_NAMES: frozenset[str] = frozenset(
    {
        "CLAUDE_CONFIG_DIR",
        "CODEX_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "ZDOTDIR",
        "ZSH",
        "PNPM_HOME",
        "VOLTA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)
# Start-of-name, case-sensitive; `npm_config_` is matched case-insensitively in env_names_to_clear.
CLEARED_ENV_PREFIXES = ("OPENCODE_CONFIG", "UV_", "HOMEBREW_")
INTERPRETER_NAMES = ("sh", "bash", "zsh")


def host_free_path(
    path_value: str,
    *,
    real_home: Path,
    linuxbrew: Path = LINUXBREW_PREFIX,
    keep: Path | None = None,
) -> str:
    """PATH without the real home, /run/user and the linuxbrew prefix, judged by resolved path.

    `keep` survives even under the real home (an interpreter link dir may sit in TMPDIR there).
    Entries keep their order; a symlink loop is handled by realpath.
    """
    roots = (
        Path(os.path.realpath(real_home)),
        RUN_USER,
        Path(os.path.realpath(linuxbrew)),
        linuxbrew,
    )
    kept_dir = Path(os.path.realpath(keep)) if keep is not None else None
    kept: list[str] = []
    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        resolved = Path(os.path.realpath(entry))
        if resolved == kept_dir or not any(resolved.is_relative_to(root) for root in roots):
            kept.append(entry)
    return os.pathsep.join(kept)


def sandboxed_path(path_value: str, *, real_home: Path, interpreter_dir: Path | None) -> str:
    """The test PATH: host-free, with the interpreter link dir first and exactly once."""
    kept = host_free_path(path_value, real_home=real_home, keep=interpreter_dir)
    if interpreter_dir is None:
        return kept
    rest = [entry for entry in kept.split(os.pathsep) if entry and entry != str(interpreter_dir)]
    return os.pathsep.join([str(interpreter_dir), *rest])


def env_names_to_clear(environ: Mapping[str, str]) -> tuple[str, ...]:
    """The names a test must not inherit, sorted. Only names are returned, never values."""
    return tuple(
        sorted(
            name
            for name in environ
            if name in CLEARED_ENV_NAMES
            or name.startswith(CLEARED_ENV_PREFIXES)
            or name.lower().startswith("npm_config_")
        )
    )


def capture_home_overrides(environ: Mapping[str, str]) -> dict[str, str | None]:
    """The fingerprint's toolchain overrides: the parent's stash when set, else the live values."""
    stashed = environ.get(OVERRIDES_STASH)
    if stashed is not None:
        loaded: dict[str, str | None] = json.loads(stashed)
        return loaded
    return {name: environ.get(name) for name in HOME_OVERRIDE_NAMES}


def link_interpreters(link_dir: Path, *, stripped_path: str, original_path: str) -> bool:
    """Link each shell the stripped PATH no longer finds to where the original PATH found it.

    Returns whether a link was made. `python3` is never linked: tests use `sys.executable`.
    """
    made = False
    for name in INTERPRETER_NAMES:
        if shutil.which(name, path=stripped_path) is not None:
            continue
        found = shutil.which(name, path=original_path)
        if found is not None:
            (link_dir / name).symlink_to(os.path.realpath(found))
            made = True
    return made


def host_zsh_stash(path_value: str) -> str:
    """The host's zsh by realpath, read before any strip; "" when the host has none."""
    found = shutil.which("zsh", path=path_value)
    return os.path.realpath(found) if found is not None else ""


def host_zsh() -> Path | None:
    """The host's own zsh as recorded before the strip; the live lookup when no stash is set."""
    if HOST_ZSH_STASH in os.environ:
        recorded = os.environ[HOST_ZSH_STASH]
        return Path(recorded) if recorded else None
    found = shutil.which("zsh")
    return Path(os.path.realpath(found)) if found is not None else None


def prepare_interpreter_dir(
    environ: MutableMapping[str, str], *, real_home: Path, make_dir: Callable[[], Path]
) -> tuple[Path | None, Path | None]:
    """Return (the link dir this run uses, the dir this process made and must remove).

    A worker reuses the controller's dir from the stash. The first process makes one only when
    a shell needs linking, and writes it to the stash for its workers.
    """
    stashed = environ.get(INTERPRETER_DIR_STASH)
    if stashed and Path(stashed).is_dir():
        return Path(stashed), None
    original = environ.get("PATH", "")
    link = make_dir()
    stripped = host_free_path(original, real_home=real_home)
    if not link_interpreters(link, stripped_path=stripped, original_path=original):
        link.rmdir()
        return None, None
    environ[INTERPRETER_DIR_STASH] = str(link)
    return link, link
