from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass
class NrpnTracker:
    nrpn_msb: int | None = None
    nrpn_lsb: int | None = None
    data_msb: int | None = None
    data_lsb: int | None = None

    def update_cc(self, control: int, value: int) -> str | None:
        if control == 99:
            self.nrpn_msb = value
            return f"NRPN addr msb={value}"
        if control == 98:
            self.nrpn_lsb = value
            return f"NRPN addr lsb={value}"
        if control == 6:
            self.data_msb = value
            return self._format_nrpn_value(part="MSB")
        if control == 38:
            self.data_lsb = value
            return self._format_nrpn_value(part="LSB")
        return None

    def _format_nrpn_value(self, *, part: str) -> str | None:
        if self.nrpn_msb is None or self.nrpn_lsb is None:
            return f"NRPN data {part} received before address"
        if self.data_msb is None:
            return None
        if self.data_lsb is None:
            value = self.data_msb
            return f"NRPN {self.nrpn_msb}/{self.nrpn_lsb} value={value} (7-bit, Data Entry MSB)"
        value_14 = ((self.data_msb & 0x7F) << 7) | (self.data_lsb & 0x7F)
        return (
            f"NRPN {self.nrpn_msb}/{self.nrpn_lsb} value14={value_14} "
            f"(msb={self.data_msb}, lsb={self.data_lsb})"
        )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Listen on a MIDI input port and print incoming messages to study "
            "whether Syntakt echoes parameter changes (CC/NRPN) from the device."
        )
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List MIDI input ports and exit.",
    )
    parser.add_argument(
        "--input-port",
        dest="input_port",
        help="Exact MIDI input port name to open.",
    )
    parser.add_argument(
        "--match",
        help="Case-insensitive substring match for auto-selecting an input port.",
    )
    parser.add_argument(
        "--channel",
        type=int,
        choices=range(1, 17),
        metavar="{1..16}",
        help="Only show channel messages for the given 1-based MIDI channel.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Seconds to listen before exiting (0 = until Ctrl+C).",
    )
    parser.add_argument(
        "--poll-ms",
        type=float,
        default=10.0,
        help="Polling interval in milliseconds for pending MIDI messages.",
    )
    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Include raw byte data when available.",
    )
    return parser.parse_args(argv)


def _import_mido() -> Any:
    try:
        import mido  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SystemExit(
            "mido is not installed. Install optional MIDI deps first: pip install -e '.[midi]'"
        ) from exc
    return mido


def _select_input_port(
    port_names: list[str],
    *,
    exact: str | None,
    match: str | None,
) -> str:
    if exact:
        if exact not in port_names:
            raise SystemExit(
                "Input port not found: "
                f"{exact!r}\nAvailable input ports:\n- " + "\n- ".join(port_names)
            )
        return exact

    if match:
        lowered = match.lower()
        matches = [name for name in port_names if lowered in name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SystemExit(
                "Multiple input ports matched "
                f"{match!r}:\n- " + "\n- ".join(matches) + "\nUse --input-port."
            )
        raise SystemExit(
            f"No input ports matched {match!r}.\nAvailable input ports:\n- "
            + "\n- ".join(port_names)
        )

    if len(port_names) == 1:
        return port_names[0]

    raise SystemExit(
        "Please choose an input port with --input-port (or --match).\n"
        "Available input ports:\n- " + "\n- ".join(port_names)
    )


def _format_message_line(
    msg: Any,
    *,
    rel_seconds: float,
    show_raw: bool,
    nrpn_trackers: dict[int, NrpnTracker],
) -> str:
    parts = [f"{rel_seconds:8.3f}s", msg.type]

    if hasattr(msg, "channel"):
        parts.append(f"ch={int(msg.channel) + 1}")

    if msg.type == "control_change":
        channel = int(getattr(msg, "channel", 0))
        control = int(msg.control)
        value = int(msg.value)
        parts.append(f"cc={control}")
        parts.append(f"val={value}")
        decoded = nrpn_trackers.setdefault(channel, NrpnTracker()).update_cc(control, value)
        if decoded is not None:
            parts.append(f"[{decoded}]")
    elif msg.type == "program_change":
        parts.append(f"program={int(msg.program)}")
    elif msg.type in {"note_on", "note_off"}:
        parts.append(f"note={int(msg.note)}")
        parts.append(f"vel={int(msg.velocity)}")
    elif msg.type == "pitchwheel":
        parts.append(f"pitch={int(msg.pitch)}")
    else:
        # Fallback for other message types (keeps output compact but useful).
        text = str(msg)
        if text and text != msg.type:
            parts.append(text)

    if show_raw and hasattr(msg, "bytes"):
        try:
            raw_bytes = list(msg.bytes())
        except Exception:
            raw_bytes = []
        if raw_bytes:
            raw_hex = " ".join(f"{byte:02X}" for byte in raw_bytes)
            parts.append(f"raw=[{raw_hex}]")

    return "  ".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    mido = _import_mido()

    input_ports = list(mido.get_input_names())
    if args.list:
        if not input_ports:
            print("No MIDI input ports found.")
            return 0
        print("MIDI input ports:")
        for name in input_ports:
            print(f"- {name}")
        return 0

    if not input_ports:
        print("No MIDI input ports found. Connect the device/interface and try again.")
        return 1

    port_name = _select_input_port(
        input_ports,
        exact=args.input_port,
        match=args.match,
    )

    channel_filter = args.channel - 1 if args.channel is not None else None
    poll_seconds = max(0.001, args.poll_ms / 1000.0)
    deadline = None if args.duration <= 0 else (time.monotonic() + args.duration)

    print(f"Listening on input port: {port_name}")
    print("Move knobs on the Syntakt and watch for incoming CC/NRPN messages.")
    print("Press Ctrl+C to stop." if deadline is None else f"Will stop after {args.duration:.1f}s.")

    counts: Counter[str] = Counter()
    cc_counts: Counter[tuple[int, int]] = Counter()
    nrpn_trackers: dict[int, NrpnTracker] = {}
    start = time.monotonic()

    try:
        with mido.open_input(port_name) as inport:
            while True:
                now = time.monotonic()
                if deadline is not None and now >= deadline:
                    break

                any_seen = False
                for msg in inport.iter_pending():
                    any_seen = True

                    if channel_filter is not None and hasattr(msg, "channel"):
                        if int(msg.channel) != channel_filter:
                            continue

                    rel = now - start
                    print(
                        _format_message_line(
                            msg,
                            rel_seconds=rel,
                            show_raw=bool(args.show_raw),
                            nrpn_trackers=nrpn_trackers,
                        )
                    )

                    counts[msg.type] += 1
                    if msg.type == "control_change":
                        cc_counts[(int(msg.channel), int(msg.control))] += 1

                if not any_seen:
                    time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        print(f"Failed while reading MIDI input: {exc}")
        return 1

    total = sum(counts.values())
    print("\nSummary")
    print(f"- Total messages: {total}")
    if not counts:
        print("- No messages received.")
        print(
            "- If Syntakt knob moves produce no input, the device may not echo parameter changes."
        )
        print("- Also verify MIDI routing/ports and the device's MIDI OUT settings.")
        return 0

    for msg_type, count in counts.most_common():
        print(f"- {msg_type}: {count}")

    if cc_counts:
        print("- Top CC activity:")
        for (channel, control), count in cc_counts.most_common(10):
            print(f"  ch={channel + 1} cc={control}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
