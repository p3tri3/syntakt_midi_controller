from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def qt_app():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover
        pytest.skip("PyQt6 not installed")

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
