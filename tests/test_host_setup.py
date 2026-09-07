from installer.host_setup import HOST_SETUPS


def test_host_setup_is_reserved_for_non_skill_interactive_host_configuration() -> None:
    assert set(HOST_SETUPS) == {"pi"}
