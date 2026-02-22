from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from syntakt_controller.controller_models import (
    DEFAULT_OUTPUT_PORT,
    AppState,
    ParameterValue,
    app_layout_definition,
)
from syntakt_controller.services.midi import MidiService
from syntakt_controller.services.parameter_mapping import (
    ParameterMappingIndex,
    load_parameter_mapping_index,
)

_log = logging.getLogger(__name__)


@dataclass
class MainController:
    midi_service: MidiService
    mapping_index: ParameterMappingIndex = field(default_factory=load_parameter_mapping_index)
    app_state: AppState = field(default_factory=AppState)
    _status_listener: Callable[[str, bool], None] | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        _validate_layout_mappings(self.mapping_index)

    @property
    def selected_channel(self) -> int:
        return self.app_state.selected_midi_channel

    def available_ports(self) -> list[str]:
        return self.midi_service.list_output_ports()

    def preferred_output_port(self) -> str | None:
        """Return DEFAULT_OUTPUT_PORT if it appears in the available port list."""
        return DEFAULT_OUTPUT_PORT if DEFAULT_OUTPUT_PORT in self.available_ports() else None

    def set_status_listener(self, listener: Callable[[str, bool], None]) -> None:
        self._status_listener = listener

    def on_parameter_changed(self, key: str, value: int | bool | str) -> None:
        self._update_app_state(key, value)

        if key == "Track/Session/Output Port":
            self._handle_output_port_selection(value)
            return

        mapping = self.mapping_index.get(key)
        if mapping is None or mapping.cc_msb is None:
            return

        # NRPN path: preferred when enabled and NRPN address is available.
        if (
            self.app_state.use_nrpn
            and mapping.nrpn_msb is not None
            and mapping.nrpn_lsb is not None
        ):
            midi_value = _to_midi_value(value)
            if midi_value is None:
                return
            if self._send_nrpn(
                self.selected_channel, mapping.nrpn_msb, mapping.nrpn_lsb, midi_value
            ):
                self._set_status(f"Sent NRPN {mapping.nrpn_msb}/{mapping.nrpn_lsb} for {key}")
            return

        # 14-bit CC path.
        if mapping.cc_lsb is not None:
            high_res_value = _to_high_resolution_midi_value(value)
            if high_res_value is None:
                return
            msb_value = (high_res_value >> 7) & 0x7F
            lsb_value = high_res_value & 0x7F
            send_msb_ok = self._send_control_change(
                self.selected_channel,
                mapping.cc_msb,
                msb_value,
            )
            send_lsb_ok = self._send_control_change(
                self.selected_channel,
                mapping.cc_lsb,
                lsb_value,
            )
            if send_msb_ok and send_lsb_ok:
                self._set_status(f"Sent high-resolution CC for {key}")
            return

        # 7-bit CC path.
        midi_value = _to_midi_value(value)
        if midi_value is None:
            return
        if self._send_control_change(self.selected_channel, mapping.cc_msb, midi_value):
            self._set_status(f"Sent CC {mapping.cc_msb} for {key}")

    def send_test_ping(self) -> None:
        """Explicitly test MIDI path without requiring full mapping logic."""
        if self._send_control_change(self.selected_channel, 95, 100):
            self._set_status("Test ping sent")

    def _update_app_state(self, key: str, value: ParameterValue) -> None:
        self.app_state.current_values[key] = value

        if key == "Track/Session/Track Channel":
            parsed_channel = _to_track_channel(value)
            if parsed_channel is not None:
                self.app_state.selected_track_channel = parsed_channel
            return

        if key == "Track/Session/Output Port" and isinstance(value, str):
            self.app_state.selected_output_port = value

    def _handle_output_port_selection(self, value: ParameterValue) -> None:
        if not isinstance(value, str):
            return

        try:
            self.midi_service.open_output(value)
        except Exception as exc:
            self._set_error(f"Failed to open MIDI port '{value}': {exc}")
            return

        self._set_status(f"Opened MIDI port: {value}")

    def _send_control_change(self, channel: int, control: int, value: int) -> bool:
        _log.debug(
            "Sending MIDI CC: channel=%d control=%d value=%d",
            channel,
            control,
            value,
        )
        try:
            self.midi_service.send_control_change(channel, control, value)
        except Exception as exc:
            self._set_error(
                f"Failed to send MIDI CC (ch={channel}, cc={control}, value={value}): {exc}"
            )
            return False
        return True

    def _send_nrpn(self, channel: int, nrpn_msb: int, nrpn_lsb: int, value: int) -> bool:
        """Send a 7-bit value via the 4-message NRPN sequence (CC 99, 98, 6, 38)."""
        results = [
            self._send_control_change(channel, 99, nrpn_msb),
            self._send_control_change(channel, 98, nrpn_lsb),
            self._send_control_change(channel, 6, value),
            self._send_control_change(channel, 38, 0),
        ]
        return all(results)

    def _set_status(self, message: str) -> None:
        self.app_state.last_status = message
        self.app_state.last_error = None
        if self._status_listener is not None:
            self._status_listener(message, False)

    def _set_error(self, message: str) -> None:
        self.app_state.last_error = message
        self.app_state.last_status = message
        if self._status_listener is not None:
            self._status_listener(message, True)


def _validate_layout_mappings(index: ParameterMappingIndex) -> None:
    """Warn at startup for any layout parameter key that has no MIDI mapping."""
    for tab in app_layout_definition():
        for group in tab.groups:
            if group.name == "Session":
                continue  # Session controls (port, channel, program) are handled outside CSV
            for param in group.parameters:
                key = f"{tab.name}/{group.name}/{param.name}"
                if index.get(key) is None:
                    _log.warning("No MIDI mapping for UI parameter key: %s", key)


def _to_midi_value(value: int | bool | str) -> int | None:
    # bool must be checked before int because bool is a subclass of int in Python.
    if isinstance(value, bool):
        return 127 if value else 0
    if isinstance(value, int):
        return max(0, min(127, value))
    if value.isdigit():
        as_int = int(value)
        return max(0, min(127, as_int))
    return None


def _to_high_resolution_midi_value(value: int | bool | str) -> int | None:
    if isinstance(value, bool):
        return 16383 if value else 0
    if isinstance(value, int):
        return max(0, min(16383, value))
    if value.isdigit():
        as_int = int(value)
        return max(0, min(16383, as_int))
    return None


def _to_track_channel(value: int | bool | str) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(1, min(16, value))
    if value.isdigit():
        as_int = int(value)
        return max(1, min(16, as_int))
    return None
