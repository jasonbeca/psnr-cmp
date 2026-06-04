"""
Block Detail Dialog
Shows detailed pixel values for a selected block with PSNR calculation.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QScrollArea,
    QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPen, QBrush, QWheelEvent, QPainter
import numpy as np


class ZoomableBlockView(QGraphicsView):
    """Zoomable view for block pixel display."""
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._zoom = 1.0
        
    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        self._zoom *= factor
        if 0.2 <= self._zoom <= 5.0:
            self.scale(factor, factor)
        else:
            self._zoom = max(0.2, min(5.0, self._zoom))


class BlockDetailDialog(QDialog):
    """Dialog showing detailed pixel values for a block."""
    
    def __init__(self, 
                 block_x: int, block_y: int, block_size: int,
                 ref_y: np.ndarray = None, ref_u: np.ndarray = None, ref_v: np.ndarray = None,
                 stream_y: np.ndarray = None, stream_u: np.ndarray = None, stream_v: np.ndarray = None,
                 stream2_y: np.ndarray = None, stream2_u: np.ndarray = None, stream2_v: np.ndarray = None,
                 show_psnr: bool = True,
                 is_diff_view: bool = False,
                 component: str = "yuv",
                 parent=None):
        super().__init__(parent)
        self.block_x = block_x
        self.block_y = block_y
        self.block_size = block_size
        self.ref_y = ref_y
        self.ref_u = ref_u
        self.ref_v = ref_v
        self.stream_y = stream_y
        self.stream_u = stream_u
        self.stream_v = stream_v
        self.stream2_y = stream2_y
        self.stream2_u = stream2_u
        self.stream2_v = stream2_v
        self.show_psnr = show_psnr
        self.is_diff_view = is_diff_view
        self.component = component.lower()
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.setWindowTitle(f"Block Detail - ({self.block_x * self.block_size}, {self.block_y * self.block_size})")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: #cccccc; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Block grids area
        grids_layout = QHBoxLayout()
        grids_layout.setSpacing(20)
        
        # Calculate block positions
        y_x = self.block_x * self.block_size
        y_y = self.block_y * self.block_size
        
        # For 420 format, U/V are half size
        uv_scale = 2  # Assuming 420
        uv_x = self.block_x * self.block_size // uv_scale
        uv_y = self.block_y * self.block_size // uv_scale
        uv_size = self.block_size // uv_scale
        
        if self.is_diff_view:
            # Diff view: show stream1 vs stream2 difference
            self._add_diff_grids(grids_layout, y_x, y_y, uv_x, uv_y, uv_size)
        else:
            # Normal view: show ref vs stream
            self._add_normal_grids(grids_layout, y_x, y_y, uv_x, uv_y, uv_size)
        
        layout.addLayout(grids_layout)
        
        # PSNR calculation text (only for non-diff views with overlay on)
        if self.show_psnr and not self.is_diff_view and self.ref_y is not None:
            psnr_text = self._calculate_psnr_text(y_x, y_y, uv_x, uv_y, uv_size)
            psnr_label = QLabel(psnr_text)
            psnr_label.setStyleSheet("color: #4ec9b0; font-family: Consolas; font-size: 12px;")
            psnr_label.setWordWrap(True)
            layout.addWidget(psnr_label)
        
        layout.addStretch()
    
    def _add_normal_grids(self, layout, y_x, y_y, uv_x, uv_y, uv_size):
        """Add Y, U, V grids for normal (non-diff) view."""
        if self.component in ['yuv', 'y']:
            if self.stream_y is not None:
                y_widget = self._create_pixel_grid(
                    f"Y ({y_x}, {y_y})",
                    self.stream_y, y_x, y_y, self.block_size
                )
                layout.addWidget(y_widget)
        
        if self.component in ['yuv', 'u']:
            if self.stream_u is not None:
                u_widget = self._create_pixel_grid(
                    f"Cb ({uv_x}, {uv_y})",
                    self.stream_u, uv_x, uv_y, uv_size
                )
                layout.addWidget(u_widget)
        
        if self.component in ['yuv', 'v']:
            if self.stream_v is not None:
                v_widget = self._create_pixel_grid(
                    f"Cr ({uv_x}, {uv_y})",
                    self.stream_v, uv_x, uv_y, uv_size
                )
                layout.addWidget(v_widget)
    
    def _add_diff_grids(self, layout, y_x, y_y, uv_x, uv_y, uv_size):
        """Add Y, U, V grids for diff view with yellow highlighting."""
        if self.component in ['yuv', 'y']:
            if self.stream_y is not None and self.stream2_y is not None:
                y_widget = self._create_diff_grid(
                    f"Y Diff ({y_x}, {y_y})",
                    self.stream_y, self.stream2_y, y_x, y_y, self.block_size
                )
                layout.addWidget(y_widget)
        
        if self.component in ['yuv', 'u']:
            if self.stream_u is not None and self.stream2_u is not None:
                u_widget = self._create_diff_grid(
                    f"Cb Diff ({uv_x}, {uv_y})",
                    self.stream_u, self.stream2_u, uv_x, uv_y, uv_size
                )
                layout.addWidget(u_widget)
        
        if self.component in ['yuv', 'v']:
            if self.stream_v is not None and self.stream2_v is not None:
                v_widget = self._create_diff_grid(
                    f"Cr Diff ({uv_x}, {uv_y})",
                    self.stream_v, self.stream2_v, uv_x, uv_y, uv_size
                )
                layout.addWidget(v_widget)
    
    def _create_pixel_grid(self, title: str, plane: np.ndarray, 
                           start_x: int, start_y: int, size: int) -> QWidget:
        """Create a widget showing pixel values in a grid."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #569cd6; font-weight: bold; font-size: 13px;")
        layout.addWidget(title_label)
        
        # Create scene and view
        scene = QGraphicsScene()
        view = ZoomableBlockView(scene)
        view.setMinimumSize(300, 250)
        
        cell_size = 28
        font = QFont("Consolas", 8)
        
        # Extract block pixels
        h, w = plane.shape
        end_x = min(start_x + size, w)
        end_y = min(start_y + size, h)
        
        for py in range(start_y, end_y):
            for px in range(start_x, end_x):
                local_x = px - start_x
                local_y = py - start_y
                
                val = plane[py, px] if py < h and px < w else 0
                
                # Cell background
                rect = QGraphicsRectItem(local_x * cell_size, local_y * cell_size, 
                                         cell_size, cell_size)
                rect.setPen(QPen(QColor(60, 60, 60)))
                rect.setBrush(QBrush(QColor(30, 30, 30)))
                scene.addItem(rect)
                
                # Value text
                text = QGraphicsTextItem(str(int(val)))
                text.setFont(font)
                text.setDefaultTextColor(QColor(0, 255, 255))  # Cyan
                text.setPos(local_x * cell_size + 2, local_y * cell_size + 4)
                scene.addItem(text)
        
        layout.addWidget(view)
        return widget
    
    def _create_diff_grid(self, title: str, plane1: np.ndarray, plane2: np.ndarray,
                          start_x: int, start_y: int, size: int) -> QWidget:
        """Create a widget showing pixel differences with yellow highlighting."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #569cd6; font-weight: bold; font-size: 13px;")
        layout.addWidget(title_label)
        
        # Create scene and view
        scene = QGraphicsScene()
        view = ZoomableBlockView(scene)
        view.setMinimumSize(300, 250)
        
        cell_size = 28
        font = QFont("Consolas", 8)
        
        h1, w1 = plane1.shape
        h2, w2 = plane2.shape
        end_x = min(start_x + size, w1, w2)
        end_y = min(start_y + size, h1, h2)
        
        for py in range(start_y, end_y):
            for px in range(start_x, end_x):
                local_x = px - start_x
                local_y = py - start_y
                
                val1 = plane1[py, px] if py < h1 and px < w1 else 0
                val2 = plane2[py, px] if py < h2 and px < w2 else 0
                diff = abs(int(val1) - int(val2))
                
                # Cell background - yellow if different
                rect = QGraphicsRectItem(local_x * cell_size, local_y * cell_size,
                                         cell_size, cell_size)
                rect.setPen(QPen(QColor(60, 60, 60)))
                if diff > 0:
                    rect.setBrush(QBrush(QColor(80, 80, 0)))  # Yellow tint
                else:
                    rect.setBrush(QBrush(QColor(30, 30, 30)))
                scene.addItem(rect)
                
                # Show diff value
                text_color = QColor(255, 255, 0) if diff > 0 else QColor(0, 255, 255)
                text = QGraphicsTextItem(str(diff))
                text.setFont(font)
                text.setDefaultTextColor(text_color)
                text.setPos(local_x * cell_size + 2, local_y * cell_size + 4)
                scene.addItem(text)
        
        layout.addWidget(view)
        return widget
    
    def _calculate_psnr_text(self, y_x, y_y, uv_x, uv_y, uv_size) -> str:
        """Calculate and format PSNR information."""
        lines = ["PSNR Calculation:"]
        
        if self.ref_y is not None and self.stream_y is not None:
            y_mse, y_psnr = self._calc_block_psnr(
                self.ref_y, self.stream_y, y_x, y_y, self.block_size
            )
            lines.append(f"  Y:  MSE = {y_mse:.2f}, PSNR = {y_psnr:.2f} dB")
        
        if self.ref_u is not None and self.stream_u is not None:
            u_mse, u_psnr = self._calc_block_psnr(
                self.ref_u, self.stream_u, uv_x, uv_y, uv_size
            )
            lines.append(f"  Cb: MSE = {u_mse:.2f}, PSNR = {u_psnr:.2f} dB")
        
        if self.ref_v is not None and self.stream_v is not None:
            v_mse, v_psnr = self._calc_block_psnr(
                self.ref_v, self.stream_v, uv_x, uv_y, uv_size
            )
            lines.append(f"  Cr: MSE = {v_mse:.2f}, PSNR = {v_psnr:.2f} dB")
        
        return "\n".join(lines)
    
    def _calc_block_psnr(self, ref: np.ndarray, stream: np.ndarray,
                         x: int, y: int, size: int) -> tuple:
        """Calculate MSE and PSNR for a block."""
        h, w = ref.shape
        end_x = min(x + size, w)
        end_y = min(y + size, h)
        
        ref_block = ref[y:end_y, x:end_x].astype(np.float64)
        stream_block = stream[y:end_y, x:end_x].astype(np.float64)
        
        mse = np.mean((ref_block - stream_block) ** 2)
        if mse == 0:
            return 0.0, float('inf')
        psnr = 10 * np.log10(255.0 ** 2 / mse)
        return mse, psnr
