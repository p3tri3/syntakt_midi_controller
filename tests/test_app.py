from __future__ import annotations

from syntakt_controller.app import _parse_cli_args
from syntakt_controller.services.midi import NullMidiService


def test_no_flags_returns_false_and_unchanged_argv() -> None:
    no_midi, verbose, qt_argv = _parse_cli_args(["prog"])
    assert not no_midi
    assert not verbose
    assert qt_argv == ["prog"]


def test_no_midi_flag_sets_no_midi() -> None:
    no_midi, verbose, qt_argv = _parse_cli_args(["prog", "--no-midi"])
    assert no_midi
    assert not verbose
    assert "--no-midi" not in qt_argv


def test_no_midi_flag_stripped_leaving_other_flags_intact() -> None:
    no_midi, verbose, qt_argv = _parse_cli_args(["prog", "--no-midi", "-style", "fusion"])
    assert no_midi
    assert not verbose
    assert "--no-midi" not in qt_argv
    assert "-style" in qt_argv
    assert "fusion" in qt_argv


def test_unknown_flags_pass_through_to_qt() -> None:
    _, _, qt_argv = _parse_cli_args(["prog", "-platform", "xcb"])
    assert "-platform" in qt_argv
    assert "xcb" in qt_argv


def test_no_midi_flag_forces_null_service() -> None:
    # Verify _parse_cli_args returns True so the caller selects NullMidiService.
    no_midi, _, _ = _parse_cli_args(["prog", "--no-midi"])
    assert no_midi
    # Constructing NullMidiService is always safe (no hardware required).
    service = NullMidiService()
    assert service.list_output_ports() == ["No Device (Development)"]


def test_verbose_flag_sets_verbose() -> None:
    no_midi, verbose, qt_argv = _parse_cli_args(["prog", "--verbose"])
    assert not no_midi
    assert verbose
    assert "--verbose" not in qt_argv


def test_verbose_short_flag_sets_verbose() -> None:
    no_midi, verbose, qt_argv = _parse_cli_args(["prog", "-v"])
    assert not no_midi
    assert verbose
    assert "-v" not in qt_argv
