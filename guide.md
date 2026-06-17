# LCEVC Enhancement Layer VQA Viewer — Development Guide

> This document is based on the architecture and implementation experience of the `psnr-cmp` project, organized as a complete technical guide for developing LCEVC enhancement layer stream viewing software.
> Key focus: **Right-click to view detailed pixels → Infinite canvas drag/zoom → Multi-window synchronization** core interaction chain.

---

## I. Overall Architecture

### 1.1 Project Structure (Recommended for Reuse)

```
lcevc-viewer/
├── main.py                    # Entry: QApplication + Dark Theme + Window Creation
├── core/
│   ├── __init__.py
│   ├── lcevc_reader.py        # LCEVC Stream Reader (replaces yuv_reader.py)
│   └── quality_engine.py      # Quality Analysis Engine (replaces psnr_engine.py)
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # Main Window: Layout + Signal Connection + Coordination Logic
│   ├── stream_view.py         # Frame Display View (replaces psnr_view.py)
│   ├── block_detail_view.py   # Pixel Detail View (reused core logic)
│   └── sidebar.py             # Sidebar Controls
└── utils/
    └── colormap.py            # Optional: Heatmap Coloring
```

### 1.2 Core Class Hierarchy

```
MainWindow
├── Sidebar                         (Configuration Panel)
├── QSplitter                       (Horizontal Split)
│   ├── StreamView (view1)          (View 1 - contains both normal/detail layers)
│   │   ├── QStackedLayout
│   │   │   ├── NormalWidget        (Frame image + Overlay)
│   │   │   │   └── ZoomableGraphicsView ← QGraphicsView
│   │   │   └── BlockDetailView     (Pixel grid canvas)
│   │   │       └── ZoomableDetailGraphicsView ← QGraphicsView
│   ├── StreamView (view2)
│   └── StreamView (diff_view)
```

### 1.3 Key Design Principles

| Principle | Description |
|------|------|
| **QGraphicsScene + QGraphicsView** | All visual displays (frame images, pixel grids) are based on Qt's Graphics View framework |
| **QStackedLayout Switching** | Normal view ↔ Detailed view switching via Stack, no pop-up windows created |
| **Signal/Slot Sync** | Multi-window zooming, dragging, and selection are all synchronized via signals |
| **_syncing Anti-recursion** | All synchronization methods must have a `_syncing` flag to prevent signal recursion |

---

## II. Dark Theme (VSCode Style)

### 2.1 Entry Setup (main.py)

```python
import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

# 1. Use Fusion style as the base
app = QApplication(sys.argv)
app.setStyle("Fusion")

# 2. Global Dark QSS
DARK_STYLE = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #cccccc; }
QGraphicsView { background-color: #252526; border: 1px solid #2d2d2d; }
QToolTip { background-color: #252526; color: #cccccc; border: 1px solid #3c3c3c; }
/* Scrollbar styles omitted... */
"""
app.setStyleSheet(DARK_STYLE)

# 3. QPalette for core color roles
palette = QPalette()
palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))
palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 38))
palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
app.setPalette(palette)

# 4. Windows Dark Title Bar
if sys.platform == "win32":
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    dwm = ctypes.windll.dwmapi
    hwnd = int(window.winId())
    value = ctypes.c_int(1)
    dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                               ctypes.byref(value), ctypes.sizeof(value))
```

---

## III. Core Module: Zoomable Canvas (ZoomableGraphicsView)

### 3.1 Design Essentials

This is the most critical low-level component of the entire application. It has two variants:
- **ZoomableGraphicsView**: Used for normal frame views (displays image + overlay)
- **ZoomableDetailGraphicsView**: Used for pixel detailed views (displays pixel grid)

### 3.2 Full Implementation Template

```python
from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent, QTransform

class ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView supporting mouse wheel zoom + gesture dragging.
    
    Key Features:
    1. Zoom anchor is always under the mouse cursor (not the viewport center)
    2. Drag mode is ScrollHandDrag (left-click hold and drag)
    3. Scene rectangle set to extremely large value to allow borderless dragging
    4. Emits transform_changed signal for multi-view synchronization
    """
    
    transform_changed = pyqtSignal(QTransform)
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        
        # ===== Key Settings =====
        # 1. Drag Mode: Left-click to drag the canvas
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        # 2. Disable Qt's built-in zoom anchor (we implement anchor-under-mouse manually)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        
        # 3. Zoom State
        self._zoom_level = 1.0
        self._min_zoom = 0.1    # Minimum zoom
        self._max_zoom = 10.0   # Maximum zoom
        self._syncing = False   # Anti-recursion flag
        
    def wheelEvent(self, event: QWheelEvent):
        """Mouse wheel zoom, anchor under the mouse cursor."""
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
            
        new_zoom = self._zoom_level * zoom_factor
        if new_zoom < self._min_zoom or new_zoom > self._max_zoom:
            return
        
        # ===== Anchor Logic (Critical!) =====
        # Method A (Recommended - for views with scrollbars):
        mouse_pos = event.position()                           # Mouse position in viewport
        scene_pos = self.mapToScene(mouse_pos.toPoint())       # Scene coords under mouse before zoom
        self.scale(zoom_factor, zoom_factor)                   # Execute scaling
        self._zoom_level = new_zoom
        new_viewport_pos = self.mapFromScene(scene_pos)        # New viewport position of same scene point after zoom
        delta_x = mouse_pos.x() - new_viewport_pos.x()        # Displacement difference
        delta_y = mouse_pos.y() - new_viewport_pos.y()
        self.horizontalScrollBar().setValue(                    # Adjust scrollbar compensation
            self.horizontalScrollBar().value() - int(delta_x))
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(delta_y))
        
        # Method B (Optional - for views without scrollbars):
        # old_pos = self.mapToScene(event.position().toPoint())
        # self.scale(zoom_factor, zoom_factor)
        # new_pos = self.mapToScene(event.position().toPoint())
        # delta = new_pos - old_pos
        # self.translate(delta.x(), delta.y())
        
        # Emit sync signal
        if not self._syncing:
            self.transform_changed.emit(self.transform())
    
    def sync_transform(self, transform: QTransform):
        """Synchronize transform matrix from other views."""
        if self._syncing:
            return
        self._syncing = True
        self.setTransform(transform)
        self._zoom_level = transform.m11()  # Extract horizontal zoom factor
        self._syncing = False
```

### 3.3 Comparison of Two Zoom Anchor Methods

| Feature | Method A (scrollbar compensation) | Method B (translate compensation) |
|------|------------------------|------------------------|
| Usage Scenario | Normal frame view (with scrollbars) | Pixel detail view (no scrollbars) |
| Precision | High (integer precision, but sufficient) | High (floating point precision) |
| Compatibility | Works well with scrollbar sync | Simpler but does not emit scroll signals |
| Code Location | `psnr_view.py:40-77` | `block_detail_view.py:37-58` |

### 3.4 Borderless Dragging

```python
# Set an extremely large logic rectangle immediately after scene creation
# This is only a coordinate range and does not allocate any graphic memory
self.scene = QGraphicsScene()
self.scene.setSceneRect(-100000, -100000, 200000, 200000)
```

> **Key Understanding**: `setSceneRect` only defines the **logic coordinate range**. Areas within the range that have no actual items do not consume memory.
> If not set, Qt will automatically calculate the scene size based on the items' boundingRect, causing dragging to stop at the content boundaries.

---

## IV. Core Module: Right-click to Enter Pixel Detail View

### 4.1 Interaction Flow

```
User right-clicks a block in the normal frame view
    ↓ block_right_clicked signal (bx, by)
MainWindow._show_block_detail(bx, by)
    ↓ Extract YUV pixel data for that block
    ↓ Call enter_block_detail(...) for each view
StreamView.enter_block_detail(...)
    ↓ detail_view.set_data(...)  // Render pixel grid
    ↓ stack.setCurrentWidget(detail_view)  // Switch to detail layer
User right-clicks in the detailed view
    ↓ view_right_clicked signal
    ↓ exit_requested signal
MainWindow._exit_block_detail()
    ↓ Call exit_block_detail() for each view
StreamView.exit_block_detail()
    ↓ stack.setCurrentWidget(normal_widget)  // Switch back to normal layer
```

### 4.2 QStackedLayout View Switching

```python
class StreamView(QWidget):
    """Container including Normal Frame View and Pixel Detail View."""
    
    def _setup_ui(self):
        # Use QStackedLayout for two-layer switching
        self.stack = QStackedLayout(self)
        
        # Layer 0: Normal Frame View
        self.normal_widget = QWidget()
        normal_layout = QVBoxLayout(self.normal_widget)
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-100000, -100000, 200000, 200000)
        self.view = ZoomableGraphicsView(self.scene, ...)
        normal_layout.addWidget(self.view)
        self.stack.addWidget(self.normal_widget)
        
        # Layer 1: Pixel Detail View
        self.detail_view = BlockDetailView()
        self.stack.addWidget(self.detail_view)
    
    def enter_block_detail(self, bx, by, block_size, data_y, data_u, data_v, ...):
        """Switch to detailed mode."""
        self.detail_view.set_data(bx, by, block_size, data_y, data_u, data_v, ...)
        self.stack.setCurrentWidget(self.detail_view)
    
    def exit_block_detail(self):
        """Switch back to normal mode."""
        self.stack.setCurrentWidget(self.normal_widget)
```

### 4.3 Capturing Right-click Signals

```python
class ZoomableGraphicsView(QGraphicsView):
    block_right_clicked = pyqtSignal(int, int)  # (block_x, block_y)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            scene_pos = self.mapToScene(event.pos())
            block_size = self._block_size_getter()
            if block_size > 0:
                bx = int(scene_pos.x() // block_size)
                by = int(scene_pos.y() // block_size)
                if bx >= 0 and by >= 0:
                    self.block_right_clicked.emit(bx, by)
        super().mousePressEvent(event)
```

### 4.4 Exiting Pixel Detail via Right-click

```python
class ZoomableDetailGraphicsView(QGraphicsView):
    view_right_clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.view_right_clicked.emit()  # → exit_requested → _exit_block_detail
        super().mousePressEvent(event)
```

---

## V. Core Module: Pixel Grid Detail View (BlockDetailView)

### 5.1 Pixel Grid Rendering

```python
class BlockDetailView(QWidget):
    """Draw pixel grid on infinite canvas."""
    
    def __init__(self):
        self.cell_size = 40       # Size of each pixel cell (pixels)
        self.spacing = 20         # Spacing between different component grids
        self._pixel_items = {}    # {(component, x, y): QGraphicsRectItem}
        self._hex_mode = False    # Hex/Dec display toggle
    
    def set_data(self, block_x, block_y, block_size,
                 data_y=None, data_u=None, data_v=None, ...):
        """Draw each pixel using QGraphicsRectItem."""
        # 1. Clear scene (Note: Reset overlay reference first!)
        self._highlight_overlay = None   # ← Critical for preventing crashes!
        self.scene.clear()
        self._pixel_items.clear()
        
        # 2. Render grids component by component
        current_x = 0
        if data_y is not None:
            self._draw_grid(y_block, ..., offset_x=current_x, label="Y")
            current_x += width * cell_size + spacing
        if data_u is not None:
            self._draw_grid(u_block, ..., offset_x=current_x, label="Cb")
            current_x += width * cell_size + spacing
        # ... similar for data_v
    
    def _draw_grid(self, data, ..., label):
        """Draw pixel grid for a single component."""
        for y in range(h):
            for x in range(w):
                val = data[y, x]
                
                # Create rectangle
                rect = QGraphicsRectItem(
                    offset_x + x * cell_size,
                    offset_y + y * cell_size,
                    cell_size, cell_size
                )
                rect.setPen(QPen(QColor(100, 100, 160)))  # Light lavender border
                rect.setBrush(QBrush(QColor(30, 30, 30)))
                
                # Store metadata (for click selection and hex/dec toggle)
                rect.pixel_x = global_x + x
                rect.pixel_y = global_y + y
                rect.pixel_val = val
                rect.component = label  # "Y" / "Cb" / "Cr"
                
                self.scene.addItem(rect)
                self._pixel_items[(label, rect.pixel_x, rect.pixel_y)] = rect
                
                # Text (pixel value)
                text = QGraphicsTextItem(str(int(val)), rect)  # rect is parent
                text.setFont(QFont("Consolas", 8))
                text.setDefaultTextColor(QColor(0, 255, 255))  # Cyan
                rect.text_item = text  # Reverse reference
```

### 5.2 Pixel Selection Highlighting

```python
def set_highlighted_pixel(self, component, x, y):
    """Highlight selected pixel with extended rounded border."""
    # 1. Safely remove old overlay
    if self._highlight_overlay is not None:
        try:
            self.scene.removeItem(self._highlight_overlay)
        except RuntimeError:
            pass  # scene.clear() already deleted it, item is invalid
        self._highlight_overlay = None
    
    # 2. Create new overlay (extended rounded rectangle)
    if (component, x, y) in self._pixel_items:
        item = self._pixel_items[(component, x, y)]
        rect = item.rect()
        
        extend = 6  # Extend outward by 6px
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(-extend, -extend, extend, extend), 10, 10)
        
        overlay = QGraphicsPathItem(path)
        pen = QPen(QColor(200, 100, 255))  # Orchid purple
        pen.setWidth(2)
        overlay.setPen(pen)
        overlay.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        overlay.setZValue(1000)  # Top layer
        
        self.scene.addItem(overlay)
        self._highlight_overlay = overlay
```

### 5.3 Pixel Click Recognition

```python
class ZoomableDetailGraphicsView(QGraphicsView):
    pixel_clicked = pyqtSignal(str, int, int)  # component, global_x, global_y
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.scene().itemAt(self.mapToScene(event.pos()), QTransform())
            
            # If text is clicked, get its parent (rectangle)
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            
            # Check for pixel metadata
            if hasattr(item, 'pixel_x') and hasattr(item, 'pixel_y'):
                self.pixel_clicked.emit(item.component, item.pixel_x, item.pixel_y)
```

---

## VI. Multi-window Synchronization Mechanism

### 6.1 Content Needing Synchronization

| Sync Item | Signal | Handler |
|-----------|--------|----------|
| **Zoom Transform** | `transform_changed(QTransform)` | `sync_transform(transform)` |
| **Scroll Position (Drag)** | `scroll_position_changed(h, v)` | `sync_scroll_position(h, v)` |
| **Pixel Selection** | `pixel_selected(comp, x, y)` | `set_highlighted_pixel(comp, x, y)` |
| **Exit Detailed Mode** | `exit_requested()` | `_exit_block_detail()` |

### 6.2 Signal Connection Pattern (N×N Full Connection)

```python
def _sync_detail_views(self):
    """Interconnect signals between all detail views."""
    if self._detail_sync_ready:
        return  # Idempotent: only connect once
    
    dv1 = self.view1.get_detail_view()
    dv2 = self.view2.get_detail_view()
    ddv = self.diff_view.get_detail_view()
    
    # Zoom sync (bi-directional connection for each pair)
    dv1.transform_changed.connect(dv2.sync_transform)
    dv1.transform_changed.connect(ddv.sync_transform)
    dv2.transform_changed.connect(dv1.sync_transform)
    dv2.transform_changed.connect(ddv.sync_transform)
    ddv.transform_changed.connect(dv1.sync_transform)
    ddv.transform_changed.connect(dv2.sync_transform)
    
    # Scroll sync (also N×N)
    dv1.scroll_position_changed.connect(dv2.sync_scroll_position)
    dv1.scroll_position_changed.connect(ddv.sync_scroll_position)
    # ... omit remaining combinations
    
    # Pixel selection sync (unified handling)
    dv1.pixel_selected.connect(self._on_pixel_selected)
    dv2.pixel_selected.connect(self._on_pixel_selected)
    ddv.pixel_selected.connect(self._on_pixel_selected)
    
    # Exit sync
    dv1.exit_requested.connect(self._exit_block_detail)
    dv2.exit_requested.connect(self._exit_block_detail)
    ddv.exit_requested.connect(self._exit_block_detail)
    
    self._detail_sync_ready = True

def _on_pixel_selected(self, component, x, y):
    """Pixel selection in any window → update highlights in all windows."""
    self.view1.get_detail_view().set_highlighted_pixel(component, x, y)
    self.view2.get_detail_view().set_highlighted_pixel(component, x, y)
    self.diff_view.get_detail_view().set_highlighted_pixel(component, x, y)
```

### 6.3 Anti-recursion Mechanism (Extremely Important!)

```python
def sync_transform(self, transform: QTransform):
    if self._syncing:        # ← Already syncing, do not process
        return
    self._syncing = True     # ← Mark entering sync
    self.setTransform(transform)
    self._syncing = False    # ← Sync completed

def scrollContentsBy(self, dx, dy):
    super().scrollContentsBy(dx, dy)
    if not self._syncing_scroll:     # ← Only emit signal in non-syncing state
        h = self.horizontalScrollBar().value()
        v = self.verticalScrollBar().value()
        self.scroll_position_changed.emit(h, v)

def sync_scroll_position(self, h, v):
    if self._syncing_scroll:    # ← Anti-recursion
        return
    self._syncing_scroll = True
    self.horizontalScrollBar().setValue(h)
    self.verticalScrollBar().setValue(v)
    self._syncing_scroll = False
```

> **Consequence of No _syncing**: A modifies → emits signal to B → B modifies → emits signal to A → Infinite loop → Hangs or crashes.

---

## VII. Common Pitfalls and Solutions

### 7.1 Crashes Caused by scene.clear()

**Issue**: `scene.clear()` deletes all items (including overlays), but Python-side references remain; calling `removeItem` then causes a crash.

**Solution**:
```python
def set_data(self, ...):
    self._highlight_overlay = None   # ← Nullify reference first
    self.scene.clear()               # ← Then clear scene
    self._pixel_items.clear()
```

```python
def set_highlighted_pixel(self, ...):
    if self._highlight_overlay is not None:
        try:
            self.scene.removeItem(self._highlight_overlay)
        except RuntimeError:
            pass  # ← Catch exception for already deleted C++ objects
        self._highlight_overlay = None
```

### 7.2 Inaccurate Zoom Anchor

**Issue**: Using Qt's built-in `AnchorUnderMouse` is inaccurate in some cases.

**Solution**: Disable Qt anchors and calculate manually:
```python
self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
# Then implement anchor logic manually in wheelEvent (see Chapter III)
```

### 7.3 Dragging Stops at Boundaries

**Issue**: Qt's default scene rect = items bounding rect; dragging stops at content boundaries.

**Solution**:
```python
self.scene.setSceneRect(-100000, -100000, 200000, 200000)  # No memory overhead
```

### 7.4 Diff View Block Size Out of Sync

**Issue**: When config changes block size, the selection box in diff view is not updated.

**Solution**: Sync block size and refresh highlight in `_update_diff_view`:
```python
self.diff_view.block_size = config["block_size"]
self.diff_view._update_highlight()
```

### 7.5 Detailed View Needs Refresh on Config Change

**Issue**: Switching components (Y/U/V) in detailed mode does not update the view.

**Solution**: Save current block position, check and re-render on config change:
```python
def _on_config_changed(self):
    self._update_psnr_only(config)
    if self._current_detail_block is not None:
        bx, by = self._current_detail_block
        self._show_block_detail(bx, by, "config_change")

def _exit_block_detail(self):
    self._current_detail_block = None   # ← Clear state
    ...
```

---

## VIII. LCEVC-Specific Extension Suggestions

### 8.1 Enhancement Layer Data Display

| Information | Display Method |
|------|----------|
| Base Layer Residual | Pixel grid (grayscale/heatmap) |
| L0/L1 Enhancement Coefficients | Pixel grid (positive/negative values distinguished by Red/Blue) |
| Prediction Mode | Block overlay color annotation |
| Quantization Step | Text overlaid on blocks |
| Decoded Reconstruction vs Original | Diff view |

### 8.2 Recommended Signal/Data Flow

```
LCEVCReader.read_frame()
    → (base_layer_y, base_layer_u, base_layer_v)    # Base layer
    → (enhance_l0_y, enhance_l0_u, enhance_l0_v)    # L0 enhancement
    → (enhance_l1_y, enhance_l1_u, enhance_l1_v)    # L1 enhancement
    → (reconstructed_y, reconstructed_u, ...)        # Final reconstruction

MainWindow._show_block_detail()
    → view1: Base layer pixels
    → view2: Enhancement layer coefficients
    → view3: Reconstructed pixels
    → diff_view: Reconstruction vs Original diff
```

### 8.3 Enhancement Layer Coefficient Coloring Suggestion

```python
def _draw_enhance_grid(self, data, ...):
    """Distinguish enhancement coefficients with positive/negative colors."""
    for y in range(h):
        for x in range(w):
            val = data[y, x]
            if val > 0:
                text_color = QColor(100, 255, 100)   # Green = Positive
                bg_color = QColor(20, 40, 20)
            elif val < 0:
                text_color = QColor(255, 100, 100)   # Red = Negative
                bg_color = QColor(40, 20, 20)
            else:
                text_color = QColor(100, 100, 100)   # Gray = Zero
                bg_color = QColor(30, 30, 30)
```

---

## IX. Full Signal Flow Diagram

```
┌─── Sidebar ───┐
│ config_changed ├──→ MainWindow._on_config_changed()
│ files_changed  ├──→ MainWindow._on_load()
│ frame_changed  ├──→ MainWindow._on_frame_changed()
└────────────────┘

┌─── ZoomableGraphicsView (Normal) ───┐
│ transform_changed    ├──→ Other view.sync_transform()
│ block_clicked        ├──→ MainWindow handles selection
│ block_right_clicked  ├──→ MainWindow._show_block_detail()
│ scroll_x/y_changed   ├──→ Other view.sync_scroll_x/y()
└──────────────────────────────────────┘

┌─── ZoomableDetailGraphicsView (Detail) ───┐
│ transform_changed        ├──→ Other detail.sync_transform()
│ scroll_position_changed  ├──→ Other detail.sync_scroll_position()
│ pixel_clicked            ├──→ BlockDetailView → MainWindow → All set_highlighted_pixel()
│ view_right_clicked       ├──→ exit_requested → MainWindow._exit_block_detail()
└───────────────────────────────────────────┘
```

---

## X. Development Sequence Suggestions

1. **Phase 1**: Build `main.py` + Dark Theme + `MainWindow` skeleton
2. **Phase 2**: Implement `ZoomableGraphicsView` (zoom + drag)
3. **Phase 3**: Implement `StreamView` (frame display + QStackedLayout)
4. **Phase 4**: Implement `BlockDetailView` (pixel grid + infinite canvas)
5. **Phase 5**: Right-click to enter/exit detailed view
6. **Phase 6**: Multi-window signal sync (zoom + drag + selection)
7. **Phase 7**: LCEVC-specific data reading and display
8. **Phase 8**: Sidebar controls + configuration linkage
