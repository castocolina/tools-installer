import pytest

from installer.cli import Options, parse_args


def test_defaults_are_interactive():
    assert parse_args([]) == Options(all=False, categories=(), yes=False)


def test_all_flag():
    assert parse_args(["--all"]) == Options(all=True, categories=(), yes=False)


def test_categories_split_and_trimmed():
    opts = parse_args(["--categories", "search, data , git"])
    assert opts.categories == ("search", "data", "git")


def test_categories_repeatable():
    opts = parse_args(["--categories", "search", "--categories", "data"])
    assert opts.categories == ("search", "data")


def test_categories_drops_empty_tokens():
    opts = parse_args(["--categories", "search,, ,data"])
    assert opts.categories == ("search", "data")


def test_yes_flag():
    assert parse_args(["--yes"]).yes is True


def test_unknown_flag_exits():
    with pytest.raises(SystemExit):
        parse_args(["--nope"])


def test_doctor_defaults_false():
    assert parse_args([]).doctor is False


def test_doctor_flag():
    assert parse_args(["--doctor"]).doctor is True


def test_uninstall_flag_defaults_false():
    assert parse_args([]).uninstall is False


def test_uninstall_flag_parses():
    assert parse_args(["--uninstall"]).uninstall is True


def test_link_mode_defaults_to_none():
    assert parse_args([]).link_mode is None


def test_link_mode_parses_each_choice():
    assert parse_args(["--link-mode", "centralized"]).link_mode == "centralized"
    assert parse_args(["--link-mode", "single"]).link_mode == "single"
    assert parse_args(["--link-mode", "split"]).link_mode == "split"


def test_link_mode_rejects_unknown_choice():
    with pytest.raises(SystemExit):
        parse_args(["--link-mode", "bogus"])
