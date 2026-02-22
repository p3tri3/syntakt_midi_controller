from __future__ import annotations

import argparse
import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from syntakt_controller.controllers.main_controller import MainController
from syntakt_controller.services.midi import MidiService, NullMidiService
from syntakt_controller.ui.main_window import MainWindow


def _parse_cli_args(argv: list[str]) -> tuple[bool, bool, list[str]]:
    """Strip recognised app flags from argv.

    Returns (no_midi_requested, verbose_requested, remaining_argv_for_qt).
    Unknown flags are left in the returned list so QApplication can consume
    Qt-specific ones.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--no-midi",
        action="store_true",
        default=False,
        dest="no_midi",
        help="Use NullMidiService instead of MidoMidiService (no hardware required).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging for outgoing MIDI messages.",
    )
    known, remaining = parser.parse_known_args(argv[1:])
    return bool(known.no_midi), bool(known.verbose), [argv[0], *remaining]


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv if argv is None else argv
    no_midi_flag, verbose_flag, qt_argv = _parse_cli_args(raw)

    if verbose_flag:
        logging.basicConfig(level=logging.DEBUG)

    force_null = no_midi_flag or os.environ.get("SYNTAKT_NO_MIDI", "") in ("1", "true", "yes")

    midi_service: MidiService
    if force_null:
        midi_service = NullMidiService()
    else:
        try:
            from syntakt_controller.services.midi import MidoMidiService  # noqa: PLC0415

            midi_service = MidoMidiService()
        except RuntimeError:
            logging.warning("mido not installed; falling back to NullMidiService")
            midi_service = NullMidiService()

    app = QApplication(qt_argv)
    controller = MainController(midi_service=midi_service)
    window = MainWindow(controller)
    window.show()

    return int(app.exec())
