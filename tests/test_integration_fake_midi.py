from __future__ import annotations

from syntakt_controller.controllers.main_controller import MainController


class FakeMidiService:
    def __init__(self) -> None:
        self.opened_port: str | None = None
        self.sent_messages: list[tuple[int, int, int]] = []

    def list_output_ports(self) -> list[str]:
        return ["Fake Device A", "Fake Device B"]

    def open_output(self, port_name: str) -> None:
        self.opened_port = port_name

    def send_control_change(self, channel: int, control: int, value: int) -> None:
        self.sent_messages.append((channel, control, value))


def test_integration_controller_event_flow_with_fake_midi() -> None:
    service = FakeMidiService()
    controller = MainController(midi_service=service)

    controller.on_parameter_changed("Track/Session/Output Port", "Fake Device B")
    controller.on_parameter_changed("Track/Session/Track Channel", "3")
    controller.on_parameter_changed("Track/Trig/Velocity", 96)
    controller.on_parameter_changed("Track/LFO 1/Depth", 1024)

    assert service.opened_port == "Fake Device B"
    assert controller.app_state.selected_track_channel == 3
    assert service.sent_messages == [
        (2, 4, 96),
        (2, 109, 8),
        (2, 61, 0),
    ]
