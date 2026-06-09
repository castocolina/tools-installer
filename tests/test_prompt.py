from installer.prompt import CallbackPrompter, Prompter
from installer.selection import Choice


def test_callback_prompter_is_a_prompter():
    prompter: Prompter = CallbackPrompter(
        ask_checkbox=lambda message, choices: [],
        ask_confirm=lambda message: True,
    )
    assert isinstance(prompter, CallbackPrompter)


def test_select_categories_forwards_choices_and_returns_ids():
    seen: list[tuple[str, list[Choice]]] = []

    def ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
        seen.append((message, choices))
        return ["search"]

    def ask_confirm(message: str) -> bool:
        return True

    prompter = CallbackPrompter(ask_checkbox=ask_checkbox, ask_confirm=ask_confirm)
    choices = [Choice(id="search", label="search (2 tools)", checked=False)]
    assert prompter.select_categories(choices) == ["search"]
    assert seen[0][1] == choices


def test_select_tools_forwards_choices():
    captured: list[list[Choice]] = []

    def ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
        captured.append(choices)
        return ["rg"]

    prompter = CallbackPrompter(ask_checkbox=ask_checkbox, ask_confirm=lambda message: False)
    choices = [Choice(id="rg", label="rg (missing)", checked=True)]
    assert prompter.select_tools(choices) == ["rg"]
    assert captured[0] == choices


def test_confirm_forwards_message():
    seen: list[str] = []

    def ask_confirm(message: str) -> bool:
        seen.append(message)
        return True

    prompter = CallbackPrompter(ask_checkbox=lambda message, choices: [], ask_confirm=ask_confirm)
    assert prompter.confirm("Proceed?") is True
    assert seen == ["Proceed?"]
