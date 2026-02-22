# Agent Collaboration Guide

This file defines project conventions for AI coding agents (Codex, Claude Code, Gemini/Jules).

## Project Goal
Build a Python Qt6 desktop application for controlling Elektron Syntakt over MIDI.

## Current Architecture
- Entry point: `syntakt_midi_controller.py`
- Package root: `syntakt_controller/`
- UI layer: `syntakt_controller/ui/`
- Controller layer: `syntakt_controller/controllers/`
- Service/integration layer: `syntakt_controller/services/`
- Tests: `tests/`
- Mapping module: `syntakt_controller/services/parameter_mapping.py`
- App state model: `syntakt_controller/controller_models.py::AppState`

UI and business logic must remain separated.
- UI widgets may emit semantic events only.
- Controller translates events to application actions.
- MIDI service is injected and replaceable.

## MIDI and Device-Safe Development
Default behavior must be safe without hardware.
- Use `NullMidiService` for local development, tests, and CI.
- Keep `MidoMidiService` optional and isolated from core UI tests.
- Never require a physical device for unit tests.
- Treat MIDI send/open failures as recoverable UI-visible errors, not crashes.

## Implementation Rules
- Prefer typed dataclasses for parameter definitions and app state.
- Keep parameter metadata in one place and avoid duplicated mappings.
- Do not embed direct MIDI calls inside Qt widgets.
- Keep functions small and testable.
- Keep parameter mapping authoritative in CSV + mapping loader, not duplicated ad-hoc in controller code.

## Testing Expectations
Before concluding major changes:
1. Run `pytest`.
2. Ensure tests pass in headless mode (`QT_QPA_PLATFORM=offscreen`).
3. Add/adjust tests for new controller logic and schema changes.
4. Cover both success and failure paths for MIDI operations when behavior changes.

## Quality and Tooling
- Dependencies and tooling are declared in `pyproject.toml`; `requirements.txt` is a redirect for `pip install -r` workflows.
- CI quality gates: `ruff`, `mypy`, `pytest --cov`.

## Suggested Next Milestones
1. Add preset save/load format and tests.
2. Optionally add device -> UI sync path with safe defaults.
3. Initialize git tracking and align workflow docs with repository conventions.
4. Expand release checklist (versioning/changelog/release automation) once repository is initialized.
