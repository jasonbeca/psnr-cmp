"""
Block Detail View
In-place infinite canvas for viewing detailed block pixels.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QFont, QColor, QPen, QBrush, QWheelEvent, QPainter, QTransform
import numpy as np


class ZoomableDetailGraphicsView(QGraphicsView):
    """Zoomable view for block details with manual anchor logic."""
    
    transform_changed = pyqtSignal(QTransform)
    scroll_position_changed = pyqtSignal(int, int)  # horizontal, vertical scroll values
    pixel_clicked = pyqtSignal(str, int, int)  # component, global x, y
    view_right_clicked = pyqtSignal()     # signal to exit detail mode
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        self._syncing = False
        self._syncing_scroll = False
        
    def wheelEvent(self, event: QWheelEvent):
        """Handle zoom with anchor under mouse."""
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
            
        new_zoom = self._zoom * zoom_factor
        if new_zoom < self._min_zoom or new_zoom > self._max_zoom:
            return
            
        self._zoom = new_zoom
        
        # Anchor under mouse logic
        old_pos = self.mapToScene(event.position().toPoint())
        self.scale(zoom_factor, zoom_factor)
        new_pos = self.mapToScene(event.position().toPoint())
        
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
        if not self._syncing:
            self.transform_changed.emit(self.transform())
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                # If we are clicking on an item (pixel), emit signal
                item = self.scene().itemAt(self.mapToScene(event.pos()), QTransform())
                if isinstance(item, (QGraphicsRectItem, QGraphicsTextItem)):
                    # Find the rect item (parent or self)
                    if isinstance(item, QGraphicsTextItem):
                        item = item.parentItem()
                    
                    if hasattr(item, 'pixel_x') and hasattr(item, 'pixel_y') and hasattr(item, 'component'):
                        self.pixel_clicked.emit(item.component, item.pixel_x, item.pixel_y)
                        
        elif event.button() == Qt.MouseButton.RightButton:
            self.view_right_clicked.emit()
            
        super().mousePressEvent(event)
        
    def sync_transform(self, transform: QTransform):
        """Sync transform from another view."""
        if self._syncing:
            return
        self._syncing = True
        self.setTransform(transform)
        self._zoom = transform.m11()
        self._syncing = False
        
    def scrollContentsBy(self, dx, dy):
        """Override to emit scroll sync signal."""
        super().scrollContentsBy(dx, dy)
        if not self._syncing_scroll:
            h_val = self.horizontalScrollBar().value()
            v_val = self.verticalScrollBar().value()
            self.scroll_position_changed.emit(h_val, v_val)
            
    def sync_scroll_position(self, h_val, v_val):
        """Sync scroll position from another view."""
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.horizontalScrollBar().setValue(h_val)
        self.verticalScrollBar().setValue(v_val)
        self._syncing_scroll = False


class BlockDetailView(QWidget):
    """Widget containing the infinite canvas for block details."""
    
    # Signals to sync with other views
    transform_changed = pyqtSignal(QTransform)
    scroll_position_changed = pyqtSignal(int, int)  # h, v scroll values
    pixel_selected = pyqtSignal(str, int, int) # component, x, y
    exit_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._hex_mode = False
        self._highlighted_pixel = None # (component, x, y)
        self._pixel_items = {} # (component, x, y) -> rect_item
        
        # Grid parameters
        self.cell_size = 40
        self.spacing = 20
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.title_label = QLabel("Detail View")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #569cd6;")
        layout.addWidget(self.title_label)
        
        self.scene = QGraphicsScene()
        # Set massive scene rect for unlimited drag (no memory impact - just logical coords)
        self.scene.setSceneRect(-100000, -100000, 200000, 200000)
        self.view = ZoomableDetailGraphicsView(self.scene)
        
        # Forward signals
        self.view.transform_changed.connect(self.transform_changed.emit)
        self.view.scroll_position_changed.connect(self.scroll_position_changed.emit)
        self.view.view_right_clicked.connect(self.exit_requested.emit)
        self.view.pixel_clicked.connect(self._on_pixel_clicked)
        
        layout.addWidget(self.view)

    def set_title(self, title: str):
        self.title_label.setText(title)
        
    def _on_pixel_clicked(self, component, x, y):
        self.set_highlighted_pixel(component, x, y)
        self.pixel_selected.emit(component, x, y)
        
    def set_highlighted_pixel(self, component, x, y):
        """Highlight a specific pixel in the grid with extended rounded border."""
        # Remove old highlight overlay safely
        if hasattr(self, '_highlight_overlay') and self._highlight_overlay is not None:
            try:
                self.scene.removeItem(self._highlight_overlay)
            except RuntimeError:
                pass  # Item already deleted (e.g., scene was cleared)
            self._highlight_overlay = None
            
        # Restore old item's original pen (if exists)
        if self._highlighted_pixel and self._highlighted_pixel in self._pixel_items:
            old_item = self._pixel_items[self._highlighted_pixel]
            old_item.setPen(QPen(QColor(100, 100, 160)))  # Light purple-blue
            
        self._highlighted_pixel = (component, x, y)
        
        # Create extended highlight overlay
        if (component, x, y) in self._pixel_items:
            item = self._pixel_items[(component, x, y)]
            rect = item.rect()
            
            # Extended border - 6px larger on each side with rounded corners
            extend = 6
            from PyQt6.QtWidgets import QGraphicsPathItem
            from PyQt6.QtGui import QPainterPath
            
            path = QPainterPath()
            extended_rect = rect.adjusted(-extend, -extend, extend, extend)
            path.addRoundedRect(extended_rect, 10, 10)  # 10px corner radius
            
            overlay = QGraphicsPathItem(path)
            pen = QPen(QColor(200, 100, 255))  # Light magenta/purple
            pen.setWidth(2)
            overlay.setPen(pen)
            overlay.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            overlay.setZValue(1000)  # On top of everything
            
            self.scene.addItem(overlay)
            self._highlight_overlay = overlay
            
    def set_hex_mode(self, enabled: bool):
        """Toggle Hex/Dec display mode."""
        if self._hex_mode == enabled:
            return
            
        self._hex_mode = enabled
        
        # Update all text items
        for _, rect_item in self._pixel_items.items():
            val = rect_item.pixel_val
            text_item = rect_item.text_item
            
            if self._hex_mode:
                text_item.setPlainText(f"{int(val):02X}")
            else:
                text_item.setPlainText(str(int(val)))
                
    def sync_transform(self, transform):
        self.view.sync_transform(transform)
        
    def sync_scroll_position(self, h_val, v_val):
        """Sync scroll position from another view."""
        self.view.sync_scroll_position(h_val, v_val)

    def set_data(self, 
                 block_x: int, block_y: int, block_size: int,
                 data_y: np.ndarray = None, data_u: np.ndarray = None, data_v: np.ndarray = None,
                 diff_y: np.ndarray = None, diff_u: np.ndarray = None, diff_v: np.ndarray = None,
                 is_diff_mode: bool = False,
                 show_psnr_text: str = None,
                 main_label: str = "Y"):
        """Render the block data."""
        # Reset overlay reference before clearing scene to avoid crash
        self._highlight_overlay = None
        self.scene.clear()
        self._pixel_items.clear()
        self._highlighted_pixel = None
        
        # Calculate start positions in full-frame coordinates
        start_x = block_x * block_size
        start_y = block_y * block_size

        def slice_block(data: np.ndarray, sx: int, sy: int, bw: int, bh: int):
            if data is None:
                return None
            h, w = data.shape
            end_x = min(sx + bw, w)
            end_y = min(sy + bh, h)
            if end_x <= sx or end_y <= sy:
                return None
            return data[sy:end_y, sx:end_x]
        
        current_x_offset = 0
        max_grid_height = 0
        
        # Render Y Grid
        if data_y is not None:
            y_block = slice_block(data_y, start_x, start_y, block_size, block_size)
            y_diff_block = slice_block(diff_y, start_x, start_y, block_size, block_size)
            if y_block is not None:
                self._draw_grid(y_block, start_x, start_y, current_x_offset, 0, main_label, is_diff_mode, y_diff_block)
                current_x_offset += (y_block.shape[1] * self.cell_size) + self.spacing
                max_grid_height = max(max_grid_height, y_block.shape[0])

        # Render U/V Grids (if available) - assuming YUV order
        # For layout, place U next to Y, V next to U
        
        if data_u is not None:
            # Infer subsampling ratio from plane shapes
            scale_x = max(1, data_y.shape[1] // data_u.shape[1]) if data_y is not None else 1
            scale_y = max(1, data_y.shape[0] // data_u.shape[0]) if data_y is not None else 1
            u_start_x = start_x // scale_x
            u_start_y = start_y // scale_y
            u_block_w = max(1, block_size // scale_x)
            u_block_h = max(1, block_size // scale_y)
            u_block = slice_block(data_u, u_start_x, u_start_y, u_block_w, u_block_h)
            u_diff_block = slice_block(diff_u, u_start_x, u_start_y, u_block_w, u_block_h)
            if u_block is not None:
                self._draw_grid(u_block, u_start_x, u_start_y, current_x_offset, 0, "Cb", is_diff_mode, u_diff_block)
                current_x_offset += (u_block.shape[1] * self.cell_size) + self.spacing
                max_grid_height = max(max_grid_height, u_block.shape[0])
             
        if data_v is not None:
            scale_x = max(1, data_y.shape[1] // data_v.shape[1]) if data_y is not None else 1
            scale_y = max(1, data_y.shape[0] // data_v.shape[0]) if data_y is not None else 1
            v_start_x = start_x // scale_x
            v_start_y = start_y // scale_y
            v_block_w = max(1, block_size // scale_x)
            v_block_h = max(1, block_size // scale_y)
            v_block = slice_block(data_v, v_start_x, v_start_y, v_block_w, v_block_h)
            v_diff_block = slice_block(diff_v, v_start_x, v_start_y, v_block_w, v_block_h)
            if v_block is not None:
                self._draw_grid(v_block, v_start_x, v_start_y, current_x_offset, 0, "Cr", is_diff_mode, v_diff_block)
                current_x_offset += (v_block.shape[1] * self.cell_size) + self.spacing
                max_grid_height = max(max_grid_height, v_block.shape[0])
             
        # Add PSNR Text if provided - white text
        if show_psnr_text:
            text_item = QGraphicsTextItem(show_psnr_text)
            font = QFont("Consolas", 10)
            text_item.setFont(font)
            text_item.setDefaultTextColor(QColor(255, 255, 255))  # White
            # Place below the grids
            text_y = (max_grid_height * self.cell_size) + 20
            text_item.setPos(0, text_y)
            self.scene.addItem(text_item)
            
    def _draw_grid(self, data: np.ndarray, logic_start_x, logic_start_y, draw_offset_x, draw_offset_y, 
                   label: str, is_diff: bool, diff_data: np.ndarray = None):
        """Draw a single pixel grid."""
        h, w = data.shape
        
        # Label with coordinates (e.g., "Y (688, 528)") - white text
        label_text = f"{label} ({logic_start_x}, {logic_start_y})"
        label_item = QGraphicsTextItem(label_text)
        label_item.setDefaultTextColor(QColor(255, 255, 255))  # White
        label_item.setPos(draw_offset_x, draw_offset_y - 25)
        self.scene.addItem(label_item)
        
        font = QFont("Consolas", 8)
        
        for y in range(h):
            for x in range(w):
                val = data[y, x]
                
                # Determine color
                bg_color = QColor(30, 30, 30)
                text_color = QColor(0, 255, 255) # Cyan
                
                if is_diff:
                     # For diff view, data contains diff values
                     # But wait, in diff view, we usually show diff values directly.
                     if val > 0:
                         text_color = QColor(255, 255, 0) # Yellow text for diff
                         bg_color = QColor(50, 50, 30) # Slight yellow tint bg
                elif diff_data is not None:
                    # Normal view but showing diff highlighting? 
                    # Actually requirement says "diff view... show diff values... non-zero diffs in yellow"
                    # For normal views, "if overlay mode... show psnr text"
                    pass

                # Rect with light purple-blue border
                rect = QGraphicsRectItem(draw_offset_x + x * self.cell_size, 
                                         draw_offset_y + y * self.cell_size,
                                         self.cell_size, self.cell_size)
                rect.setPen(QPen(QColor(100, 100, 160)))  # Light purple-blue border
                rect.setBrush(QBrush(bg_color))
                
                # Store metadata for selection
                rect.pixel_x = logic_start_x + x
                rect.pixel_y = logic_start_y + y
                rect.pixel_val = val
                rect.component = label # "Y", "Cb", "Cr"
                
                self.scene.addItem(rect)
                self._pixel_items[(label, rect.pixel_x, rect.pixel_y)] = rect
                
                # Text
                text_str = f"{int(val):02X}" if self._hex_mode else str(int(val))
                text = QGraphicsTextItem(text_str, rect)
                text.setFont(font)
                text.setDefaultTextColor(text_color)
                
                # Center text
                # We need to calculate position after font metrics, or just approximate offset
                text.setPos(draw_offset_x + x * self.cell_size + 2, 
                            draw_offset_y + y * self.cell_size + 4)
                
                rect.text_item = text # Link for updates logic
