# LCEVC Enhancement Layer VQA Viewer — 开发指南

> 本文档基于 `psnr-cmp` 项目的架构和实现经验，整理出开发 LCEVC 增强层码流查看软件的完整技术指南。
> 重点涵盖：**右击查看详细像素 → 无限画布拖拽/缩放 → 多窗口同步** 这一核心交互链路。

---

## 一、整体架构

### 1.1 项目结构（推荐复用）

```
lcevc-viewer/
├── main.py                    # 入口：QApplication + 暗色主题 + 窗口创建
├── core/
│   ├── __init__.py
│   ├── lcevc_reader.py        # LCEVC 码流读取器（替换 yuv_reader.py）
│   └── quality_engine.py      # 质量分析引擎（替换 psnr_engine.py）
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # 主窗口：布局 + 信号连接 + 协调逻辑
│   ├── stream_view.py         # 帧显示视图（替换 psnr_view.py）
│   ├── block_detail_view.py   # 像素详细视图（复用核心逻辑）
│   └── sidebar.py             # 侧边栏控件
└── utils/
    └── colormap.py            # 可选：热力图着色
```

### 1.2 核心类层级关系

```
MainWindow
├── Sidebar                         (配置面板)
├── QSplitter                       (水平分割)
│   ├── StreamView (view1)          (视图1 - 包含正常/详细两层)
│   │   ├── QStackedLayout
│   │   │   ├── NormalWidget        (帧画面 + 叠加层)
│   │   │   │   └── ZoomableGraphicsView ← QGraphicsView
│   │   │   └── BlockDetailView     (像素网格画布)
│   │   │       └── ZoomableDetailGraphicsView ← QGraphicsView
│   ├── StreamView (view2)
│   └── StreamView (diff_view)
```

### 1.3 关键设计原则

| 原则 | 说明 |
|------|------|
| **QGraphicsScene + QGraphicsView** | 所有画面展示（帧画面、像素网格）都基于 Qt 的 Graphics View 框架 |
| **QStackedLayout 切换** | 正常视图 ↔ 详细视图通过 Stack 切换，不创建弹窗 |
| **Signal/Slot 同步** | 多窗口的缩放、拖拽、选择全部通过信号同步 |
| **_syncing 防递归** | 所有同步方法必须有 `_syncing` 标志防止信号递归 |

---

## 二、暗色主题（VSCode 风格）

### 2.1 入口设置（main.py）

```python
import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

# 1. 使用 Fusion 样式作为基底
app = QApplication(sys.argv)
app.setStyle("Fusion")

# 2. 全局暗色 QSS
DARK_STYLE = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #cccccc; }
QGraphicsView { background-color: #252526; border: 1px solid #2d2d2d; }
QToolTip { background-color: #252526; color: #cccccc; border: 1px solid #3c3c3c; }
/* 滚动条样式省略... */
"""
app.setStyleSheet(DARK_STYLE)

# 3. QPalette 设置核心颜色角色
palette = QPalette()
palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))
palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 38))
palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
app.setPalette(palette)

# 4. Windows 暗色标题栏
if sys.platform == "win32":
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    dwm = ctypes.windll.dwmapi
    hwnd = int(window.winId())
    value = ctypes.c_int(1)
    dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                               ctypes.byref(value), ctypes.sizeof(value))
```

---

## 三、核心模块：可缩放画布（ZoomableGraphicsView）

### 3.1 设计要点

这是整个应用最关键的底层组件。有两个变体：
- **ZoomableGraphicsView**：用于正常帧视图（显示图像 + 叠加层）
- **ZoomableDetailGraphicsView**：用于像素详细视图（显示像素网格）

### 3.2 完整实现模板

```python
from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent, QTransform

class ZoomableGraphicsView(QGraphicsView):
    """支持鼠标滚轮缩放 + 手势拖拽的 QGraphicsView。
    
    核心特性：
    1. 缩放锚点始终在鼠标光标下方（非视口中心）
    2. 拖拽模式为 ScrollHandDrag（左键按住拖拽）
    3. 场景矩形设为极大值，允许无边界拖拽
    4. 发出 transform_changed 信号用于多视图同步
    """
    
    transform_changed = pyqtSignal(QTransform)
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        
        # ===== 关键设置 =====
        # 1. 拖拽模式：鼠标左键拖拽画布
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        # 2. 禁用 Qt 内置缩放锚点（我们手动实现 anchor-under-mouse）
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        
        # 3. 缩放状态
        self._zoom_level = 1.0
        self._min_zoom = 0.1    # 最小缩放
        self._max_zoom = 10.0   # 最大缩放
        self._syncing = False   # 防递归标志
        
    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮缩放，锚点在鼠标光标下方。"""
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
            
        new_zoom = self._zoom_level * zoom_factor
        if new_zoom < self._min_zoom or new_zoom > self._max_zoom:
            return
        
        # ===== 锚点逻辑（关键！）=====
        # 方法A（推荐 - 用于有滚动条的视图）：
        mouse_pos = event.position()                           # 鼠标在视口中的位置
        scene_pos = self.mapToScene(mouse_pos.toPoint())       # 缩放前，鼠标下的场景坐标
        self.scale(zoom_factor, zoom_factor)                   # 执行缩放
        self._zoom_level = new_zoom
        new_viewport_pos = self.mapFromScene(scene_pos)        # 缩放后，同一场景点的新视口位置
        delta_x = mouse_pos.x() - new_viewport_pos.x()        # 位移差
        delta_y = mouse_pos.y() - new_viewport_pos.y()
        self.horizontalScrollBar().setValue(                    # 调整滚动条补偿
            self.horizontalScrollBar().value() - int(delta_x))
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(delta_y))
        
        # 方法B（可选 - 用于隐藏滚动条的视图）：
        # old_pos = self.mapToScene(event.position().toPoint())
        # self.scale(zoom_factor, zoom_factor)
        # new_pos = self.mapToScene(event.position().toPoint())
        # delta = new_pos - old_pos
        # self.translate(delta.x(), delta.y())
        
        # 发出同步信号
        if not self._syncing:
            self.transform_changed.emit(self.transform())
    
    def sync_transform(self, transform: QTransform):
        """从其他视图同步变换矩阵。"""
        if self._syncing:
            return
        self._syncing = True
        self.setTransform(transform)
        self._zoom_level = transform.m11()  # 提取水平缩放因子
        self._syncing = False
```

### 3.3 两种缩放锚点方法对比

| 特性 | 方法A（scrollbar 补偿） | 方法B（translate 补偿） |
|------|------------------------|------------------------|
| 使用场景 | 正常帧视图（有滚动条） | 像素详细视图（无滚动条） |
| 精度 | 高（整数精度，但足够） | 高（浮点精度） |
| 兼容性 | 与 scrollbar 同步配合好 | 更简洁但不emit scroll信号 |
| 代码位置 | `psnr_view.py:40-77` | `block_detail_view.py:37-58` |

### 3.4 无边界拖拽

```python
# 在 scene 创建后立即设置极大的逻辑矩形
# 仅是坐标范围，不分配任何图形内存
self.scene = QGraphicsScene()
self.scene.setSceneRect(-100000, -100000, 200000, 200000)
```

> **关键理解**：`setSceneRect` 仅定义**逻辑坐标范围**，范围内没有实际 item 的区域不消耗内存。
> 如果不设置，Qt 会自动根据 items 的 boundingRect 计算场景大小，导致拖拽到边界就停止。

---

## 四、核心模块：右键进入像素详细视图

### 4.1 交互流程

```
用户在正常帧视图右键点击某个 block
    ↓ block_right_clicked 信号 (bx, by)
MainWindow._show_block_detail(bx, by)
    ↓ 提取该 block 的 YUV 像素数据
    ↓ 对每个视图调用 enter_block_detail(...)
StreamView.enter_block_detail(...)
    ↓ detail_view.set_data(...)  // 渲染像素网格
    ↓ stack.setCurrentWidget(detail_view)  // 切换到详细层
用户在详细视图右键点击
    ↓ view_right_clicked 信号
    ↓ exit_requested 信号
MainWindow._exit_block_detail()
    ↓ 对每个视图调用 exit_block_detail()
StreamView.exit_block_detail()
    ↓ stack.setCurrentWidget(normal_widget)  // 切回正常层
```

### 4.2 QStackedLayout 实现视图切换

```python
class StreamView(QWidget):
    """包含 正常帧视图 和 像素详细视图 的容器。"""
    
    def _setup_ui(self):
        # 使用 QStackedLayout 实现两层切换
        self.stack = QStackedLayout(self)
        
        # Layer 0: 正常帧视图
        self.normal_widget = QWidget()
        normal_layout = QVBoxLayout(self.normal_widget)
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-100000, -100000, 200000, 200000)
        self.view = ZoomableGraphicsView(self.scene, ...)
        normal_layout.addWidget(self.view)
        self.stack.addWidget(self.normal_widget)
        
        # Layer 1: 像素详细视图
        self.detail_view = BlockDetailView()
        self.stack.addWidget(self.detail_view)
    
    def enter_block_detail(self, bx, by, block_size, data_y, data_u, data_v, ...):
        """切换到详细模式。"""
        self.detail_view.set_data(bx, by, block_size, data_y, data_u, data_v, ...)
        self.stack.setCurrentWidget(self.detail_view)
    
    def exit_block_detail(self):
        """切回正常模式。"""
        self.stack.setCurrentWidget(self.normal_widget)
```

### 4.3 右键信号的捕获

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

### 4.4 像素详细右键退出

```python
class ZoomableDetailGraphicsView(QGraphicsView):
    view_right_clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.view_right_clicked.emit()  # → exit_requested → _exit_block_detail
        super().mousePressEvent(event)
```

---

## 五、核心模块：像素网格详细视图（BlockDetailView）

### 5.1 像素网格渲染

```python
class BlockDetailView(QWidget):
    """在无限画布上绘制像素网格。"""
    
    def __init__(self):
        self.cell_size = 40       # 每个像素格子的大小（像素）
        self.spacing = 20         # 不同分量网格之间的间距
        self._pixel_items = {}    # {(component, x, y): QGraphicsRectItem}
        self._hex_mode = False    # Hex/Dec 显示切换
    
    def set_data(self, block_x, block_y, block_size,
                 data_y=None, data_u=None, data_v=None, ...):
        """用 QGraphicsRectItem 绘制每个像素。"""
        # 1. 清空场景（注意先重置 overlay 引用！）
        self._highlight_overlay = None   # ← 防崩溃关键！
        self.scene.clear()
        self._pixel_items.clear()
        
        # 2. 逐分量渲染网格
        current_x = 0
        if data_y is not None:
            self._draw_grid(y_block, ..., offset_x=current_x, label="Y")
            current_x += width * cell_size + spacing
        if data_u is not None:
            self._draw_grid(u_block, ..., offset_x=current_x, label="Cb")
            current_x += width * cell_size + spacing
        # ... data_v 类似
    
    def _draw_grid(self, data, ..., label):
        """绘制单个分量的像素网格。"""
        for y in range(h):
            for x in range(w):
                val = data[y, x]
                
                # 创建矩形
                rect = QGraphicsRectItem(
                    offset_x + x * cell_size,
                    offset_y + y * cell_size,
                    cell_size, cell_size
                )
                rect.setPen(QPen(QColor(100, 100, 160)))  # 淡紫蓝色边框
                rect.setBrush(QBrush(QColor(30, 30, 30)))
                
                # 存储元数据（用于点击选择和hex/dec切换）
                rect.pixel_x = global_x + x
                rect.pixel_y = global_y + y
                rect.pixel_val = val
                rect.component = label  # "Y" / "Cb" / "Cr"
                
                self.scene.addItem(rect)
                self._pixel_items[(label, rect.pixel_x, rect.pixel_y)] = rect
                
                # 文本（像素值）
                text = QGraphicsTextItem(str(int(val)), rect)  # rect 为 parent
                text.setFont(QFont("Consolas", 8))
                text.setDefaultTextColor(QColor(0, 255, 255))  # 青色
                rect.text_item = text  # 反向引用
```

### 5.2 像素选中高亮

```python
def set_highlighted_pixel(self, component, x, y):
    """用扩展圆角边框高亮选中像素。"""
    # 1. 安全移除旧 overlay
    if self._highlight_overlay is not None:
        try:
            self.scene.removeItem(self._highlight_overlay)
        except RuntimeError:
            pass  # scene.clear() 已删除，item 已失效
        self._highlight_overlay = None
    
    # 2. 创建新 overlay（扩展圆角矩形）
    if (component, x, y) in self._pixel_items:
        item = self._pixel_items[(component, x, y)]
        rect = item.rect()
        
        extend = 6  # 向外扩展 6px
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(-extend, -extend, extend, extend), 10, 10)
        
        overlay = QGraphicsPathItem(path)
        pen = QPen(QColor(200, 100, 255))  # 洋紫红色
        pen.setWidth(2)
        overlay.setPen(pen)
        overlay.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        overlay.setZValue(1000)  # 最顶层
        
        self.scene.addItem(overlay)
        self._highlight_overlay = overlay
```

### 5.3 点击像素识别

```python
class ZoomableDetailGraphicsView(QGraphicsView):
    pixel_clicked = pyqtSignal(str, int, int)  # component, global_x, global_y
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.scene().itemAt(self.mapToScene(event.pos()), QTransform())
            
            # 如果点击的是文本，获取其父级（矩形）
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            
            # 检查是否有像素元数据
            if hasattr(item, 'pixel_x') and hasattr(item, 'pixel_y'):
                self.pixel_clicked.emit(item.component, item.pixel_x, item.pixel_y)
```

---

## 六、多窗口同步机制

### 6.1 需要同步的内容

| 同步项 | 信号 | 处理方法 |
|--------|------|----------|
| **缩放变换** | `transform_changed(QTransform)` | `sync_transform(transform)` |
| **滚动位置（拖拽）** | `scroll_position_changed(h, v)` | `sync_scroll_position(h, v)` |
| **像素选择** | `pixel_selected(comp, x, y)` | `set_highlighted_pixel(comp, x, y)` |
| **退出详细** | `exit_requested()` | `_exit_block_detail()` |

### 6.2 信号连接模式（N×N 全连通）

```python
def _sync_detail_views(self):
    """将所有详细视图之间的信号互连。"""
    if self._detail_sync_ready:
        return  # 幂等：只连接一次
    
    dv1 = self.view1.get_detail_view()
    dv2 = self.view2.get_detail_view()
    ddv = self.diff_view.get_detail_view()
    
    # 缩放同步（每对双向连接）
    dv1.transform_changed.connect(dv2.sync_transform)
    dv1.transform_changed.connect(ddv.sync_transform)
    dv2.transform_changed.connect(dv1.sync_transform)
    dv2.transform_changed.connect(ddv.sync_transform)
    ddv.transform_changed.connect(dv1.sync_transform)
    ddv.transform_changed.connect(dv2.sync_transform)
    
    # 滚动同步（同样 N×N）
    dv1.scroll_position_changed.connect(dv2.sync_scroll_position)
    dv1.scroll_position_changed.connect(ddv.sync_scroll_position)
    # ... 省略其余组合
    
    # 像素选择同步（统一处理）
    dv1.pixel_selected.connect(self._on_pixel_selected)
    dv2.pixel_selected.connect(self._on_pixel_selected)
    ddv.pixel_selected.connect(self._on_pixel_selected)
    
    # 退出同步
    dv1.exit_requested.connect(self._exit_block_detail)
    dv2.exit_requested.connect(self._exit_block_detail)
    ddv.exit_requested.connect(self._exit_block_detail)
    
    self._detail_sync_ready = True

def _on_pixel_selected(self, component, x, y):
    """任意窗口的像素选择 → 更新所有窗口的高亮。"""
    self.view1.get_detail_view().set_highlighted_pixel(component, x, y)
    self.view2.get_detail_view().set_highlighted_pixel(component, x, y)
    self.diff_view.get_detail_view().set_highlighted_pixel(component, x, y)
```

### 6.3 防递归机制（极其重要！）

```python
def sync_transform(self, transform: QTransform):
    if self._syncing:        # ← 已在同步中，不再处理
        return
    self._syncing = True     # ← 标记进入同步
    self.setTransform(transform)
    self._syncing = False    # ← 同步完成

def scrollContentsBy(self, dx, dy):
    super().scrollContentsBy(dx, dy)
    if not self._syncing_scroll:     # ← 仅在非同步状态下发信号
        h = self.horizontalScrollBar().value()
        v = self.verticalScrollBar().value()
        self.scroll_position_changed.emit(h, v)

def sync_scroll_position(self, h, v):
    if self._syncing_scroll:    # ← 防递归
        return
    self._syncing_scroll = True
    self.horizontalScrollBar().setValue(h)
    self.verticalScrollBar().setValue(v)
    self._syncing_scroll = False
```

> **不加 _syncing 的后果**：A修改 → 发信号给B → B修改 → 发信号给A → 无限循环 → 卡死或崩溃

---

## 七、常见坑和解决方案

### 7.1 scene.clear() 导致的崩溃

**问题**：`scene.clear()` 删除所有 item（包括 overlay），但 Python 侧的引用还在，再 `removeItem` 就崩溃。

**解决**：
```python
def set_data(self, ...):
    self._highlight_overlay = None   # ← 先置空引用
    self.scene.clear()               # ← 再清除场景
    self._pixel_items.clear()
```

```python
def set_highlighted_pixel(self, ...):
    if self._highlight_overlay is not None:
        try:
            self.scene.removeItem(self._highlight_overlay)
        except RuntimeError:
            pass  # ← 捕获 C++ 对象已删除的异常
        self._highlight_overlay = None
```

### 7.2 缩放锚点不准

**问题**：使用 Qt 内置的 `AnchorUnderMouse` 在某些情况下不准确。

**解决**：禁用 Qt 锚点，手动计算：
```python
self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
# 然后在 wheelEvent 中手动实现锚点逻辑（见第三章）
```

### 7.3 拖拽到边界就停止

**问题**：Qt 默认 scene rect = items bounding rect，拖到内容边界就停了。

**解决**：
```python
self.scene.setSceneRect(-100000, -100000, 200000, 200000)  # 无内存开销
```

### 7.4 Diff 视图 blocksize 不同步

**问题**：config 切换 blocksize 时，diff 视图的选择框没有更新。

**解决**：在 `_update_diff_view` 中同步 blocksize 并刷新高亮：
```python
self.diff_view.block_size = config["block_size"]
self.diff_view._update_highlight()
```

### 7.5 配置变更时详细视图需要刷新

**问题**：在详细模式中切换分量（Y/U/V），视图不更新。

**解决**：保存当前 block 位置，config 变更时检查并重新渲染：
```python
def _on_config_changed(self):
    self._update_psnr_only(config)
    if self._current_detail_block is not None:
        bx, by = self._current_detail_block
        self._show_block_detail(bx, by, "config_change")

def _exit_block_detail(self):
    self._current_detail_block = None   # ← 清除状态
    ...
```

---

## 八、LCEVC 特定扩展建议

### 8.1 增强层数据展示

| 信息 | 展示方式 |
|------|----------|
| 基础层残差 | 像素网格（灰度/热力图） |
| L0/L1 增强系数 | 像素网格（正/负值用红/蓝区分） |
| 预测模式 | Block 叠加层颜色标注 |
| 量化步长 | 文字叠加在 block 上 |
| 解码重建 vs 原始 | Diff 视图 |

### 8.2 推荐的信号/数据流

```
LCEVCReader.read_frame()
    → (base_layer_y, base_layer_u, base_layer_v)    # 基础层
    → (enhance_l0_y, enhance_l0_u, enhance_l0_v)    # L0 增强
    → (enhance_l1_y, enhance_l1_u, enhance_l1_v)    # L1 增强
    → (reconstructed_y, reconstructed_u, ...)        # 最终重建

MainWindow._show_block_detail()
    → view1: 基础层像素
    → view2: 增强层系数
    → view3: 重建结果像素
    → diff_view: 重建 vs 原始 diff
```

### 8.3 增强层系数着色建议

```python
def _draw_enhance_grid(self, data, ...):
    """增强层系数用正/负颜色区分。"""
    for y in range(h):
        for x in range(w):
            val = data[y, x]
            if val > 0:
                text_color = QColor(100, 255, 100)   # 绿色 = 正值
                bg_color = QColor(20, 40, 20)
            elif val < 0:
                text_color = QColor(255, 100, 100)   # 红色 = 负值
                bg_color = QColor(40, 20, 20)
            else:
                text_color = QColor(100, 100, 100)   # 灰色 = 零
                bg_color = QColor(30, 30, 30)
```

---

## 九、完整信号流图

```
┌─── Sidebar ───┐
│ config_changed ├──→ MainWindow._on_config_changed()
│ files_changed  ├──→ MainWindow._on_load()
│ frame_changed  ├──→ MainWindow._on_frame_changed()
└────────────────┘

┌─── ZoomableGraphicsView (Normal) ───┐
│ transform_changed    ├──→ 其他 view.sync_transform()
│ block_clicked        ├──→ MainWindow 处理选择
│ block_right_clicked  ├──→ MainWindow._show_block_detail()
│ scroll_x/y_changed   ├──→ 其他 view.sync_scroll_x/y()
└──────────────────────────────────────┘

┌─── ZoomableDetailGraphicsView (Detail) ───┐
│ transform_changed        ├──→ 其他 detail.sync_transform()
│ scroll_position_changed  ├──→ 其他 detail.sync_scroll_position()
│ pixel_clicked            ├──→ BlockDetailView → MainWindow → 全部 set_highlighted_pixel()
│ view_right_clicked       ├──→ exit_requested → MainWindow._exit_block_detail()
└───────────────────────────────────────────┘
```

---

## 十、开发顺序建议

1. **Phase 1**：搭建 `main.py` + 暗色主题 + `MainWindow` 骨架
2. **Phase 2**：实现 `ZoomableGraphicsView`（缩放 + 拖拽）
3. **Phase 3**：实现 `StreamView`（帧显示 + QStackedLayout）
4. **Phase 4**：实现 `BlockDetailView`（像素网格 + 无限画布）
5. **Phase 5**：右键进入/退出详细视图
6. **Phase 6**：多窗口信号同步（缩放 + 拖拽 + 选择）
7. **Phase 7**：LCEVC 特定数据读取和展示
8. **Phase 8**：侧边栏控件 + 配置联动
