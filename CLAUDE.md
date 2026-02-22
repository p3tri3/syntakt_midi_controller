# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Desktop Qt6 application for controlling the Elektron Syntakt synthesizer via MIDI CC messages. Python 3.11+, PyQt6 UI with strict separation between UI, controllers, and services layers.

## Commands

```bash
# Run the app (MIDI on by default; falls back to NullMidiService if mido not installed)
python syntakt_midi_controller.py
python syntakt_midi_controller.py --no-midi    # disable MIDI (no hardware required)
python syntakt_midi_controller.py --verbose

# Run tests (requires QT_QPA_PLATFORM=offscreen for headless/CI)
QT_QPA_PLATFORM=offscreen pytest

# Run a single test
QT_QPA_PLATFORM=offscreen pytest tests/test_controller.py::test_name

# Lint
ruff check .

# Format
ruff format .

# Type check
mypy syntakt_controller/

# Makefile shortcuts
make test
make lint
make typecheck
make run

# Install dependencies
pip install -e ".[dev]"         # app + dev tools
pip install -e ".[dev,midi]"    # add runtime MIDI support
pip install -r requirements.txt # equivalent redirect to .[dev,midi]
```

## Architecture

```
syntakt_midi_controller.py  →  syntakt_controller/app.py::main()
                                    ↓
                               MainWindow (UI)
                                    │ on_parameter_changed()
                                    ↓
                               MainController
                                ↙          ↘
                  ParameterMappingIndex    MidiService (injected)
                  (loaded from CSV)        ├─ NullMidiService (default)
                                           └─ MidoMidiService (optional)
```

- **UI layer** (`syntakt_controller/ui/`): Qt6 widgets that emit semantic events only — no direct MIDI calls
- **Controller** (`syntakt_controller/controllers/main_controller.py`): Routes UI events to MIDI sends, manages AppState, handles errors as recoverable UI-visible status
- **Services** (`syntakt_controller/services/`): `MidiService` protocol with dependency injection; `ParameterMappingIndex` maps UI keys to MIDI CC/NRPN from CSV
- **Models** (`syntakt_controller/controller_models.py`): Typed dataclasses for `Parameter`, `ParameterGroup`, `TabDefinition`, `AppState`; `app_layout_definition()` defines the 3-tab UI layout

## Key Design Constraints

- UI and business logic must stay strictly separated
- `NullMidiService` is the safe default — no physical device required for development or tests
- Parameter metadata lives in `specs/syntakt_midi_parameters.csv` (single source of truth, 102 parameters)
- Controller supports both 7-bit CC (0-127) and 14-bit CC (0-16383, via cc_msb/cc_lsb pairs)
- MIDI errors are recoverable and propagated to the UI status bar, never fatal
- NRPN send path is opt-in: set `AppState.use_nrpn = True`; CC is always the default
- `_send_nrpn` sends all four MIDI CCs (99/MSB, 98/LSB, 6/value, 38/0) unconditionally even on partial failure, to avoid leaving partial NRPN state on the device; it returns `all(results)`
- `MidiService` Protocol requires all three methods: `list_output_ports`, `open_output`, `send_control_change`

## Parameter Mapping Gotchas

- When a CSV parameter name differs from its UI label, add the alias to `_PARAMETER_TO_UI_NAME` in `parameter_mapping.py`. Missing entries cause silent MIDI no-ops with no error — the mapping returns `None` and the controller skips the send.
- `MainController.__post_init__` runs `_validate_layout_mappings` on every construction — check for `WARNING`-level log output after any layout or parameter rename.
- UI key format is `"{Tab}/{Group}/{Parameter}"` — must match exactly what `app_layout_definition()` produces. The `_SUBSECTION_TO_GROUP` table in `parameter_mapping.py` controls group name translation from CSV subsection names.
- Combo widgets: named combos use `currentIndexChanged` + `param.min_value` offset so the integer index is sent to the controller. `Track/Session/Output Port` is the only exception — it uses `currentTextChanged` because the controller needs the port name string.
- 14-bit CC tests must cover mid-range values (1–127), not just 0 and 16383. The MSB/LSB split (`value >> 7`, `value & 0x7F`) is unconditional — a conditional on `> 127` will silently mis-encode the lower range.
- NRPN LSB data quality: `Attack Time`, `Sustain Level`, `Release Time` (AMP section), and `Filter/Base` all share `nrpn_lsb=24` in the CSV. Verify these addresses against the physical Syntakt MIDI implementation chart before enabling `use_nrpn=True` in production.

## Testing

- pytest with 80% coverage minimum enforced (`--cov-fail-under=80`)
- Tests must pass headless (`QT_QPA_PLATFORM=offscreen`)
- Never require a physical MIDI device — use `NullMidiService` in tests
- Session-scoped QApplication fixture in `tests/conftest.py`

## CI

GitHub Actions runs on Python 3.11, 3.12, 3.13 with workflows for tests, coverage (codecov), CodeQL security scanning, and pre-commit validation. Pre-commit hooks: file hygiene, ruff lint+format, mypy strict.

CI runners require system packages before pip install: `libasound2-dev libjack-jackd2-dev` (to compile `python-rtmidi` from source on Python 3.13, which has no pre-built wheel) and `libegl1` (required by PyQt6 at import time on headless Ubuntu).

## mypy and PyQt6/mido

`PyQt6` and `mido` are configured with `follow_imports = "skip"` and `ignore_missing_imports = true` in `pyproject.toml`. This tells mypy to treat all symbols from these packages as `Any` regardless of whether stubs are bundled (PyQt6 ≥6.10 ships inline stubs). Without this, mypy behaviour diverges across PyQt6 versions — older versions report `import-untyped`, newer ones expose real Qt type errors. The trade-off is that mypy does not type-check Qt widget code. Do not remove these overrides without also fixing all resulting Qt type errors in `main_window.py` and `app.py`.
