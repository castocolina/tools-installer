from installer.host_setup import HOST_SETUPS


def test_host_setup_is_reserved_for_non_skill_interactive_host_configuration() -> None:
    assert set(HOST_SETUPS) == {"pi"}


def test_reviewed_handoff_names_one_pnpm_add_command() -> None:
    """G14: the reviewed handoff is the one source of a pnpm hint."""
    from installer.host_setup import pnpm_add_command

    assert pnpm_add_command("pi") == (
        "pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent"
    )
    assert pnpm_add_command("no-such-setup") is None
