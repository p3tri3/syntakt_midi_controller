from __future__ import annotations

import logging

import pytest

from syntakt_controller.controllers.main_controller import MainController
from syntakt_controller.services.midi import NullMidiService


class FailingSendMidiService:
    def list_output_ports(self) -> list[str]:
        return ["Broken Port"]

    def open_output(self, port_name: str) -> None:
        pass

    def send_control_change(self, channel: int, control: int, value: int) -> None:
        raise RuntimeError("send failed")


class FailingOpenMidiService(NullMidiService):
    def open_output(self, port_name: str) -> None:
        raise RuntimeError("open failed")


class FailOnSpecificControlMidiService(NullMidiService):
    def __init__(self, failing_control: int) -> None:
        super().__init__()
        self.failing_control = failing_control

    def send_control_change(self, channel: int, control: int, value: int) -> None:
        self.sent_messages.append((channel, control, value))
        if control == self.failing_control:
            raise RuntimeError(f"send failed for control {control}")


def test_controller_lists_ports_from_service() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)
    assert controller.available_ports() == ["No Device (Development)"]


def test_controller_can_send_test_ping() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.send_test_ping()

    assert service.sent_messages == [(13, 95, 100)]


def test_controller_sends_mapped_slider_value() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert service.sent_messages == [(13, 4, 64)]


def test_controller_sends_mapped_toggle_value() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Trig/Filter Trig", True)
    controller.on_parameter_changed("Track/Trig/Filter Trig", False)

    assert service.sent_messages == [(13, 13, 127), (13, 13, 0)]


def test_controller_ignores_unmapped_or_non_numeric_combo_values() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Session/Output Port", "No Device (Development)")
    controller.on_parameter_changed("Track/Filter/Filter Type", "N/A (v1)")

    assert service.sent_messages == []
    assert controller.app_state.selected_output_port == "No Device (Development)"


def test_controller_sends_high_resolution_cc_for_applicable_parameters() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/LFO 1/Depth", 16383)

    assert service.sent_messages == [(13, 109, 127), (13, 61, 127)]


def test_controller_14bit_values_below_128_split_correctly() -> None:
    # Values ≤ 127 must still use the full MSB/LSB split, not be sent raw as MSB.
    # value=64: MSB = 64 >> 7 = 0, LSB = 64 & 0x7F = 64 (not MSB=64, LSB=0).
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/LFO 1/Depth", 64)

    assert service.sent_messages == [(13, 109, 0), (13, 61, 64)]


def test_controller_clamps_high_resolution_cc_values() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/LFO 1/Depth", 99999)
    controller.on_parameter_changed("Track/LFO 1/Depth", -5)

    assert service.sent_messages == [
        (13, 109, 127),
        (13, 61, 127),
        (13, 109, 0),
        (13, 61, 0),
    ]


def test_controller_updates_selected_channel_from_app_state() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Session/Track Channel", "3")
    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert controller.app_state.selected_track_channel == 3
    assert controller.selected_channel == 2
    assert service.sent_messages == [(2, 4, 64)]


def test_controller_ignores_bool_track_channel_value() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Session/Track Channel", True)
    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert controller.app_state.selected_track_channel == 14
    assert controller.selected_channel == 13
    assert service.sent_messages == [(13, 4, 64)]


def test_controller_tracks_current_values_for_events() -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Trig/Note", 48)
    controller.on_parameter_changed("Track/Trig/Filter Trig", True)

    assert controller.app_state.current_values["Track/Trig/Note"] == 48
    assert controller.app_state.current_values["Track/Trig/Filter Trig"] is True


def test_controller_sets_error_status_when_midi_send_fails() -> None:
    controller = MainController(midi_service=FailingSendMidiService())

    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert controller.app_state.last_error is not None
    assert "Failed to send MIDI CC" in controller.app_state.last_error


def test_controller_sends_cc_for_named_combo_integer_index() -> None:
    # Named combo parameters (e.g. Filter Type) now send their selection index as an
    # integer. Verify the index is forwarded as the CC value (CC 76 for Filter Type).
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Filter/Filter Type", 1)  # LP1 = index 1

    assert service.sent_messages == [(13, 76, 1)]


def test_controller_sends_nrpn_when_use_nrpn_enabled() -> None:
    # Velocity: nrpn_msb=3, nrpn_lsb=1 per spec. Expect the 4-message NRPN sequence.
    service = NullMidiService()
    controller = MainController(midi_service=service)
    controller.app_state.use_nrpn = True

    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert service.sent_messages == [
        (13, 99, 3),  # NRPN MSB
        (13, 98, 1),  # NRPN LSB
        (13, 6, 64),  # Data Entry MSB (value)
        (13, 38, 0),  # Data Entry LSB (0 for 7-bit)
    ]


def test_controller_falls_back_to_cc_when_no_nrpn_mapping() -> None:
    # Filter Trig has no NRPN mapping (CC-only parameter). Even with use_nrpn=True,
    # the controller must fall back to the CC path.
    service = NullMidiService()
    controller = MainController(midi_service=service)
    controller.app_state.use_nrpn = True

    controller.on_parameter_changed("Track/Trig/Filter Trig", True)

    assert service.sent_messages == [(13, 13, 127)]


def test_controller_uses_cc_by_default_when_use_nrpn_false() -> None:
    # use_nrpn=False (default): must use CC path, not NRPN.
    service = NullMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert service.sent_messages == [(13, 4, 64)]


def test_controller_nrpn_attempts_all_messages_even_if_one_fails() -> None:
    service = FailOnSpecificControlMidiService(failing_control=98)
    controller = MainController(midi_service=service)
    controller.app_state.use_nrpn = True

    controller.on_parameter_changed("Track/Trig/Velocity", 64)

    assert service.sent_messages == [
        (13, 99, 3),
        (13, 98, 1),  # raises, but controller continues with remaining NRPN CCs
        (13, 6, 64),
        (13, 38, 0),
    ]
    assert controller.app_state.last_error is not None
    assert "send failed for control 98" in controller.app_state.last_error


def test_controller_construction_logs_no_unmapped_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # All non-Session layout parameters should resolve in the mapping index.
    with caplog.at_level(
        logging.WARNING,
        logger="syntakt_controller.controllers.main_controller",
    ):
        MainController(midi_service=NullMidiService())

    assert caplog.records == [], [r.message for r in caplog.records]


def test_preferred_output_port_returns_default_when_available() -> None:
    from syntakt_controller.controller_models import DEFAULT_OUTPUT_PORT

    class FixedPortMidiService(NullMidiService):
        def list_output_ports(self) -> list[str]:
            return ["Other Port", DEFAULT_OUTPUT_PORT, "Yet Another Port"]

    controller = MainController(midi_service=FixedPortMidiService())
    assert controller.preferred_output_port() == DEFAULT_OUTPUT_PORT


def test_preferred_output_port_returns_none_when_unavailable() -> None:
    # NullMidiService returns ["No Device (Development)"], not the real device name.
    controller = MainController(midi_service=NullMidiService())
    assert controller.preferred_output_port() is None


def test_controller_sets_error_status_when_output_open_fails() -> None:
    service = FailingOpenMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Session/Output Port", "Broken Port")

    assert controller.app_state.selected_output_port == "Broken Port"
    assert controller.app_state.last_error is not None
    assert "Failed to open MIDI port 'Broken Port'" in controller.app_state.last_error


def test_controller_logs_debug_for_each_outgoing_nrpn_cc_send(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = NullMidiService()
    controller = MainController(midi_service=service)
    controller.app_state.use_nrpn = True

    with caplog.at_level(
        logging.DEBUG,
        logger="syntakt_controller.controllers.main_controller",
    ):
        controller.on_parameter_changed("Track/Trig/Velocity", 64)

    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(debug_records) == 4
    assert all("Sending MIDI CC:" in r.message for r in debug_records)
