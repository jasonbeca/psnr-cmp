"""
PSNR View Widget
Displays a video frame with PSNR heatmap overlay, grid lines, and PSNR values.
Supports synchronized mouse wheel zoom (anchor under mouse) and Green-Yellow-Orange gradient.
"""
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QStackedLayout
)
from PyQt6.QtGui import QPixmap, QImage, QPen, QBrush, QColor, QFont, QWheelEvent, QTransform
from PyQt6.QtCore import Qt, pyqtSignal, QPointF


class ZoomableGraphicsView(QGraphicsView):
    """Custom QGraphicsView with mouse wheel zoom support.
    
    Zoom logic: Manual anchor under mouse - the scene point under cursor stays stationary.
    """
    
    transform_changed = pyqtSignal(QTransform)
    block_clicked = pyqtSignal(int, int)  # block_x, block_y
    block_right_clicked = pyqtSignal(int, int)  # block_x, block_y (for context menu)

    def __init__(self, scene, block_size_getter, psnr_grid_getter=None, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # We will handle anchoring manually for reliable behavior
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self._zoom_level = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        self._syncing = False
        self._block_size_getter = block_size_getter
        self._psnr_grid_getter = psnr_grid_getter
        self.setMouseTracking(True)

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zoom with proper anchor-under-mouse behavior."""
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor

        new_zoom = self._zoom_level * zoom_factor
        if new_zoom < self._min_zoom or new_zoom > self._max_zoom:
            return

        # Get the mouse position in viewport coordinates
        mouse_viewport_pos = event.position()
        
        # Get the scene position under the mouse BEFORE scaling
        scene_pos = self.mapToScene(mouse_viewport_pos.toPoint())

        # Apply scale
        self.scale(zoom_factor, zoom_factor)
        self._zoom_level = new_zoom

        # Get where that same scene point now appears in viewport coordinates AFTER scaling
        new_viewport_pos = self.mapFromScene(scene_pos)
        
        # Calculate how much we need to scroll to bring the scene point back under the mouse
        # delta = where it should be - where it is now
        delta_x = mouse_viewport_pos.x() - new_viewport_pos.x()
        delta_y = mouse_viewport_pos.y() - new_viewport_pos.y()
        
        # Adjust scrollbars (scrollbar adjustment is opposite to viewport movement)
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - int(delta_x)
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(delta_y)
        )

        if not self._syncing:
            self.transform_changed.emit(self.transform())

    def mousePressEvent(self, event):
        """Handle mouse click for block selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            block_size = self._block_size_getter()
            if block_size > 0:
                bx = int(scene_pos.x() // block_size)
                by = int(scene_pos.y() // block_size)
                if bx >= 0 and by >= 0:
                    self.block_clicked.emit(bx, by)
        elif event.button() == Qt.MouseButton.RightButton:
            scene_pos = self.mapToScene(event.pos())
            block_size = self._block_size_getter()
            if block_size > 0:
                bx = int(scene_pos.x() // block_size)
                by = int(scene_pos.y() // block_size)
                if bx >= 0 and by >= 0:
                    self.block_right_clicked.emit(bx, by)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Show coordinate tooltip on hover."""
        scene_pos = self.mapToScene(event.pos())
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        block_size = self._block_size_getter()
        
        if x >= 0 and y >= 0 and block_size > 0:
            bx = x // block_size
            by = y // block_size
            
            # Build tooltip
            tooltip = f"Pixel: ({x}, {y})\nBlock: ({bx}, {by})"
            
            # Add PSNR if available
            if self._psnr_grid_getter:
                psnr_grid = self._psnr_grid_getter()
                if psnr_grid is not None and by < psnr_grid.shape[0] and bx < psnr_grid.shape[1]:
                    psnr_val = psnr_grid[by, bx]
                    if psnr_val != float('inf'):
                        tooltip += f"\nPSNR: {psnr_val:.2f} dB"
                    else:
                        tooltip += "\nPSNR: ∞"
            
            self.setToolTip(tooltip)
        else:
            self.setToolTip("")
        
        super().mouseMoveEvent(event)

    def sync_transform(self, transform: QTransform):
        """Sync transform (zoom) from another view."""
        if self._syncing:
            return
        self._syncing = True
        self.setTransform(transform)
        self._zoom_level = transform.m11() 
        self._syncing = False

    def reset_zoom(self):
        """Reset zoom to fit the scene."""
        self.resetTransform()
        self._zoom_level = 1.0
        if self.scene() and self.scene().items():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)


class PSNRView(QWidget):
    """Widget to display a frame with PSNR heatmap overlay."""
    
    # Signals for view synchronization
    view_transform_changed = pyqtSignal(QTransform)
    block_selected = pyqtSignal(int, int)  # block_x, block_y
    scroll_x_changed = pyqtSignal(int)
    scroll_y_changed = pyqtSignal(int)
    block_right_clicked = pyqtSignal(int, int)  # block_x, block_y (for detail popup)

    def __init__(self, title: str = "Stream", parent=None):
        super().__init__(parent)
        self.title = title
        self.block_size = 64
        self.psnr_grid = None
        self.min_psnr = 20.0
        self.max_psnr = 50.0
        self.show_values = True
        self.show_grid_lines = True
        self._frame_width = 0
        self._frame_height = 0
        self._selected_block = None  # (bx, by)
        self._highlight_item = None
        self._show_overlay = True  # Controls overlay visibility
        self._show_grid = False  # Grid-only mode (no PSNR heatmap)
        self._overlay_opacity = 1.0
        
        # Reference frame data for PSNR calculation display
        self._ref_y = None
        self._ref_u = None
        self._ref_v = None
        
        self._zoom_initialized = False
        
        self._setup_ui()

    def set_title(self, title: str):
        self.title = title
        self.title_label.setText(title)
        self.detail_view.set_title(title)

    def set_overlay_visible(self, visible: bool):
        """Show or hide the PSNR heatmap overlay (but not the selection highlight)."""
        self._show_overlay = visible
        for item in self.heatmap_items:
            item.setVisible(visible)
        for item in self.grid_line_items:
            item.setVisible(visible)
        for item in self.text_items:
            item.setVisible(visible)
        if visible:
            self._apply_overlay_opacity()
        # Note: _highlight_item is NOT affected - always visible

    def set_overlay_opacity(self, opacity: float):
        """Set overlay opacity (0.0 - 1.0) for heatmap and labels."""
        self._overlay_opacity = max(0.0, min(1.0, opacity))
        self._apply_overlay_opacity()

    def _apply_overlay_opacity(self):
        for item in self.heatmap_items:
            item.setOpacity(self._overlay_opacity)
        for item in self.grid_line_items:
            item.setOpacity(self._overlay_opacity)
        for item in self.text_items:
            item.setOpacity(self._overlay_opacity)

    def set_grid_visible(self, visible: bool):
        """Show or hide the grid-only overlay (without PSNR heatmap)."""
        self._show_grid = visible
        for item in self.grid_only_items:
            item.setVisible(visible)

    def show_grid_only(self, block_size: int):
        """Draw grid-only overlay (no PSNR heatmap, just grid lines)."""
        # Clear existing grid-only items
        for item in self.grid_only_items:
            self.scene.removeItem(item)
        self.grid_only_items.clear()
        
        if self._frame_width == 0 or self._frame_height == 0:
            return
        
        self.block_size = block_size
        
        grid_pen = QPen(QColor(255, 255, 255, 150))
        grid_pen.setWidth(1)
        
        # Calculate grid dimensions
        blocks_x = (self._frame_width + block_size - 1) // block_size
        blocks_y = (self._frame_height + block_size - 1) // block_size
        
        # Draw vertical lines
        for bx in range(blocks_x + 1):
            x = min(bx * block_size, self._frame_width)
            line = QGraphicsLineItem(x, 0, x, self._frame_height)
            line.setPen(grid_pen)
            line.setVisible(self._show_grid)
            self.scene.addItem(line)
            self.grid_only_items.append(line)
        
        # Draw horizontal lines
        for by in range(blocks_y + 1):
            y = min(by * block_size, self._frame_height)
            line = QGraphicsLineItem(0, y, self._frame_width, y)
            line.setPen(grid_pen)
            line.setVisible(self._show_grid)
            self.scene.addItem(line)
            self.grid_only_items.append(line)

    def show_diff_highlight(self, diff_mask: np.ndarray, block_size: int):
        """Highlight blocks that have differences with transparent yellow.
        
        Args:
            diff_mask: 2D boolean array where True means block has differences
            block_size: Block size in pixels
        """
        # Clear existing grid-only items first
        for item in self.grid_only_items:
            self.scene.removeItem(item)
        self.grid_only_items.clear()
        
        if self._frame_width == 0 or self._frame_height == 0:
            return
        
        self.block_size = block_size
        
        grid_pen = QPen(QColor(255, 255, 255, 150))
        grid_pen.setWidth(1)
        
        # Calculate grid dimensions
        blocks_x = (self._frame_width + block_size - 1) // block_size
        blocks_y = (self._frame_height + block_size - 1) // block_size
        
        # Draw diff highlight rectangles
        for by in range(min(blocks_y, diff_mask.shape[0])):
            for bx in range(min(blocks_x, diff_mask.shape[1])):
                if diff_mask[by, bx]:
                    x = bx * block_size
                    y = by * block_size
                    
                    # Calculate actual block dimensions (clip to frame boundary)
                    block_w = min(block_size, self._frame_width - x)
                    block_h = min(block_size, self._frame_height - y)
                    
                    # Transparent yellow highlight
                    rect = QGraphicsRectItem(x, y, block_w, block_h)
                    rect.setPen(QPen(Qt.GlobalColor.transparent))
                    rect.setBrush(QBrush(QColor(255, 255, 0, 80)))  # Transparent yellow
                    rect.setVisible(self._show_grid)
                    self.scene.addItem(rect)
                    self.grid_only_items.append(rect)
        
        # Draw vertical grid lines
        for bx in range(blocks_x + 1):
            x = min(bx * block_size, self._frame_width)
            line = QGraphicsLineItem(x, 0, x, self._frame_height)
            line.setPen(grid_pen)
            line.setVisible(self._show_grid)
            self.scene.addItem(line)
            self.grid_only_items.append(line)
        
        # Draw horizontal grid lines
        for by in range(blocks_y + 1):
            y = min(by * block_size, self._frame_height)
            line = QGraphicsLineItem(0, y, self._frame_width, y)
            line.setPen(grid_pen)
            line.setVisible(self._show_grid)
            self.scene.addItem(line)
            self.grid_only_items.append(line)
    def _setup_ui(self):
        # Stacked layout to switch between Normal and Detail modes
        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        
        # --- Normal View Widget ---
        self.normal_widget = QWidget()
        normal_layout = QVBoxLayout(self.normal_widget)
        normal_layout.setContentsMargins(2, 2, 2, 2)

        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #569cd6;")
        normal_layout.addWidget(self.title_label)
        
        self.scene = QGraphicsScene()
        # Set massive scene rect for unlimited drag (no memory impact - just logical coords)
        self.scene.setSceneRect(-100000, -100000, 200000, 200000)
        self.view = ZoomableGraphicsView(self.scene, lambda: self.block_size, lambda: self.psnr_grid)
        
        # Sync Scrollbars (Normal View)
        self.view.horizontalScrollBar().valueChanged.connect(self._on_scroll_x)
        self.view.verticalScrollBar().valueChanged.connect(self._on_scroll_y)
        
        # Connect signals (Normal View)
        self.view.transform_changed.connect(self.view_transform_changed.emit)
        self.view.block_clicked.connect(self._on_block_clicked)
        self.view.block_right_clicked.connect(self.block_right_clicked.emit)
        
        normal_layout.addWidget(self.view)
        
        self.frame_item = None
        self.heatmap_items = []
        self.grid_line_items = []
        self.text_items = []
        self.grid_only_items = []  # Grid-only mode items (grid lines + diff highlight)
        
        self.info_label = QLabel("No frame loaded")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #cccccc;")
        normal_layout.addWidget(self.info_label)
        
        self.stack.addWidget(self.normal_widget)
        
        # --- Detail View Widget ---
        from .block_detail_view import BlockDetailView
        self.detail_view = BlockDetailView()
        self.detail_view.set_title(self.title)
        self.stack.addWidget(self.detail_view)
        
        self._syncing_scroll = False

    def enter_block_detail(self, bx, by, block_size, data_y, data_u, data_v, 
                          diff_y=None, diff_u=None, diff_v=None, 
                          is_diff_mode=False, psnr_text=None, main_label="Y"):
        """Switch to block detail mode."""
        self.detail_view.set_data(bx, by, block_size, 
                                 data_y, data_u, data_v, 
                                 diff_y, diff_u, diff_v, 
                                 is_diff_mode, psnr_text, main_label=main_label)
        self.stack.setCurrentWidget(self.detail_view)

    def exit_block_detail(self):
        """Switch back to normal view."""
        self.stack.setCurrentWidget(self.normal_widget)

    def get_detail_view(self):
        return self.detail_view

    def _on_scroll_x(self, value):
        if not self._syncing_scroll:
            self.scroll_x_changed.emit(value)

    def _on_scroll_y(self, value):
        if not self._syncing_scroll:
            self.scroll_y_changed.emit(value)

    def sync_scroll_x(self, value):
        """Sync horizontal scroll from another view."""
        self._syncing_scroll = True
        if self.stack.currentWidget() == self.normal_widget:
            self.view.horizontalScrollBar().setValue(value)
        self._syncing_scroll = False

    def sync_scroll_y(self, value):
        """Sync vertical scroll from another view."""
        self._syncing_scroll = True
        if self.stack.currentWidget() == self.normal_widget:
            self.view.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def sync_from_view(self, transform: QTransform):
        """Sync transform from another PSNRView."""
        if self.stack.currentWidget() == self.normal_widget:
            self.view.sync_transform(transform)
        else:
            self.detail_view.sync_transform(transform)

    def sync_block_selection(self, bx: int, by: int):
        """Sync block selection from another view."""
        # Allow selection even without psnr_grid (for diff view)
        if self._frame_width == 0 or self._frame_height == 0:
            return
        # Basic bounds check using frame dimensions
        max_bx = self._frame_width // self.block_size
        max_by = self._frame_height // self.block_size
        if bx >= max_bx or by >= max_by:
            return
        self._selected_block = (bx, by)
        self._update_highlight()

    def _on_block_clicked(self, bx: int, by: int):
        if self._frame_width == 0 or self._frame_height == 0:
            return
        max_bx = self._frame_width // self.block_size
        max_by = self._frame_height // self.block_size
        if bx >= max_bx or by >= max_by:
            return
        
        self._selected_block = (bx, by)
        self._update_highlight()
        self.block_selected.emit(bx, by)

    def set_reference_frame(self, y: np.ndarray, u: np.ndarray = None, v: np.ndarray = None):
        """Set reference frame data for PSNR calculation display."""
        self._ref_y = y
        self._ref_u = u
        self._ref_v = v

    def _update_highlight(self):
        """Update purple highlight on selected block."""
        if self._highlight_item is not None:
            self.scene.removeItem(self._highlight_item)
            self._highlight_item = None
        
        if self._selected_block is None:
            return
        
        bx, by = self._selected_block
        x = bx * self.block_size
        y = by * self.block_size
        
        self._highlight_item = QGraphicsRectItem(x, y, self.block_size, self.block_size)
        pen = QPen(QColor(128, 0, 255, 255))
        pen.setWidth(2)
        pen.setCosmetic(True)  # Keep same screen width regardless of zoom
        self._highlight_item.setPen(pen)
        self._highlight_item.setBrush(QBrush(Qt.GlobalColor.transparent))
        self._highlight_item.setZValue(100)
        self.scene.addItem(self._highlight_item)
        # Note: Highlight is always visible, regardless of overlay state

    def set_frame(self, y_plane: np.ndarray, u_plane: np.ndarray = None, v_plane: np.ndarray = None):
        """Set the frame to display (stores all planes, displays Y by default)."""
        self._y_plane = y_plane
        self._u_plane = u_plane
        self._v_plane = v_plane
        self._current_component = 'y'  # Default to Y
        
        height, width = y_plane.shape
        res_changed = (width != self._frame_width or height != self._frame_height)
        
        self._frame_width = width
        self._frame_height = height
        
        self._display_plane(y_plane, res_changed)

    def set_display_component(self, component: str):
        """Update displayed plane based on component selection (y, u, v, yuv)."""
        if not hasattr(self, '_y_plane') or self._y_plane is None:
            return
        
        component = component.lower()
        self._current_component = component
        
        if component == 'yuv':
            # Display as color image
            self._display_yuv_color()
        elif component == 'y':
            self._display_plane(self._y_plane, False)
        elif component == 'u' and self._u_plane is not None:
            # Upsample U to Y size for consistent display
            y_h, y_w = self._y_plane.shape
            u_h, u_w = self._u_plane.shape
            if u_h != y_h or u_w != y_w:
                scale_y = y_h // u_h
                scale_x = y_w // u_w
                upsampled = np.repeat(np.repeat(self._u_plane, scale_y, axis=0), scale_x, axis=1)
                self._display_plane(upsampled, False)
            else:
                self._display_plane(self._u_plane, False)
        elif component == 'v' and self._v_plane is not None:
            # Upsample V to Y size for consistent display
            y_h, y_w = self._y_plane.shape
            v_h, v_w = self._v_plane.shape
            if v_h != y_h or v_w != y_w:
                scale_y = y_h // v_h
                scale_x = y_w // v_w
                upsampled = np.repeat(np.repeat(self._v_plane, scale_y, axis=0), scale_x, axis=1)
                self._display_plane(upsampled, False)
            else:
                self._display_plane(self._v_plane, False)
        else:
            self._display_plane(self._y_plane, False)

    def _display_yuv_color(self):
        """Convert YUV to RGB and display as color image."""
        if self._y_plane is None:
            return
        
        y = self._y_plane.astype(np.float32)
        height, width = y.shape
        
        if self._u_plane is not None and self._v_plane is not None:
            # Upsample U and V to match Y dimensions (for 420/422 formats)
            u_h, u_w = self._u_plane.shape
            v_h, v_w = self._v_plane.shape
            
            # Simple nearest-neighbor upscaling
            u_scale_y = height // u_h
            u_scale_x = width // u_w
            u = np.repeat(np.repeat(self._u_plane, u_scale_y, axis=0), u_scale_x, axis=1).astype(np.float32)
            
            v_scale_y = height // v_h
            v_scale_x = width // v_w
            v = np.repeat(np.repeat(self._v_plane, v_scale_y, axis=0), v_scale_x, axis=1).astype(np.float32)
        else:
            # No U/V, show grayscale
            self._display_plane(self._y_plane, False)
            return
        
        # YUV to RGB conversion (BT.601)
        # R = Y + 1.402 * (V - 128)
        # G = Y - 0.344 * (U - 128) - 0.714 * (V - 128)
        # B = Y + 1.772 * (U - 128)
        r = y + 1.402 * (v - 128)
        g = y - 0.344 * (u - 128) - 0.714 * (v - 128)
        b = y + 1.772 * (u - 128)
        
        # Clip and convert to uint8
        r = np.clip(r, 0, 255).astype(np.uint8)
        g = np.clip(g, 0, 255).astype(np.uint8)
        b = np.clip(b, 0, 255).astype(np.uint8)
        
        # Create RGB image
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[:, :, 0] = r
        rgb[:, :, 1] = g
        rgb[:, :, 2] = b
        
        # Convert to QImage (RGB888)
        image = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image.copy())
        
        if self.frame_item is None:
            self.frame_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.frame_item)
        else:
            self.frame_item.setPixmap(pixmap)

    def _display_plane(self, plane: np.ndarray, fit_view: bool):
        """Display a single plane as grayscale image."""
        height, width = plane.shape
        image = QImage(plane.data, width, height, width, QImage.Format.Format_Grayscale8)
        pixmap = QPixmap.fromImage(image.copy())
        
        if self.frame_item is None:
            self.frame_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.frame_item)
        else:
            self.frame_item.setPixmap(pixmap)
        
        if not self._zoom_initialized or fit_view:
            self.view.fitInView(self.frame_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_initialized = True
        
        self.view.viewport().update()

    def set_psnr_grid(self, psnr_grid: np.ndarray, block_size: int):
        """Set PSNR grid and update heatmap overlay."""
        self.psnr_grid = psnr_grid
        self.block_size = block_size
        self._selected_block = None
        
        # Calculate dynamic range from current frame
        if self.psnr_grid is not None:
            valid_vals = self.psnr_grid[self.psnr_grid != float('inf')]
            if valid_vals.size > 0:
                self.min_psnr = float(valid_vals.min())
                self.max_psnr = float(valid_vals.max())
                # Ensure some range to avoid div by zero
                if self.max_psnr <= self.min_psnr:
                     self.max_psnr = self.min_psnr + 1.0
            else:
                 self.min_psnr = 0.0
                 self.max_psnr = 100.0

        self._update_heatmap()

    def _update_heatmap(self):
        """Redraw heatmap overlay."""
        for item in self.heatmap_items:
            self.scene.removeItem(item)
        self.heatmap_items.clear()
        
        for item in self.grid_line_items:
            self.scene.removeItem(item)
        self.grid_line_items.clear()
        
        for item in self.text_items:
            self.scene.removeItem(item)
        self.text_items.clear()
        
        if self._highlight_item is not None:
            self.scene.removeItem(self._highlight_item)
            self._highlight_item = None

        if self.psnr_grid is None:
            return

        grid_pen = QPen(QColor(255, 255, 255, 100))
        grid_pen.setWidth(1)
        
        font = QFont("Arial", 7)
        font.setBold(True)

        for by in range(self.psnr_grid.shape[0]):
            for bx in range(self.psnr_grid.shape[1]):
                psnr_val = self.psnr_grid[by, bx]
                color = self._psnr_to_color(psnr_val)
                
                x = bx * self.block_size
                y = by * self.block_size
                
                # Calculate actual block dimensions (clip to frame boundary)
                block_w = min(self.block_size, self._frame_width - x) if self._frame_width > 0 else self.block_size
                block_h = min(self.block_size, self._frame_height - y) if self._frame_height > 0 else self.block_size
                
                rect = QGraphicsRectItem(x, y, block_w, block_h)
                rect.setPen(QPen(Qt.GlobalColor.transparent))
                rect.setBrush(QBrush(color))
                
                if psnr_val != float('inf'):
                    tooltip = f"({x}, {y}) PSNR: {psnr_val:.2f} dB"
                else:
                    tooltip = f"({x}, {y}) PSNR: ∞"
                rect.setToolTip(tooltip)
                
                self.scene.addItem(rect)
                self.heatmap_items.append(rect)
                
                if self.show_values and self.block_size >= 24:
                    text_str = f"{psnr_val:.1f}" if psnr_val != float('inf') else "∞"
                    text_item = QGraphicsTextItem(text_str)
                    text_item.setFont(font)
                    text_item.setDefaultTextColor(QColor(255, 255, 255, 220))
                    
                    text_rect = text_item.boundingRect()
                    text_x = x + (block_w - text_rect.width()) / 2
                    text_y = y + (block_h - text_rect.height()) / 2
                    text_item.setPos(text_x, text_y)
                    
                    self.scene.addItem(text_item)
                    self.text_items.append(text_item)

        if self.show_grid_lines:
            # Use actual frame dimensions for grid lines
            grid_width = min(self.psnr_grid.shape[1] * self.block_size, self._frame_width) if self._frame_width > 0 else self.psnr_grid.shape[1] * self.block_size
            grid_height = min(self.psnr_grid.shape[0] * self.block_size, self._frame_height) if self._frame_height > 0 else self.psnr_grid.shape[0] * self.block_size
            
            for bx in range(self.psnr_grid.shape[1] + 1):
                x = min(bx * self.block_size, grid_width)
                line = QGraphicsLineItem(x, 0, x, grid_height)
                line.setPen(grid_pen)
                self.scene.addItem(line)
                self.grid_line_items.append(line)
            
            for by in range(self.psnr_grid.shape[0] + 1):
                y = min(by * self.block_size, grid_height)
                line = QGraphicsLineItem(0, y, grid_width, y)
                line.setPen(grid_pen)
                self.scene.addItem(line)
                self.grid_line_items.append(line)
        
        # Apply current overlay visibility state to all items
        if not self._show_overlay:
            for item in self.heatmap_items:
                item.setVisible(False)
            for item in self.grid_line_items:
                item.setVisible(False)
            for item in self.text_items:
                item.setVisible(False)
        else:
            self._apply_overlay_opacity()

    def _psnr_to_color(self, psnr: float) -> QColor:
        """Map PSNR value to color using user-defined gradient.
        
        Scheme (High PSNR -> Low PSNR):
        - Red (High)
        - Orange
        - Yellow
        - Light Green
        - Cyan (Low)
        """
        if psnr == float('inf'):
            return QColor(255, 0, 0, 140)  # Red for perfect (Highest)

        # Normalize t: 0.0 (Min/Low) -> 1.0 (Max/High)
        psnr = max(self.min_psnr, min(psnr, self.max_psnr))
        t = (psnr - self.min_psnr) / (self.max_psnr - self.min_psnr)

        # Invert logic: User wants Red at High, Cyan at Low.
        # Let's map t (0->1) to Cyan->Red
        
        # 4 stops: 
        # 0.00 - 0.25: Cyan -> Green
        # 0.25 - 0.50: Green -> Yellow
        # 0.50 - 0.75: Yellow -> Orange
        # 0.75 - 1.00: Orange -> Red
        
        if t < 0.25:
            # Cyan (0,255,255) -> Green (0,255,0)
            # R: 0, G: 255, B: 255->0
            factor = t * 4
            r = 0
            g = 255
            b = int(255 * (1 - factor))
        elif t < 0.5:
            # Green (0,255,0) -> Yellow (255,255,0)
            # R: 0->255, G: 255, B: 0
            factor = (t - 0.25) * 4
            r = int(255 * factor)
            g = 255
            b = 0
        elif t < 0.75:
            # Yellow (255,255,0) -> Orange (255,165,0)
            # R: 255, G: 255->165, B: 0
            factor = (t - 0.5) * 4
            r = 255
            g = int(255 - (255 - 165) * factor)
            b = 0
        else:
            # Orange (255,165,0) -> Red (255,0,0)
            # R: 255, G: 165->0, B: 0
            factor = (t - 0.75) * 4
            r = 255
            g = int(165 * (1 - factor))
            b = 0

        return QColor(r, g, b, 140)

    def set_psnr_range(self, min_psnr: float, max_psnr: float):
        """Set PSNR range for color mapping."""
        self.min_psnr = min_psnr
        self.max_psnr = max_psnr
        self._update_heatmap()

    def set_psnr_diff_grid(self, psnr_diff: np.ndarray, block_size: int):
        """Set PSNR difference grid and update heatmap with diverging color scheme.
        
        Color scheme:
        - Green: Positive values (S1 is better than S2)
        - Yellow: Near zero (similar quality)
        - Red: Negative values (S2 is better than S1)
        """
        self.psnr_grid = psnr_diff  # Reuse for tooltip
        self.block_size = block_size
        self._selected_block = None
        
        # Clear existing items
        for item in self.heatmap_items:
            self.scene.removeItem(item)
        self.heatmap_items.clear()
        
        for item in self.grid_line_items:
            self.scene.removeItem(item)
        self.grid_line_items.clear()
        
        for item in self.text_items:
            self.scene.removeItem(item)
        self.text_items.clear()
        
        if self._highlight_item is not None:
            self.scene.removeItem(self._highlight_item)
            self._highlight_item = None
        
        if psnr_diff is None:
            return
        
        # Calculate symmetric range for diverging colormap
        max_abs = max(abs(psnr_diff.min()), abs(psnr_diff.max()), 1.0)
        
        grid_pen = QPen(QColor(255, 255, 255, 100))
        grid_pen.setWidth(1)
        
        font = QFont("Arial", 7)
        font.setBold(True)
        
        for by in range(psnr_diff.shape[0]):
            for bx in range(psnr_diff.shape[1]):
                diff_val = psnr_diff[by, bx]
                color = self._psnr_diff_to_color(diff_val, max_abs)
                
                x = bx * self.block_size
                y = by * self.block_size
                
                # Calculate actual block dimensions (clip to frame boundary)
                block_w = min(self.block_size, self._frame_width - x) if self._frame_width > 0 else self.block_size
                block_h = min(self.block_size, self._frame_height - y) if self._frame_height > 0 else self.block_size
                
                rect = QGraphicsRectItem(x, y, block_w, block_h)
                rect.setPen(QPen(Qt.GlobalColor.transparent))
                rect.setBrush(QBrush(color))
                
                if diff_val >= 0:
                    tooltip = f"({x}, {y}) PSNR Diff: +{diff_val:.2f} dB (S1 better)"
                else:
                    tooltip = f"({x}, {y}) PSNR Diff: {diff_val:.2f} dB (S2 better)"
                rect.setToolTip(tooltip)
                
                self.scene.addItem(rect)
                self.heatmap_items.append(rect)
                
                # Show values if block is large enough
                if self.show_values and self.block_size >= 24:
                    text_str = f"{diff_val:+.1f}"
                    text_item = QGraphicsTextItem(text_str)
                    text_item.setFont(font)
                    text_item.setDefaultTextColor(QColor(255, 255, 255, 220))
                    
                    text_rect = text_item.boundingRect()
                    text_x = x + (block_w - text_rect.width()) / 2
                    text_y = y + (block_h - text_rect.height()) / 2
                    text_item.setPos(text_x, text_y)
                    
                    self.scene.addItem(text_item)
                    self.text_items.append(text_item)
        
        # Draw grid lines
        if self.show_grid_lines:
            # Use actual frame dimensions for grid lines
            grid_width = min(psnr_diff.shape[1] * self.block_size, self._frame_width) if self._frame_width > 0 else psnr_diff.shape[1] * self.block_size
            grid_height = min(psnr_diff.shape[0] * self.block_size, self._frame_height) if self._frame_height > 0 else psnr_diff.shape[0] * self.block_size
            
            for bx in range(psnr_diff.shape[1] + 1):
                x = min(bx * self.block_size, grid_width)
                line = QGraphicsLineItem(x, 0, x, grid_height)
                line.setPen(grid_pen)
                self.scene.addItem(line)
                self.grid_line_items.append(line)
            
            for by in range(psnr_diff.shape[0] + 1):
                y = min(by * self.block_size, grid_height)
                line = QGraphicsLineItem(0, y, grid_width, y)
                line.setPen(grid_pen)
                self.scene.addItem(line)
                self.grid_line_items.append(line)
        
        # Apply current overlay visibility state
        if not self._show_overlay:
            for item in self.heatmap_items:
                item.setVisible(False)
            for item in self.grid_line_items:
                item.setVisible(False)
            for item in self.text_items:
                item.setVisible(False)
        else:
            self._apply_overlay_opacity()

    def _psnr_diff_to_color(self, diff: float, max_abs: float) -> QColor:
        """Map PSNR difference to diverging color scheme.
        
        - Green: Positive (S1 better)
        - Yellow: Zero (equal)
        - Red: Negative (S2 better)
        """
        # Normalize to [-1, 1] range
        t = diff / max_abs if max_abs > 0 else 0
        t = max(-1.0, min(1.0, t))
        
        if t >= 0:
            # Yellow (255, 255, 0) -> Green (0, 255, 0)
            r = int(255 * (1 - t))
            g = 255
            b = 0
        else:
            # Yellow (255, 255, 0) -> Red (255, 0, 0)
            t_abs = abs(t)
            r = 255
            g = int(255 * (1 - t_abs))
            b = 0
        
        return QColor(r, g, b, 140)

    def update_info(self, text: str):
        """Update info label text."""
        self.info_label.setText(text)

    def clear(self):
        """Clear the view."""
        self.scene.clear()
        self.frame_item = None
        self.heatmap_items.clear()
        self.grid_line_items.clear()
        self.text_items.clear()
        self._highlight_item = None
        self.psnr_grid = None
        self._zoom_initialized = False 
        self.info_label.setText("No frame loaded")
