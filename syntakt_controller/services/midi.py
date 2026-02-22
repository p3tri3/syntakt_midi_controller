from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class MidiService(Protocol):
    def list_output_ports(self) -> list[str]: ...

    def open_output(self, port_name: str) -> None: ...

    def send_control_change(self, channel: int, control: int, value: int) -> None: ...


@dataclass
class NullMidiService:
    """Safe default service for UI development and CI.

    It records outgoing messages in memory instead of talking to hardware.
    """

    sent_messages: list[tuple[int, int, int]]

    def __init__(self) -> None:
        self.sent_messages = []

    def list_output_ports(self) -> list[str]:
        return ["No Device (Development)"]

    def open_output(self, port_name: str) -> None:
        pass  # no-op: no hardware in development/CI mode

    def send_control_change(self, channel: int, control: int, value: int) -> None:
        self.sent_messages.append((channel, control, value))


class MidoMidiService:
    """Runtime MIDI service using mido/python-rtmidi.

    Kept separate from UI and not used by default in tests.
    """

    def __init__(self) -> None:
        try:
            import mido  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - integration path
            raise RuntimeError("mido is not installed") from exc

        self._mido = mido
        self._port: Any | None = None  # mido port has no stable public stub type

    def list_output_ports(self) -> list[str]:
        return list(self._mido.get_output_names())

    def open_output(self, port_name: str) -> None:
        self._port = self._mido.open_output(port_name)

    def send_control_change(self, channel: int, control: int, value: int) -> None:
        if self._port is None:
            raise RuntimeError("No MIDI output port is open. Select a port first.")
        msg = self._mido.Message("control_change", channel=channel, control=control, value=value)
        self._port.send(msg)
