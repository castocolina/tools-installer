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
