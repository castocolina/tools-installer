"""Prompting abstraction. Pure: real terminal IO is injected as callbacks."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from installer.selection import Choice

# Show a multi-select of `choices` under `message`; return the chosen ids.
AskCheckbox = Callable[[str, list[Choice]], list[str]]
# Ask a yes/no question; return the answer.
AskConfirm = Callable[[str], bool]


class Prompter(Protocol):
    def select_categories(self, choices: list[Choice]) -> list[str]: ...
    def select_tools(self, choices: list[Choice]) -> list[str]: ...
    def confirm(self, message: str) -> bool: ...


@dataclass(frozen=True)
class CallbackPrompter:
    ask_checkbox: AskCheckbox
    ask_confirm: AskConfirm

    def select_categories(self, choices: list[Choice]) -> list[str]:
        return self.ask_checkbox("Select categories", choices)

    def select_tools(self, choices: list[Choice]) -> list[str]:
        return self.ask_checkbox("Select tools", choices)

    def confirm(self, message: str) -> bool:
        return self.ask_confirm(message)
