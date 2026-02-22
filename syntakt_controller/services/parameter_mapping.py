from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAPPING_CSV = Path(__file__).resolve().parents[2] / "specs" / "syntakt_midi_parameters.csv"

_TRACK_SECTIONS_TO_TAB = {
    "B.1 TRACK PARAMETERS": "Track",
    "B.2 TRIG PARAMETERS": "Track",
    "B.3 SYN PARAMETERS": "Track",
    "B.4 FILTER PARAMETERS": "Track",
    "B.5 AMP PARAMETERS": "Track",
    "B.6 LFO PARAMETERS": "Track",
    "B.7 FX PARAMETERS": "Global FX",
    "B.8 VAL PARAMETERS": "Global FX",
    "B.9 MISC PARAMETERS": "Global FX",
    "B.10 FX TRACK PARAMETERS": "FX Track",
}

_SUBSECTION_TO_GROUP = {
    "TRIG PARAMETERS": "Trig",
    "SOURCE": "SYN (A-H)",
    "FILTER": "Filter",
    "AMP": "Amp",
    "LFO 1": "LFO 1",
    "LFO 2": "LFO 2",
    "DELAY": "Delay",
    "REVERB": "Reverb",
    "EXTERNAL IN MIXER": "External In",
    "CC VAL": "Misc",
    "MISC": "Misc",
    "SYN": "SYN",
}

_PARAMETER_TO_UI_NAME = {
    "Data entry knob A": "Data Entry A",
    "Data entry knob B": "Data Entry B",
    "Data entry knob C": "Data Entry C",
    "Data entry knob D": "Data Entry D",
    "Data entry knob E": "Data Entry E",
    "Data entry knob F": "Data Entry F",
    "Data entry knob G": "Data Entry G",
    "Data entry knob H": "Data Entry H",
    "Attack Time": "Attack",
    "Hold Time": "Hold",
    "Decay Time": "Decay",
    "Sustain Level": "Sustain",
    "Release Time": "Release",
    "Env. Depth": "Env Depth",
    "Env. Delay": "Env Delay",
    "Env. Reset": "Env Reset",
    "Highpass Filter": "Highpass",
    "Lowpass Filter": "Lowpass",
    "Mix Volume": "Mix",
    "Input Balance": "Balance",
    "Input Delay Send": "Delay Send",
    "Input Reverb Send": "Reverb Send",
    "Input FX Routing": "FX Routing",
}


@dataclass(frozen=True)
class MidiParameterMapping:
    parameter_key: str
    section: str
    subsection: str
    parameter: str
    cc_msb: int | None
    cc_lsb: int | None
    nrpn_msb: int | None
    nrpn_lsb: int | None
    source: str
    confidence: str
    notes: str

    @property
    def has_high_resolution_cc(self) -> bool:
        return self.cc_lsb is not None


@dataclass(frozen=True)
class ParameterMappingIndex:
    by_spec_key: dict[str, MidiParameterMapping]
    by_ui_key: dict[str, MidiParameterMapping]

    def get(self, key: str) -> MidiParameterMapping | None:
        mapping = self.by_ui_key.get(key) or self.by_spec_key.get(key)
        if mapping is not None:
            return mapping

        normalized = _normalize_key(key)
        return self.by_ui_key.get(normalized) or self.by_spec_key.get(normalized)


def load_parameter_mapping_index(
    csv_path: str | Path = DEFAULT_MAPPING_CSV,
) -> ParameterMappingIndex:
    csv_path = Path(csv_path)
    spec_map: dict[str, MidiParameterMapping] = {}
    ui_map: dict[str, MidiParameterMapping] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            section = row["section"].strip()
            subsection = row["subsection"].strip()
            parameter = row["parameter"].strip()
            spec_key = f"{section}/{subsection}/{parameter}"
            mapping = MidiParameterMapping(
                parameter_key=spec_key,
                section=section,
                subsection=subsection,
                parameter=parameter,
                cc_msb=_parse_optional_int(row["cc_msb"]),
                cc_lsb=_parse_optional_int(row["cc_lsb"]),
                nrpn_msb=_parse_optional_int(row["nrpn_msb"]),
                nrpn_lsb=_parse_optional_int(row["nrpn_lsb"]),
                source=row["source"].strip(),
                confidence=row["confidence"].strip(),
                notes=row["notes"].strip(),
            )
            _insert_key(spec_map, spec_key, mapping, csv_path)
            _insert_key(spec_map, _normalize_key(spec_key), mapping, csv_path)

            ui_key = _to_ui_key(mapping)
            if ui_key is not None:
                _insert_key(ui_map, ui_key, mapping, csv_path)
                _insert_key(ui_map, _normalize_key(ui_key), mapping, csv_path)

    return ParameterMappingIndex(by_spec_key=spec_map, by_ui_key=ui_map)


def _to_ui_key(mapping: MidiParameterMapping) -> str | None:
    tab_name = _TRACK_SECTIONS_TO_TAB.get(mapping.section)
    group_name = _SUBSECTION_TO_GROUP.get(mapping.subsection)
    parameter_name = _PARAMETER_TO_UI_NAME.get(mapping.parameter, mapping.parameter)

    if tab_name is None or group_name is None:
        return None

    # Session controls are not represented in the current v1 CSV rows.
    if mapping.subsection == "TRACK":
        return None

    if (
        mapping.section == "B.8 VAL PARAMETERS"
        and mapping.subsection == "CC VAL"
        and not parameter_name.startswith("VAL")
    ):
        return None

    return f"{tab_name}/{group_name}/{parameter_name}"


def _parse_optional_int(value: str) -> int | None:
    cleaned = value.strip()
    return int(cleaned) if cleaned else None


def _normalize_key(key: str) -> str:
    parts = [part.strip().lower() for part in key.split("/")]
    normalized_parts = [_normalize_part(part) for part in parts]
    return "/".join(normalized_parts)


def _normalize_part(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", compact)


def _insert_key(
    destination: dict[str, MidiParameterMapping],
    key: str,
    mapping: MidiParameterMapping,
    csv_path: Path,
) -> None:
    existing = destination.get(key)
    if existing is None:
        destination[key] = mapping
        return
    if existing.parameter_key == mapping.parameter_key:
        return
    raise ValueError(
        f"In {csv_path}: Duplicate mapping key with conflicting values: "
        f"{key} ({existing.parameter_key} vs {mapping.parameter_key})"
    )
