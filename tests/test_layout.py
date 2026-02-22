from __future__ import annotations

from syntakt_controller.controller_models import app_layout_definition


def test_layout_has_three_tabs() -> None:
    tabs = app_layout_definition()
    assert [tab.name for tab in tabs] == ["Track", "Global FX", "FX Track"]


def test_layout_has_expected_parameter_volume() -> None:
    tabs = app_layout_definition()
    total_params = sum(len(group.parameters) for tab in tabs for group in tab.groups)
    # UI prototype intentionally covers all major groups while keeping v1 practical.
    assert total_params >= 70
