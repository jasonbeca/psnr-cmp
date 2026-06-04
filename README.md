# PSNR Comparison Tool

A high-performance YUV comparison and PSNR calculation tool built with PyQt6. This application allows users to visually compare a Reference YUV file against one or two Stream files, providing synchronized playback, block-level PSNR analysis, and detailed pixel-level inspection.

## Key Features

### 1. Multi-View Comparison
- **Split View**: Displays "Stream 1 vs Reference", "Stream 2 vs Reference", and an optional "Difference (S1 - S2)" view side-by-side.
- **Synchronization**: All views are fully synchronized for:
  - **Zoom & Pan**: Mouse wheel zoom (anchored to cursor) and drag-to-pan.
  - **Block Selection**: Clicking a block in any view selects it in all others.
  - **Pixel Inspection**: Selecting a pixel in detail mode highlights it across all views.
  - **Scrolling**: Horizontal and vertical scrollbars are linked.

### 2. Advanced Analysis
- **PSNR Heatmap**: Overlay shows color-coded blocks (Green/Yellow/Orange/Red) based on PSNR quality.
- **Diff View**: Visualizes absolute differences between Stream 1 and Stream 2.
  - Supports Y, U, V, or YUV (color) difference modes.
  - In Detail Mode, highlights non-zero differences in yellow.
- **Real-time Metrics**: Displays Average PSNR / Mean Absolute Difference for the current frame.
- **Component Selection**: Toggle display between Y, U, V, or YUV planes.

### 3. Detailed Inspection ("Infinite Canvas")
- **Right-Click Block Detail**: Right-clicking any 64x64 block switches the view to an in-place "Infinite Canvas" detail mode.
  - **In-Place Switching**: Replaces the video frame with a pixel grid view without opening new windows.
  - **Unified Canvas**: Displays Y, Cb, and Cr component grids side-by-side.
  - **Pixel Values**: Shows exact pixel values.
  - **Hex/Dec Toggle**: Switch pixel values between Decimal and Hexadecimal formats.
  - **PSNR Calculation**: Shows detailed MSE and PSNR calculation breakdown for the selected block (when Overlay is active).
  - **Pixel Highlighting**: Click any pixel to highlight it with a purple border across all synchronized views.

### 4. Format Support
- **YUV Playback**: Supports raw YUV files (I420/420p).
- **Encoded Streams**: Supports decoding observable streams (if integrated with `yuv_reader` extensions).
- **Navigation**: Frame slider, Next/Prev frame buttons.

## Project Architecture

### Directory Structure
```
root/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── core/
│   ├── psnr_engine.py      # Core PSNR calculation logic (MSE, dB, grid generation)
│   └── yuv_reader.py       # YUV file reading and frame decoding
├── ui/
│   ├── main_window.py      # Central controller: Layout, Signal connections, Data flow
│   ├── sidebar.py          # Left sidebar: Configuration, Navigation, View options
│   ├── psnr_view.py        # Wrapper widget managing Image View <-> Detail View switching
│   ├── block_detail_view.py# "Infinite Canvas" pixel grid implementation (QWidget + QGraphicsView)
│   └── block_detail_dialog.py # (Legacy) Dialog implementation of detail view
└── utils/
    └── colormap.py         # Color mapping utilities for heatmaps
```

### Key Components

- **`MainWindow` (`ui/main_window.py`)**:
  - Orchestrates the application.
  - Manages `YUVReader` and frame caching (`_cached_ref`, `_cached_s1`, `_cached_s2`).
  - Handles signal synchronization (Zoom, Pan, Selection) between `PSNRView` instances.
  - Implements the logic to switch all 3 views into Block Detail Mode (`_show_block_detail`, `_exit_block_detail`).

- **`PSNRView` (`ui/psnr_view.py`)**:
  - Uses `QStackedLayout` to manage two modes:
    1.  **Normal Mode**: `ZoomableGraphicsView` showing the video frame + PSNR Overlay.
    2.  **Detail Mode**: `BlockDetailView` showing the pixel grids.
  - Exposes unified signals (e.g., `view_transform_changed`) regardless of the active mode.

- **`BlockDetailView` (`ui/block_detail_view.py`)**:
  - Implements the "Infinite Canvas" using `QGraphicsScene`.
  - Renders pixel grids for Y, U, V components.
  - Handles interaction: Zoom (mouse anchor), Pan available, Pixel Click selection.
  - Supports Hex/Dec formatting via `set_hex_mode`.

- **`Sidebar` (`ui/sidebar.py`)**:
  - Controls file inputs (Ref, Stream 1, Stream 2).
  - Configures parameters (Resolution, Block Size, Component).
  - Toggles view options (Overlay, Diff View).
  - **New**: Controls Pixel Format (Hex/Dec) which broadcasts to all detail views.

## Recent Changes (as of Jan 2026)
- **In-Place Detail View**: Replaced popup dialogs with seamless in-place view switching.
- **Three-View Sync**: Full synchronization of detailed views (Stream 1, Stream 2, Diff) including zoom, pan, and pixel highlighting.
- **Component-Aware Selection**: Pixel selection respects Y/U/V components to ensure correct highlighting alignment.
- **Hex/Dec Support**: Added global toggle for pixel value formatting.

## Environment & Dependencies
The project uses a local virtual environment located at `.venv` to manage dependencies.

**Important for New Sessions:**
When starting a new terminal or AI session, the environment may not be automatically activated. If you encounter missing package errors, activate the environment manually:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on Linux/Mac:
```bash
source .venv/bin/activate
```

This prevents the need to re-install packages (`pip install -r requirements.txt`) every time a new session starts.

## Usage
1.  Run `python main.py`.
2.  Select Reference and Stream YUV files in the Sidebar.
3.  Set Resolution (e.g., 1920x1080) and YUV Format.
4.  Click **Load & Compare**.
5.  **Normal Mode**: Scroll/Drag to navigate. Toggle "Show PSNR Overlay".
6.  **Detail Mode**: Right-click any block to enter. Right-click again to exit.
## CentOS 7 离线编译 (无需复制源码)

1.  **准备**: 确保 `dist/centos` 文件夹已上传至服务器项目根目录下的 `dist/` 中。
    *(即目录结构应为: `~/psnr-cmp/dist/centos/`，里面包含 `wheels` 和 `Miniconda`)*
2.  **编译**:
    在项目根目录 (`~/psnr-cmp`) 直接运行：
    ```bash
    bash build-centos.sh
    ```
    脚本会自动调用 `dist/centos` 里的环境，编译当前目录的代码，生成的 Binary 会在 `dist/linux_output/` 下。
