from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from syntakt_controller.controller_models import (
    Parameter,
    ParameterGroup,
    TabDefinition,
    app_layout_definition,
)
from syntakt_controller.controllers.main_controller import MainController


class MainWindow(QMainWindow):
    def __init__(self, controller: MainController) -> None:
        super().__init__()
        self._controller = controller
        self._controller.set_status_listener(self._on_controller_status)

        self.setWindowTitle("Syntakt MIDI Controller (UI Prototype)")
        self.resize(1280, 880)

        self._port_combo = QComboBox()  # configured in _build_connection_bar
        self._tabs = QTabWidget()
        self._build_tabs(app_layout_definition())

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._build_connection_bar())
        vbox.addWidget(self._tabs)
        self.setCentralWidget(container)

        if sb := self.statusBar():
            sb.showMessage("Ready")

    def _build_connection_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 4, 6, 4)

        layout.addWidget(QLabel("Output Port:"))
        self._port_combo.setObjectName("Track/Session/Output Port")
        self._port_combo.setMinimumWidth(220)
        self._port_combo.currentTextChanged.connect(
            lambda text: self._controller.on_parameter_changed("Track/Session/Output Port", text)
        )
        self._populate_port_combo()
        layout.addWidget(self._port_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setToolTip("Rescan available MIDI output ports")
        refresh_btn.clicked.connect(self._refresh_ports)
        layout.addWidget(refresh_btn)

        layout.addWidget(QLabel("Track Channel:"))
        channel_combo = QComboBox()
        channel_combo.setObjectName("Track/Session/Track Channel")
        channel_combo.addItems([str(i) for i in range(1, 17)])
        channel_combo.currentIndexChanged.connect(
            lambda idx: self._controller.on_parameter_changed(
                "Track/Session/Track Channel", idx + 1
            )
        )
        layout.addWidget(channel_combo)

        ping_btn = QPushButton("Send Test Ping")
        ping_btn.clicked.connect(self._controller.send_test_ping)
        layout.addWidget(ping_btn)

        layout.addStretch(1)
        return bar

    def _populate_port_combo(self) -> None:
        """Populate the output port combo and auto-select the best port.

        On initial call the combo is empty, so ``current_text`` is ``""``.
        The preferred default port is selected and opened when available.

        On subsequent calls (Refresh) the current selection is preserved if it
        is still in the new list; otherwise the preferred default is tried next.
        A port open call is only made when the effective selection changes.
        """
        ports = self._controller.available_ports()
        current_text = self._port_combo.currentText()  # "" on the first call

        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItems(ports if ports else ["No Device (Development)"])

        # Prefer current selection (Refresh); fall back to the preferred default.
        target: str | None = None
        if current_text and self._port_combo.findText(current_text) >= 0:
            target = current_text
        else:
            preferred = self._controller.preferred_output_port()
            if preferred is not None and self._port_combo.findText(preferred) >= 0:
                target = preferred

        if target is not None:
            self._port_combo.setCurrentText(target)

        self._port_combo.blockSignals(False)

        # Open the port when the selection changed (includes the initial auto-select).
        new_text = self._port_combo.currentText()
        if target is not None and new_text != current_text:
            self._controller.on_parameter_changed("Track/Session/Output Port", new_text)

    def _refresh_ports(self) -> None:
        """Rescan available MIDI output ports and repopulate the selector."""
        self._populate_port_combo()

    def _build_tabs(self, definitions: tuple[TabDefinition, ...]) -> None:
        for tab_def in definitions:
            page = QWidget()
            page_layout = QVBoxLayout(page)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content_layout = QVBoxLayout(content)

            for group in tab_def.groups:
                content_layout.addWidget(self._build_group_widget(tab_def.name, group))

            content_layout.addStretch(1)
            scroll.setWidget(content)
            page_layout.addWidget(scroll)

            self._tabs.addTab(page, tab_def.name)

    def _build_group_widget(self, tab_name: str, group: ParameterGroup) -> QWidget:
        box = QGroupBox(group.name)

        if group.columns > 1:
            box_layout = QGridLayout(box)
            cols = group.columns
            for i, param in enumerate(group.parameters):
                key = f"{tab_name}/{group.name}/{param.name}"
                widget = self._make_parameter_widget(key, param)
                row = i // cols
                col_pair = i % cols
                label = QLabel(param.name)
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                box_layout.addWidget(label, row, col_pair * 2)
                box_layout.addWidget(widget, row, col_pair * 2 + 1)
            for c in range(cols):
                box_layout.setColumnStretch(c * 2, 0)  # label: no stretch
                box_layout.setColumnStretch(c * 2 + 1, 1)  # widget: expand
        else:
            box_layout = QFormLayout(box)
            for param in group.parameters:
                key = f"{tab_name}/{group.name}/{param.name}"
                widget = self._make_parameter_widget(key, param)
                box_layout.addRow(param.name, widget)

        return box

    def _make_parameter_widget(self, key: str, param: Parameter) -> QWidget:
        if param.control_type == "toggle":
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(
                lambda state, k=key: self._controller.on_parameter_changed(
                    k, state == Qt.CheckState.Checked.value
                )
            )
            return checkbox

        if param.control_type == "combo":
            combo = QComboBox()
            combo.setObjectName(key)
            combo.addItems(self._combo_options_for(key, param))
            if key == "Track/Session/Output Port":
                # Port selection requires the actual port name string.
                combo.currentTextChanged.connect(
                    lambda text, k=key: self._controller.on_parameter_changed(k, text)
                )
            else:
                # All other combos send the selection index offset by min_value so that
                # both named options (min_value=0 → raw index) and numeric ranges
                # (e.g. Track Channel min_value=1 → index+1) map correctly to MIDI.
                combo.currentIndexChanged.connect(
                    lambda idx, k=key, offset=param.min_value: (
                        self._controller.on_parameter_changed(k, idx + offset)
                    )
                )
            return combo

        slider_container = QWidget()
        layout = QHBoxLayout(slider_container)
        layout.setContentsMargins(0, 0, 0, 0)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(param.min_value, param.max_value)
        slider.setValue(param.min_value)

        value_label = QLabel(str(param.min_value))
        value_label.setMinimumWidth(32)

        def on_change(value: int, *, k: str = key) -> None:
            value_label.setText(str(value))
            self._controller.on_parameter_changed(k, value)

        slider.valueChanged.connect(on_change)

        layout.addWidget(slider)
        layout.addWidget(value_label)
        return slider_container

    def _combo_options_for(self, key: str, param: Parameter) -> list[str]:
        if param.options:
            return list(param.options)

        return [str(option) for option in range(param.min_value, param.max_value + 1)]

    def _on_controller_status(self, message: str, is_error: bool) -> None:
        color = "#b00020" if is_error else "#1f6f43"
        if sb := self.statusBar():
            sb.setStyleSheet(f"color: {color};")
            sb.showMessage(message)
