"""The unit-test subprocess allowlist: pure functions, judged by resolved real path.

A test may start only a program that sits under pytest's base temp dir, a script of
this checkout, or an allowlisted interpreter or utility. `tests/conftest.py` wires
`check_launch` into its Popen guard; nothing here runs a process or reads the host
beyond `os.path.realpath`, `shutil.which` and `Path.exists`.

Messages carry program names, paths and script text only, never environment values.
"""

import os
import re
import shlex
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

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


def _under_checkout_roots(path: Path, policy: LaunchPolicy) -> bool:
    return (
        path.is_relative_to(policy.checkout / "scripts")
        or path == policy.checkout / "install.sh"
        or path == policy.checkout / "setup.py"
    )


def _file_allowed(path: Path, policy: LaunchPolicy) -> bool:
    return path.is_relative_to(policy.allowed_root) or _under_checkout_roots(path, policy)


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
        for index in range(1, len(tokens) - 1):
            if tokens[index : index + 2] == ["(", ")"] and not _is_operator(tokens[index - 1]):
                self.functions.add(tokens[index - 1])
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
                index += 3  # `name ( )`: a function header, recorded up front
            elif word in _SKIPPED_KEYWORDS:
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
        if not _file_allowed(target, self.policy):
            raise self.refuse(f"it sources {target}, outside tmp_path and the checkout scripts")
        if _under_checkout_roots(target, self.policy):
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
            index += 1
        elif word.startswith("-") and len(word) > 1:
            cluster = word[1:]
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
    script = _real(base / remaining[0])
    if not _file_allowed(script, policy):
        raise _host_refusal(Path(remaining[0]).name, script)


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
        found = shutil.which(program, path=(env if env is not None else os.environ).get("PATH", ""))
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
        elif resolved in policy.interpreters and resolved.name in _SHELL_NAMES:
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
    # 4. the roots
    if _file_allowed(resolved, policy):
        return
    # 5. anything else is a host program
    raise _host_refusal(name, resolved)
