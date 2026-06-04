"""
Sidebar Widget
Refined dark theme file selection and configuration controls with collapse support.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QComboBox, QSlider, QGroupBox, QFileDialog,
    QFormLayout, QFrame, QSizePolicy, QCheckBox, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont


# Refined Dark Style
# Refined Dark Style - Professional Tool Panel
REFINED_STYLE = """
QWidget {
    background-color: #252526;
    color: #cccccc;
    font-size: 11px;
    font-family: 'Segoe UI', sans-serif;
}
/* Section Headers */
QGroupBox {
    background-color: #252526;
    border: none;
    border-top: 1px solid #3e3e42;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    text-transform: uppercase;
    color: #aaaaaa;
    font-size: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px;
    padding: 0 4px;
}
/* Form Controls */
QLineEdit, QSpinBox, QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c; /* Flat look */
    border-radius: 2px;
    padding: 4px;
    color: #cccccc;
    min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #007acc;
    background-color: #3f3f46;
}
/* Buttons */
QPushButton {
    background-color: #0e639c;
    border: none;
    border-radius: 2px;
    padding: 5px 12px;
    color: white;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:pressed {
    background-color: #005a9e;
}
/* Tool Buttons (Browse, etc) */
QPushButton#toolBtn {
    background-color: #3c3c3c;
    border: 1px solid #3e3e42;
    padding: 4px;
    min-width: 24px;
}
QPushButton#toolBtn:hover {
    background-color: #505050;
}
/* Segmented Control Buttons (Component Selector) */
QPushButton#compBtn {
    background-color: #3c3c3c;
    border: 1px solid #3e3e42;
    border-radius: 0px;
    margin: 0px;
    padding: 6px 10px;
    font-weight: bold;
}
QPushButton#compBtn:checked {
    background-color: #0e639c; /* Blue active state */
    border: 1px solid #007acc;
    color: white;
}
QPushButton#compBtn:hover:!checked {
    background-color: #454545;
}
/* Playback Controls */
QPushButton#playBtn {
    background-color: transparent;
    border: 1px solid transparent;
    font-size: 14px;
    border-radius: 4px;
}
QPushButton#playBtn:hover {
    background-color: #3e3e42;
}
QPushButton#playBtn:checked {
    color: #007acc; /* Active accent color */
}
/* Scrollbars (VSCode Style) */
QScrollBar:vertical {
    background: #252526;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #424242;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #4f4f4f;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: #252526;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #424242;
    min-width: 20px;
    border-radius: 5px;
}
"""


class Sidebar(QWidget):
    """Refined sidebar with file selection and configuration controls."""

    # Signals
    files_changed = pyqtSignal()
    config_changed = pyqtSignal()
    frame_changed = pyqtSignal(int)
    collapse_toggled = pyqtSignal(bool)  # True = collapsed
    overlay_toggled = pyqtSignal(bool)  # True = show overlay
    overlay_opacity_changed = pyqtSignal(int)  # 0-100
    diff_view_toggled = pyqtSignal(bool)  # True = show diff view
    diff_mode_changed = pyqtSignal(str)  # s1_ref, s2_ref, s1_s2
    hex_mode_toggled = pyqtSignal(bool)  # True = hex mode
    grid_toggled = pyqtSignal(bool)  # True = show grid (without PSNR)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._expanded_width = 280
        self.setMinimumWidth(32)
        self.setMaximumWidth(self._expanded_width)
        self.setStyleSheet(REFINED_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Sidebar Header / Collapse ---
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: #333333; border-bottom: 1px solid #3e3e42;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 6, 8, 6)
        
        title_label = QLabel("CONFIGURATION")
        title_label.setStyleSheet("font-weight: bold; color: #aaaaaa; font-size: 10px; letter-spacing: 1px;")
        
        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setObjectName("collapseBtn")
        self.collapse_btn.setFixedWidth(20)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.collapse_btn)
        
        self.main_layout.addWidget(header_widget)

        # --- Scrollable Content Area ---
        from PyQt6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)

        # 1. SOURCE MEDIA
        source_group = QGroupBox("SOURCE MEDIA")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(8)
        
        # Files
        self.ref_path = self._create_file_input("Ref YUV...", source_layout)
        ref_browse = self._add_browse_btn(self.ref_path, "YUV Files (*.yuv);;All Files (*)")

        self.stream1_path = self._create_file_input("Stream 1...", source_layout)
        s1_browse = self._add_browse_btn(self.stream1_path, "Video Files (*.264 *.265 *.h264 *.h265 *.hevc *.mp4 *.yuv);;All Files (*)")

        self.stream2_path = self._create_file_input("Stream 2...", source_layout)
        s2_browse = self._add_browse_btn(self.stream2_path, "Video Files (*.264 *.265 *.h264 *.h265 *.hevc *.mp4 *.yuv);;All Files (*)")
        
        # Res & Load
        res_row = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 8192)
        self.width_spin.setValue(1920)
        self.width_spin.setPrefix("W: ")
        
        self.height_spin = QSpinBox()
        self.height_spin.setRange(16, 8192)
        self.height_spin.setValue(1080)
        self.height_spin.setPrefix("H: ")
        
        res_row.addWidget(self.width_spin)
        res_row.addWidget(self.height_spin)
        source_layout.addLayout(res_row)
        
        self.load_btn = QPushButton("LOAD & COMPARE")
        self.load_btn.setFixedHeight(26)
        self.load_btn.setStyleSheet("font-weight: bold; font-size: 10px;")
        self.load_btn.clicked.connect(self.files_changed.emit)
        source_layout.addWidget(self.load_btn)
        
        content_layout.addWidget(source_group)

        # 2. ANALYSIS TOOLS
        analysis_group = QGroupBox("ANALYSIS TOOLS")
        analysis_layout = QFormLayout(analysis_group)
        analysis_layout.setSpacing(8)
        analysis_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["420", "422", "444"])
        analysis_layout.addRow("Format:", self.format_combo)
        
        # Component Selector (Segmented Control)
        self.comp_btn_group = QButtonGroup(self)
        self.comp_btn_group.setExclusive(True)
        comp_container = QWidget()
        comp_layout = QHBoxLayout(comp_container)
        comp_layout.setContentsMargins(0, 0, 0, 0)
        comp_layout.setSpacing(1)
        
        for idx, label in enumerate(["YUV", "Y", "U", "V"]):
            btn = QPushButton(label)
            btn.setObjectName("compBtn")
            btn.setCheckable(True)
            if idx == 0: btn.setChecked(True)
            self.comp_btn_group.addButton(btn, idx)
            comp_layout.addWidget(btn)
            
            # Map buttons to attributes for reference if needed
            if label == "YUV": self.comp_yuv_btn = btn
            elif label == "Y": self.comp_y_btn = btn
            elif label == "U": self.comp_u_btn = btn
            elif label == "V": self.comp_v_btn = btn

        self.comp_btn_group.buttonClicked.connect(lambda: self.config_changed.emit())
        analysis_layout.addRow("Component:", comp_container)
        
        # Block Size
        self.block_size_combo = QComboBox()
        self.block_size_combo.addItems(["64", "32", "16", "8"])
        self.block_size_combo.setCurrentText("64")
        self.block_size_combo.currentTextChanged.connect(lambda: self.config_changed.emit())
        analysis_layout.addRow("Block Size:", self.block_size_combo)
        
        # Pixel Format (Hex/Dec)
        pixel_row = QHBoxLayout()
        self.dec_radio = QPushButton("Dec")
        self.dec_radio.setCheckable(True)
        self.dec_radio.setChecked(True)
        self.dec_radio.setObjectName("compBtn") # Reuse segmented style
        self.dec_radio.clicked.connect(lambda: self._on_pixel_format_changed(False))
        
        self.hex_radio = QPushButton("Hex")
        self.hex_radio.setCheckable(True)
        self.hex_radio.setObjectName("compBtn") # Reuse segmented style
        self.hex_radio.clicked.connect(lambda: self._on_pixel_format_changed(True))
        
        pixel_row.addWidget(self.dec_radio)
        pixel_row.addWidget(self.hex_radio)
        pixel_row.addStretch()
        analysis_layout.addRow("Values:", pixel_row)
        
        content_layout.addWidget(analysis_group)

        # 3. VIEW OPTIONS
        view_group = QGroupBox("VIEW OPTIONS")
        view_layout = QVBoxLayout(view_group)
        view_layout.setSpacing(6)
        
        self.overlay_checkbox = QCheckBox("PSNR Heatmap")
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.toggled.connect(self.overlay_toggled.emit)

        self.overlay_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_opacity_slider.setRange(0, 100)
        self.overlay_opacity_slider.setValue(100)
        self.overlay_opacity_slider.setToolTip("PSNR overlay opacity")
        self.overlay_opacity_value = QLabel("100%")
        self.overlay_opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.overlay_opacity_slider.valueChanged.connect(self._on_overlay_opacity_changed)
        
        self.grid_checkbox = QCheckBox("Grid Lines")
        self.grid_checkbox.setChecked(False)
        self.grid_checkbox.toggled.connect(self.grid_toggled.emit)
        
        self.diff_checkbox = QCheckBox("Diff View (Split)")
        self.diff_checkbox.setChecked(False)
        self.diff_checkbox.toggled.connect(self._on_diff_view_toggled)

        self.diff_mode_group = QButtonGroup(self)
        self.diff_mode_group.setExclusive(True)
        diff_mode_row = QHBoxLayout()
        diff_mode_row.setSpacing(1)

        self.diff_mode_s1_ref = QPushButton("S1 vs Ref")
        self.diff_mode_s1_ref.setCheckable(True)
        self.diff_mode_s1_ref.setObjectName("compBtn")
        self.diff_mode_s1_ref.setProperty("diff_mode", "s1_ref")

        self.diff_mode_s2_ref = QPushButton("S2 vs Ref")
        self.diff_mode_s2_ref.setCheckable(True)
        self.diff_mode_s2_ref.setObjectName("compBtn")
        self.diff_mode_s2_ref.setProperty("diff_mode", "s2_ref")

        self.diff_mode_s1_s2 = QPushButton("S1 vs S2")
        self.diff_mode_s1_s2.setCheckable(True)
        self.diff_mode_s1_s2.setChecked(True)
        self.diff_mode_s1_s2.setObjectName("compBtn")
        self.diff_mode_s1_s2.setProperty("diff_mode", "s1_s2")

        for btn in (self.diff_mode_s1_ref, self.diff_mode_s2_ref, self.diff_mode_s1_s2):
            self.diff_mode_group.addButton(btn)
            diff_mode_row.addWidget(btn)

        self.diff_mode_group.buttonClicked.connect(self._on_diff_mode_changed)

        view_layout.addWidget(self.overlay_checkbox)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity"))
        opacity_row.addWidget(self.overlay_opacity_slider)
        opacity_row.addWidget(self.overlay_opacity_value)
        view_layout.addLayout(opacity_row)
        view_layout.addWidget(self.grid_checkbox)
        view_layout.addWidget(self.diff_checkbox)
        view_layout.addLayout(diff_mode_row)
        for btn in (self.diff_mode_s1_ref, self.diff_mode_s2_ref, self.diff_mode_s1_s2):
            btn.setEnabled(self.diff_checkbox.isChecked())
        
        content_layout.addWidget(view_group)
        content_layout.addStretch()

        # 4. NAVIGATION (Fixed at bottom of scroll area content, but visually distinct)
        nav_group = QGroupBox("NAVIGATION")
        nav_layout = QVBoxLayout(nav_group)
        nav_layout.setSpacing(8)
        
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.valueChanged.connect(self._on_frame_changed)
        nav_layout.addWidget(self.frame_slider)
        
        cntrl_row = QHBoxLayout()
        cntrl_row.setSpacing(10)
        
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setObjectName("playBtn")
        self.prev_btn.setToolTip("Previous Frame")
        self.prev_btn.clicked.connect(self._prev_frame)
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setCheckable(True)
        self.play_btn.setToolTip("Play/Pause")
        self.play_btn.clicked.connect(self._toggle_play)
        
        self.next_btn = QPushButton("⏭")
        self.next_btn.setObjectName("playBtn")
        self.next_btn.setToolTip("Next Frame")
        self.next_btn.clicked.connect(self._next_frame)
        
        self.frame_label = QLabel("0 / 0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setStyleSheet("color: #007acc; font-weight: bold;")
        
        cntrl_row.addStretch()
        cntrl_row.addWidget(self.prev_btn)
        cntrl_row.addWidget(self.play_btn)
        cntrl_row.addWidget(self.next_btn)
        cntrl_row.addStretch()
        
        nav_layout.addLayout(cntrl_row)
        nav_layout.addWidget(self.frame_label, 0, Qt.AlignmentFlag.AlignHCenter)
        
        content_layout.addWidget(nav_group)
        
        # Finish Setup
        scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(scroll_area)
        
        # Initialize Playback Timer
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(100)
        self._play_timer.timeout.connect(self._play_next_frame)

    def _on_overlay_opacity_changed(self, value: int):
        self.overlay_opacity_value.setText(f"{value}%")
        self.overlay_opacity_changed.emit(value)

    def _on_diff_view_toggled(self, checked: bool):
        for btn in (self.diff_mode_s1_ref, self.diff_mode_s2_ref, self.diff_mode_s1_s2):
            btn.setEnabled(checked)
        self.diff_view_toggled.emit(checked)

    def _on_diff_mode_changed(self, _btn=None):
        btn = self.diff_mode_group.checkedButton()
        if btn is None:
            return
        self.diff_mode_changed.emit(btn.property("diff_mode"))

    def _create_file_input(self, placeholder, layout):
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        layout.addWidget(line_edit)
        return line_edit

    def _add_browse_btn(self, line_edit, filter_str):
        # Helper to add browse button next to input
        # Note: In this layout I'm putting the button inside the input visually or next to it
        # Let's use a horizontal layout wrapper for the input + button
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        
        # Remove line_edit from previous parent layout and add to this row
        layout = line_edit.parentWidget().layout()
        if layout:
            layout.removeWidget(line_edit)
            
        row.addWidget(line_edit)
        
        btn = QPushButton("...")
        btn.setObjectName("toolBtn")
        btn.clicked.connect(lambda: self._browse_file(line_edit, filter_str))
        row.addWidget(btn)
        
        # Add container back to original layout
        layout.addWidget(container)
        return btn

    def _toggle_collapse(self):
        """Toggle sidebar collapse state."""
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.content_widget.hide()
            self.collapse_btn.setText("▶")
            self.setMinimumWidth(32)
            self.setMaximumWidth(32)
        else:
            self.content_widget.show()
            self.collapse_btn.setText("◀")
            self.setMinimumWidth(32)
            self.setMaximumWidth(self._expanded_width)
        self.collapse_toggled.emit(self._collapsed)

    def _browse_file(self, line_edit: QLineEdit, file_filter: str):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select File", 
            "", 
            file_filter,
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if path:
            line_edit.setText(path)

    def _on_frame_changed(self, value: int):
        total = self.frame_slider.maximum() + 1
        self.frame_label.setText(f"{value} / {total - 1}")
        self.frame_changed.emit(value)

    def _prev_frame(self):
        if self.frame_slider.value() > 0:
            self.frame_slider.setValue(self.frame_slider.value() - 1)

    def _next_frame(self):
        if self.frame_slider.value() < self.frame_slider.maximum():
            self.frame_slider.setValue(self.frame_slider.value() + 1)

    def _on_pixel_format_changed(self, is_hex: bool):
        self._update_pixel_format_style(is_hex)
        self.hex_mode_toggled.emit(is_hex)
        
    def _update_pixel_format_style(self, is_hex: bool):
        # Update checked state
        self.dec_radio.setChecked(not is_hex)
        self.hex_radio.setChecked(is_hex)
        
        # Style logic to show active state
        active_style = "background-color: #0e639c; color: white;"
        inactive_style = "background-color: #3c3c3c; color: #cccccc;"
        
        self.dec_radio.setStyleSheet(inactive_style if is_hex else active_style)
        self.hex_radio.setStyleSheet(active_style if is_hex else inactive_style)

    def set_frame_count(self, count: int):
        """Set the total number of frames."""
        self.frame_slider.setRange(0, max(0, count - 1))
        self.frame_label.setText(f"0 / {count - 1}")

    def get_config(self) -> dict:
        """Get current configuration."""
        # Component from radio buttons
        checked_btn = self.comp_btn_group.checkedButton()
        comp_text = checked_btn.text().lower() if checked_btn else "yuv"

        return {
            "ref_path": self.ref_path.text(),
            "stream1_path": self.stream1_path.text(),
            "stream2_path": self.stream2_path.text(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "yuv_format": self.format_combo.currentText(),
            "block_size": int(self.block_size_combo.currentText()),
            "components": comp_text,
            "frame_idx": self.frame_slider.value(),
            "diff_mode": (self.diff_mode_group.checkedButton().property("diff_mode")
                          if self.diff_mode_group.checkedButton() else "s1_s2")
        }

    def _toggle_play(self):
        """Toggle play/pause state."""
        if self.play_btn.isChecked():
            self.play_btn.setText("⏸")
            self._play_timer.start()
        else:
            self.play_btn.setText("▶")
            self._play_timer.stop()

    def _play_next_frame(self):
        """Advance to next frame during playback."""
        if self.frame_slider.value() < self.frame_slider.maximum():
            self.frame_slider.setValue(self.frame_slider.value() + 1)
        else:
            # Loop back to start or stop
            self.frame_slider.setValue(0)
