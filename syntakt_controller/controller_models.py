from __future__ import annotations

from dataclasses import dataclass, field

ParameterValue = int | bool | str

# Default MIDI output port name.  Selected automatically on startup when available.
DEFAULT_OUTPUT_PORT: str = "UFX II Midi Port 2 2"

# Named option tuples for combo parameters, sourced from the Syntakt MIDI spec.
_FILTER_TYPES: tuple[str, ...] = ("LP2", "LP1", "BP", "HP1", "HP2", "BS", "PK")
_LFO_WAVEFORMS: tuple[str, ...] = ("TRI", "SIN", "SQR", "SAW", "EXP", "RMP", "RND")
_LFO_TRIG_MODES: tuple[str, ...] = ("FREE", "TRG", "HLD", "ONE", "HLF")
_LFO_MULTIPLIERS: tuple[str, ...] = (
    "1",
    "2",
    "4",
    "8",
    "16",
    "32",
    "64",
    "128",
    "256",
    "512",
    "1K",
    "2K",
)
_AMP_MODES: tuple[str, ...] = ("GAT", "INF")
_FX_ROUTINGS: tuple[str, ...] = ("PRE", "POST")


@dataclass(frozen=True)
class Parameter:
    name: str
    control_type: str  # slider | toggle | combo
    min_value: int = 0
    max_value: int = 127
    options: tuple[str, ...] = ()  # non-empty only for named combo parameters


@dataclass(frozen=True)
class ParameterGroup:
    name: str
    parameters: tuple[Parameter, ...] = field(default_factory=tuple)
    columns: int = 1  # Number of label+widget column pairs in the UI grid


@dataclass(frozen=True)
class TabDefinition:
    name: str
    groups: tuple[ParameterGroup, ...] = field(default_factory=tuple)


@dataclass
class AppState:
    selected_track_channel: int = 14  # Default is 14: Syntakt factory auto-channel.
    selected_output_port: str | None = None
    current_values: dict[str, ParameterValue] = field(default_factory=dict)
    last_status: str | None = None
    last_error: str | None = None
    use_nrpn: bool = False  # When True, prefer NRPN over CC for mapped parameters

    @property
    def selected_midi_channel(self) -> int:
        return self.selected_track_channel - 1


def app_layout_definition() -> tuple[TabDefinition, ...]:
    """Static v1 layout."""
    return (
        TabDefinition(
            name="Track",
            groups=(
                ParameterGroup(
                    name="Session",
                    parameters=(
                        # Placeholder UI control for future Program Change support.
                        Parameter("Program", "slider", 0, 127),
                    ),
                ),
                ParameterGroup(
                    name="Trig",
                    parameters=(
                        Parameter("Note", "slider", 0, 127),
                        Parameter("Velocity", "slider", 0, 127),
                        Parameter("Length", "slider", 0, 127),
                        Parameter("Filter Trig", "toggle"),
                        Parameter("LFO Trig", "toggle"),
                    ),
                ),
                ParameterGroup(
                    name="SYN (A-H)",
                    parameters=tuple(
                        Parameter(f"Data Entry {ch}", "slider", 0, 127) for ch in "ABCDEFGH"
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="Filter",
                    parameters=(
                        Parameter("Filter Frequency", "slider"),
                        Parameter("Resonance", "slider"),
                        Parameter("Filter Type", "combo", options=_FILTER_TYPES),
                        Parameter("Attack", "slider"),
                        Parameter("Decay", "slider"),
                        Parameter("Sustain", "slider"),
                        Parameter("Release", "slider"),
                        Parameter("Env Depth", "slider"),
                        Parameter("Env Delay", "slider"),
                        Parameter("Base", "slider"),
                        Parameter("Width", "slider"),
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="Amp",
                    parameters=(
                        Parameter("Attack", "slider"),
                        Parameter("Hold", "slider"),
                        Parameter("Decay", "slider"),
                        Parameter("Sustain", "slider"),
                        Parameter("Release", "slider"),
                        Parameter("Delay Send", "slider"),
                        Parameter("Reverb Send", "slider"),
                        Parameter("Pan", "slider"),
                        Parameter("Volume", "slider"),
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="LFO 1",
                    parameters=(
                        Parameter("Speed", "slider"),
                        Parameter("Multiplier", "combo", options=_LFO_MULTIPLIERS),
                        Parameter("Fade In/Out", "slider"),
                        Parameter("Destination", "combo"),
                        Parameter("Waveform", "combo", options=_LFO_WAVEFORMS),
                        Parameter("Start Phase", "slider"),
                        Parameter("Trig Mode", "combo", options=_LFO_TRIG_MODES),
                        Parameter("Depth", "slider"),
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="LFO 2",
                    parameters=(
                        Parameter("Speed", "slider"),
                        Parameter("Multiplier", "combo", options=_LFO_MULTIPLIERS),
                        Parameter("Fade In/Out", "slider"),
                        Parameter("Destination", "combo"),
                        Parameter("Waveform", "combo", options=_LFO_WAVEFORMS),
                        Parameter("Start Phase", "slider"),
                        Parameter("Trig Mode", "combo", options=_LFO_TRIG_MODES),
                        Parameter("Depth", "slider"),
                    ),
                    columns=2,
                ),
            ),
        ),
        TabDefinition(
            name="Global FX",
            groups=(
                ParameterGroup(
                    name="Delay",
                    parameters=(
                        Parameter("Delay Time", "slider"),
                        Parameter("Pingpong", "toggle"),
                        Parameter("Stereo Width", "slider"),
                        Parameter("Feedback", "slider"),
                        Parameter("Highpass", "slider"),
                        Parameter("Lowpass", "slider"),
                        Parameter("Reverb Send", "slider"),
                        Parameter("Mix", "slider"),
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="Reverb",
                    parameters=(
                        Parameter("Predelay", "slider"),
                        Parameter("Decay", "slider"),
                        Parameter("Shelving Freq", "slider"),
                        Parameter("Shelving Gain", "slider"),
                        Parameter("Highpass", "slider"),
                        Parameter("Lowpass", "slider"),
                        Parameter("Mix", "slider"),
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="External In",
                    parameters=(
                        Parameter("Input LR", "slider"),
                        Parameter("Balance", "slider"),
                        Parameter("Delay Send", "slider"),
                        Parameter("Reverb Send", "slider"),
                        Parameter("FX Routing", "combo", options=_FX_ROUTINGS),
                    ),
                ),
                ParameterGroup(
                    name="Misc",
                    parameters=(
                        Parameter("Pattern Mute", "toggle"),
                        Parameter("VAL1", "slider"),
                        Parameter("VAL2", "slider"),
                        Parameter("VAL3", "slider"),
                        Parameter("VAL4", "slider"),
                        Parameter("VAL5", "slider"),
                        Parameter("VAL6", "slider"),
                        Parameter("VAL7", "slider"),
                        Parameter("VAL8", "slider"),
                    ),
                    columns=2,
                ),
            ),
        ),
        TabDefinition(
            name="FX Track",
            groups=(
                ParameterGroup(name="SYN", parameters=(Parameter("Drive", "slider"),)),
                ParameterGroup(
                    name="Filter",
                    parameters=(
                        Parameter("Filter Frequency", "slider"),
                        Parameter("Resonance", "slider"),
                        Parameter("Filter Type", "combo", options=_FILTER_TYPES),
                        Parameter("Attack", "slider"),
                        Parameter("Decay", "slider"),
                        Parameter("Sustain", "slider"),
                        Parameter("Release", "slider"),
                        Parameter("Env Depth", "slider"),
                        Parameter("Env Delay", "slider"),
                    ),
                    columns=2,
                ),
                ParameterGroup(
                    name="Amp",
                    parameters=(
                        Parameter("Attack", "slider"),
                        Parameter("Hold", "slider"),
                        Parameter("Decay", "slider"),
                        Parameter("Sustain", "slider"),
                        Parameter("Release", "slider"),
                        Parameter("Delay Send", "slider"),
                        Parameter("Reverb Send", "slider"),
                        Parameter("Pan", "slider"),
                        Parameter("Volume", "slider"),
                        Parameter("Env Depth", "slider"),
                        Parameter("Mode", "combo", options=_AMP_MODES),
                        Parameter("Env Reset", "toggle"),
                    ),
                    columns=2,
                ),
            ),
        ),
    )
