.PHONY: test lint typecheck run

PYTHON ?= python

test:
	QT_QPA_PLATFORM=offscreen pytest

lint:
	ruff check .

typecheck:
	mypy syntakt_controller/

run:
	$(PYTHON) syntakt_midi_controller.py
