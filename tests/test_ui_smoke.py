from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QTabWidget

from syntakt_controller.controllers.main_controller import MainController
from syntakt_controller.services.midi import NullMidiService
from syntakt_controller.ui.main_window import MainWindow


class FailingSendMidiService:
    def list_output_ports(self) -> list[str]:
        return ["No Device (Development)"]

    def open_output(self, port_name: str) -> None:
        pass

    def send_control_change(self, channel: int, control: int, value: int) -> None:
        raise RuntimeError("send failed")


def test_main_window_builds(qt_app) -> None:
    controller = MainController(midi_service=NullMidiService())
    window = MainWindow(controller)

    assert window.windowTitle()
    assert window.centralWidget() is not None
    tabs = window.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 3


def test_combo_boxes_use_real_value_options(qt_app) -> None:
    controller = MainController(midi_service=NullMidiService())
    window = MainWindow(controller)

    output_port_combo = window.findChild(QComboBox, "Track/Session/Output Port")
    assert output_port_combo is not None
    assert output_port_combo.count() >= 1
    assert output_port_combo.itemText(0) == "No Device (Development)"

    track_channel_combo = window.findChild(QComboBox, "Track/Session/Track Channel")
    assert track_channel_combo is not None
    assert track_channel_combo.count() == 16
    assert track_channel_combo.itemText(0) == "1"
    assert track_channel_combo.itemText(15) == "16"


def test_main_window_status_bar_updates_on_controller_error(qt_app) -> None:
    controller = MainController(midi_service=FailingSendMidiService())
    window = MainWindow(controller)

    controller.on_parameter_changed("Track/Trig/Velocity", 100)

    assert "Failed to send MIDI CC" in window.statusBar().currentMessage()
