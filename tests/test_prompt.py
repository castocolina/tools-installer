from installer.prompt import CallbackPrompter, Prompter


def test_callback_prompter_is_a_prompter():
    prompter: Prompter = CallbackPrompter(ask_confirm=lambda message, default: True)
    assert isinstance(prompter, CallbackPrompter)


def test_confirm_forwards_message():
    seen: list[str] = []

    def ask_confirm(message: str, default: bool) -> bool:
        seen.append(message)
        return True

    prompter = CallbackPrompter(ask_confirm=ask_confirm)
    assert prompter.confirm("Proceed?") is True
    assert seen == ["Proceed?"]


def test_callback_prompter_forwards_the_default():
    seen: list[tuple[str, bool]] = []

    def ask_confirm(message: str, default: bool) -> bool:
        seen.append((message, default))
        return default

    prompter = CallbackPrompter(ask_confirm=ask_confirm)
    assert prompter.confirm("q", default=False) is False
    assert prompter.confirm("q") is True
    assert seen == [("q", False), ("q", True)]
