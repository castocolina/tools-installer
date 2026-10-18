"""Prompting abstraction. Pure: real terminal IO is injected as callbacks."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

# Ask a yes/no question; return the answer.
AskConfirm = Callable[[str], bool]


class Prompter(Protocol):
    def confirm(self, message: str) -> bool: ...


@dataclass(frozen=True)
class CallbackPrompter:
    ask_confirm: AskConfirm

    def confirm(self, message: str) -> bool:
        return self.ask_confirm(message)
