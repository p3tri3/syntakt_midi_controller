from __future__ import annotations

from pathlib import Path

import pytest

from syntakt_controller.services.parameter_mapping import load_parameter_mapping_index


def test_parameter_mapping_loads_all_spec_rows() -> None:
    index = load_parameter_mapping_index()

    spec_keys = {
        mapping.parameter_key
        for key, mapping in index.by_spec_key.items()
        if key == mapping.parameter_key
    }
    assert len(spec_keys) == 102


def test_parameter_mapping_resolves_ui_key() -> None:
    index = load_parameter_mapping_index()

    mapping = index.get("Track/Trig/Velocity")
    assert mapping is not None
    assert mapping.cc_msb == 4
    assert mapping.nrpn_msb == 3
    assert mapping.nrpn_lsb == 1


def test_parameter_mapping_resolves_ui_aliases_and_high_res_cc() -> None:
    index = load_parameter_mapping_index()

    mapping = index.get("Track/SYN (A-H)/Data Entry A")
    assert mapping is not None
    assert mapping.cc_msb == 17
    assert mapping.nrpn_lsb == 1

    high_res = index.get("Track/LFO 1/Depth")
    assert high_res is not None
    assert high_res.cc_msb == 109
    assert high_res.cc_lsb == 61
    assert high_res.has_high_resolution_cc is True


def test_parameter_mapping_resolves_spec_key_and_unknown_key() -> None:
    index = load_parameter_mapping_index()

    spec_key = "B.7 FX PARAMETERS/REVERB/Highpass Filter"
    mapping = index.get(spec_key)
    assert mapping is not None
    assert mapping.cc_msb == 90
    assert mapping.parameter_key == spec_key

    assert index.get("Track/Session/Output Port") is None


def test_parameter_mapping_resolves_env_reset_alias() -> None:
    index = load_parameter_mapping_index()

    mapping = index.get("FX Track/Amp/Env Reset")
    assert mapping is not None
    assert mapping.cc_msb == 88
    assert mapping.nrpn_msb == 1
    assert mapping.nrpn_lsb == 36


def test_parameter_mapping_uses_corrected_track_amp_nrpn_lsb_values() -> None:
    index = load_parameter_mapping_index()

    sustain = index.get("Track/Amp/Sustain")
    release = index.get("Track/Amp/Release")
    delay_send = index.get("Track/Amp/Delay Send")
    reverb_send = index.get("Track/Amp/Reverb Send")
    pan = index.get("Track/Amp/Pan")
    volume = index.get("Track/Amp/Volume")

    assert sustain is not None and sustain.nrpn_lsb == 27
    assert release is not None and release.nrpn_lsb == 28
    assert delay_send is not None and delay_send.nrpn_lsb == 30
    assert reverb_send is not None and reverb_send.nrpn_lsb == 31
    assert pan is not None and pan.nrpn_lsb == 32
    assert volume is not None and volume.nrpn_lsb == 33


def test_parameter_mapping_duplicate_conflict_error_includes_csv_path(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "conflict.csv"
    csv_path.write_text(
        (
            "section,subsection,parameter,cc_msb,cc_lsb,nrpn_msb,nrpn_lsb,source,confidence,notes\n"
            "B.1 TRACK PARAMETERS,TRIG PARAMETERS,Env Depth,1,,,,spec,high,\n"
            "B.1 TRACK PARAMETERS,TRIG PARAMETERS,Env. Depth,2,,,,spec,high,\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_parameter_mapping_index(csv_path)

    message = str(exc_info.value)
    assert str(csv_path) in message
    assert "Duplicate mapping key with conflicting values" in message
