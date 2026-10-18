from installer.prompt import CallbackPrompter, Prompter


def test_callback_prompter_is_a_prompter():
    prompter: Prompter = CallbackPrompter(ask_confirm=lambda message: True)
    assert isinstance(prompter, CallbackPrompter)


def test_confirm_forwards_message():
    seen: list[str] = []

    def ask_confirm(message: str) -> bool:
        seen.append(message)
        return True

    prompter = CallbackPrompter(ask_confirm=ask_confirm)
    assert prompter.confirm("Proceed?") is True
    assert seen == ["Proceed?"]
