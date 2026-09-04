import datetime as dt

import pytest

from installer.helper_assets import wait_time


def test_current_time_uses_env_override_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAIT_TIME_NOW", "2026-01-01T10:00:00")
    assert wait_time.current_time() == dt.datetime(2026, 1, 1, 10, 0, 0)


def test_current_time_falls_back_to_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WAIT_TIME_NOW", raising=False)
    before = dt.datetime.now()
    result = wait_time.current_time()
    after = dt.datetime.now()
    assert before <= result <= after


def test_parse_duration_bare_seconds() -> None:
    assert wait_time.parse_duration("120") == 120


def test_parse_duration_rejects_unrecognized_text() -> None:
    assert wait_time.parse_duration("not a duration") is None


def test_parse_duration_rejects_trailing_residue() -> None:
    assert wait_time.parse_duration("5sxyz") is None


def test_parse_clock_simple_hour() -> None:
    assert wait_time.parse_clock("10") == (10, 0, 0, 0)


def test_parse_clock_hour_minute_second() -> None:
    assert wait_time.parse_clock("10:30:15") == (10, 30, 15, 0)


def test_parse_clock_with_colon_microseconds() -> None:
    assert wait_time.parse_clock("10:30:15:123") == (10, 30, 15, 123000)


def test_parse_clock_with_dot_microseconds() -> None:
    assert wait_time.parse_clock("10:30:15.5") == (10, 30, 15, 500000)


def test_parse_clock_am_midnight() -> None:
    assert wait_time.parse_clock("12am") == (0, 0, 0, 0)


def test_parse_clock_pm_noon_stays_twelve() -> None:
    assert wait_time.parse_clock("12pm") == (12, 0, 0, 0)


def test_parse_clock_pm_adds_twelve_hours() -> None:
    assert wait_time.parse_clock("1pm") == (13, 0, 0, 0)


def test_parse_clock_rejects_invalid_twelve_hour_range() -> None:
    with pytest.raises(ValueError, match="12-hour times must use hours 1 through 12"):
        wait_time.parse_clock("13am")


def test_parse_clock_rejects_out_of_range_time() -> None:
    with pytest.raises(ValueError, match="time is outside the valid clock range"):
        wait_time.parse_clock("23:99")


def test_parse_clock_rejects_unmatched_text() -> None:
    with pytest.raises(ValueError, match="expected a duration or target time"):
        wait_time.parse_clock("not a clock")


def test_parse_compact_date_mmdd() -> None:
    base = dt.datetime(2026, 3, 1)
    assert wait_time.parse_compact_date("0704", base) == (2026, 7, 4, True)


def test_parse_compact_date_yymmdd() -> None:
    base = dt.datetime(2026, 3, 1)
    assert wait_time.parse_compact_date("260704", base) == (2026, 7, 4, False)


def test_parse_compact_date_yyyymmdd() -> None:
    base = dt.datetime(2026, 3, 1)
    assert wait_time.parse_compact_date("20260704", base) == (2026, 7, 4, False)


def test_parse_compact_date_rejects_bad_length() -> None:
    with pytest.raises(ValueError, match="dates must be MMDD, YYMMDD, or YYYYMMDD"):
        wait_time.parse_compact_date("704", dt.datetime(2026, 3, 1))


def test_parse_target_same_day_future_time() -> None:
    base = dt.datetime(2026, 3, 1, 8, 0, 0)
    assert wait_time.parse_target("10am", base) == dt.datetime(2026, 3, 1, 10, 0, 0)


def test_parse_target_rolls_to_next_day_when_time_passed() -> None:
    base = dt.datetime(2026, 3, 1, 8, 0, 0)
    assert wait_time.parse_target("7am", base) == dt.datetime(2026, 3, 2, 7, 0, 0)


def test_parse_target_tomorrow_keyword() -> None:
    base = dt.datetime(2026, 3, 1, 8, 0, 0)
    assert wait_time.parse_target("tomorrow 10am", base) == dt.datetime(2026, 3, 2, 10, 0, 0)


def test_parse_target_compact_date_rolls_year_when_in_the_past() -> None:
    base = dt.datetime(2026, 3, 1, 8, 0, 0)
    # "0101" with no year resolves to this year's Jan 1, already past base -> rolls forward.
    assert wait_time.parse_target("0101 10am", base) == dt.datetime(2027, 1, 1, 10, 0, 0)


def test_parse_target_compact_date_future_this_year_does_not_roll() -> None:
    base = dt.datetime(2026, 3, 1, 8, 0, 0)
    assert wait_time.parse_target("0704 10am", base) == dt.datetime(2026, 7, 4, 10, 0, 0)


def test_parse_target_full_date_never_rolls_year() -> None:
    base = dt.datetime(2026, 3, 1, 8, 0, 0)
    assert wait_time.parse_target("20250101 10am", base) == dt.datetime(2025, 1, 1, 10, 0, 0)


def test_parse_target_rejects_unmatched_text() -> None:
    with pytest.raises(ValueError):
        wait_time.parse_target("", dt.datetime(2026, 3, 1))


def test_parse_seconds_empty_argv_is_zero() -> None:
    assert wait_time.parse_seconds([]) == 0


def test_parse_seconds_resolves_a_clock_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAIT_TIME_NOW", "2026-03-01T09:59:00")
    assert wait_time.parse_seconds(["10:00:00"]) == 60


def test_left_time_omits_zero_units() -> None:
    assert wait_time.left_time(45) == "45s"


def test_left_time_includes_all_nonzero_units() -> None:
    assert wait_time.left_time(90061) == "1d 1h 1m 1s"


def test_current_clock_uses_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAIT_TIME_CLOCK", "23:59:59")
    assert wait_time.current_clock() == "23:59:59"


def test_style_for_no_blink_when_far_from_zero() -> None:
    assert wait_time.style_for(50, 100) == ("", "")


def test_render_line_includes_clock_and_remaining(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAIT_TIME_CLOCK", "12:00:00")
    line = wait_time.render_line(45, 100)
    assert "now 12:00:00" in line
    assert "left 45s" in line


def test_usage_prints_all_invocation_forms(capsys: pytest.CaptureFixture[str]) -> None:
    wait_time.usage()
    out = capsys.readouterr().out
    assert "--seconds|--preview" in out
    assert "tomorrow 10am" in out
    assert "YYMMDD-HH:MM" in out


def test_main_help_prints_usage_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert wait_time.main(["--help"]) == 0
    assert "usage: wait_time" in capsys.readouterr().out


def test_main_seconds_mode_prints_integer(capsys: pytest.CaptureFixture[str]) -> None:
    assert wait_time.main(["--seconds", "120"]) == 0
    assert capsys.readouterr().out.strip() == "120"


def test_main_preview_mode_prints_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert wait_time.main(["--preview", "5"]) == 0
    assert "left 5s" in capsys.readouterr().out


def test_main_with_no_args_skips_the_countdown_loop(capsys: pytest.CaptureFixture[str]) -> None:
    assert wait_time.main([]) == 0
    assert capsys.readouterr().out.endswith("\r")


def test_main_counts_down_without_real_sleeping(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(wait_time.time, "sleep", _no_sleep)
    assert wait_time.main(["2"]) == 0
    out = capsys.readouterr().out
    assert "left 2s" in out
    assert "left 1s" in out


def test_main_reports_parse_errors_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    assert wait_time.main(["25:99"]) == 2
    err = capsys.readouterr().err
    assert "wait_time:" in err
