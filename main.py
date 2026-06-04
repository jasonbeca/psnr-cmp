"""
PSNR Comparison Tool
A PyQt6 application for comparing PSNR between video streams.
VSCode-style dark theme with Windows Immersive Dark Mode support.
"""
import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon
from ui.main_window import MainWindow

# Constants for DwmSetWindowAttribute
DWMWA_USE_IMMERSIVE_DARK_MODE = 20

def set_windows_dark_mode(hwnd):
    """Enable Windows Immersive Dark Mode for the title bar."""
    try:
        # Check if DwmSetWindowAttribute is available (Windows 11 / Windows 10 20H1+)
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
}
QSplitter::handle {
    background-color: #3c3c3c;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
QLabel {
    color: #cccccc;
    background: transparent;
}
QGraphicsView {
    background-color: #252526;
    border: 1px solid #2d2d2d;
}
QToolTip {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #3c3c3c;
    padding: 4px;
}
/* Scrollbars (VSCode Style) */
QScrollBar:vertical {
    background: #252526;
    width: 10px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: #424242;
    min-height: 20px;
    border-radius: 5px;
    border: none;
}
QScrollBar::handle:vertical:hover {
    background: #4f4f4f;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: #252526;
    height: 10px;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #424242;
    min-width: 20px;
    border-radius: 5px;
    border: none;
}
QScrollBar::handle:horizontal:hover {
    background: #4f4f4f;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
"""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    
    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))
    palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 38))
    palette.setColor(QPalette.ColorRole.Text, QColor(204, 204, 204))
    palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 60))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(204, 204, 204))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    window = MainWindow()
    
    # Set application icon
    icon_path = "icon.png"
    app.setWindowIcon(QIcon(icon_path))
    window.setWindowIcon(QIcon(icon_path))
    
    # Enable dark title bar
    if sys.platform == "win32":
        set_windows_dark_mode(int(window.winId()))
        
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
