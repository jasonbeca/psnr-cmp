"""
Main Window
Application window with sidebar and split comparison view.
Includes frame caching for faster component switching.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt

from .sidebar import Sidebar
from .psnr_view import PSNRView
from .block_detail_dialog import BlockDetailDialog
from core.yuv_reader import YUVReader
from core.psnr_engine import calculate_block_psnr, calculate_combined_psnr


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VidCompare Pro - Video Quality Analysis")
        self.setMinimumSize(1200, 700)
        
        self.reader = None
        
        # Frame cache for faster component switching
        self._cached_frame_idx = -1
        self._cached_ref = None  # (y, u, v)
        self._cached_s1 = None   # (y, u, v)
        self._cached_s2 = None   # (y, u, v)
        self._detail_sync_ready = False
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Horizontal splitter for views
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.view1 = PSNRView("Stream 1 vs Reference")
        self.view2 = PSNRView("Stream 2 vs Reference")
        self.diff_view = PSNRView("Difference (S1 - S2)")
        
        self.splitter.addWidget(self.view1)
        self.splitter.addWidget(self.view2)
        self.splitter.addWidget(self.diff_view)
        self.splitter.setSizes([500, 500, 0])
        self.diff_view.hide()  # Hidden by default
        
        main_layout.addWidget(self.splitter, stretch=1)

    def _connect_signals(self):
        self.sidebar.files_changed.connect(self._on_load)
        self.sidebar.config_changed.connect(self._on_config_changed)
        self.sidebar.frame_changed.connect(self._on_frame_changed)
        
        # Sync transform (zoom) between views
        self.view1.view_transform_changed.connect(self.view2.sync_from_view)
        self.view2.view_transform_changed.connect(self.view1.sync_from_view)
        self.view1.view_transform_changed.connect(self.diff_view.sync_from_view)
        self.view2.view_transform_changed.connect(self.diff_view.sync_from_view)  # Added
        self.diff_view.view_transform_changed.connect(self.view1.sync_from_view)
        self.diff_view.view_transform_changed.connect(self.view2.sync_from_view)
        
        # Sync scrollbars (pan) between views
        self.view1.scroll_x_changed.connect(self.view2.sync_scroll_x)
        self.view2.scroll_x_changed.connect(self.view1.sync_scroll_x)
        self.view1.scroll_y_changed.connect(self.view2.sync_scroll_y)
        self.view2.scroll_y_changed.connect(self.view1.sync_scroll_y)
        self.view1.scroll_x_changed.connect(self.diff_view.sync_scroll_x)
        self.view1.scroll_y_changed.connect(self.diff_view.sync_scroll_y)
        self.view2.scroll_x_changed.connect(self.diff_view.sync_scroll_x)  # Added
        self.view2.scroll_y_changed.connect(self.diff_view.sync_scroll_y)  # Added
        self.diff_view.scroll_x_changed.connect(self.view1.sync_scroll_x)
        self.diff_view.scroll_x_changed.connect(self.view2.sync_scroll_x)
        self.diff_view.scroll_y_changed.connect(self.view1.sync_scroll_y)
        self.diff_view.scroll_y_changed.connect(self.view2.sync_scroll_y)
        
        # Sync block selection between views
        self.view1.block_selected.connect(self.view2.sync_block_selection)
        self.view2.block_selected.connect(self.view1.sync_block_selection)
        self.view1.block_selected.connect(self.diff_view.sync_block_selection)
        self.view2.block_selected.connect(self.diff_view.sync_block_selection)  # Added
        self.diff_view.block_selected.connect(self.view1.sync_block_selection)
        self.diff_view.block_selected.connect(self.view2.sync_block_selection)
        
        # Overlay toggle
        self.sidebar.overlay_toggled.connect(self.view1.set_overlay_visible)
        self.sidebar.overlay_toggled.connect(self.view2.set_overlay_visible)
        self.sidebar.overlay_toggled.connect(self.diff_view.set_overlay_visible)
        self.sidebar.overlay_opacity_changed.connect(self._on_overlay_opacity_changed)
        
        # Right-click for block detail
        self.view1.block_right_clicked.connect(lambda bx, by: self._show_block_detail(bx, by, 'view1'))
        self.view2.block_right_clicked.connect(lambda bx, by: self._show_block_detail(bx, by, 'view2'))
        self.diff_view.block_right_clicked.connect(lambda bx, by: self._show_block_detail(bx, by, 'diff'))
        
        # Diff view toggle
        self.sidebar.diff_view_toggled.connect(self._toggle_diff_view)
        self.sidebar.diff_mode_changed.connect(self._on_diff_mode_changed)

        # Hex/Dec toggle sync
        self.sidebar.hex_mode_toggled.connect(self._on_hex_mode_changed)
        
        # Grid toggle (for grid-only mode)
        self.sidebar.grid_toggled.connect(self._on_grid_toggled)

    def _on_overlay_opacity_changed(self, value: int):
        opacity = max(0.0, min(1.0, value / 100.0))
        self.view1.set_overlay_opacity(opacity)
        self.view2.set_overlay_opacity(opacity)
        self.diff_view.set_overlay_opacity(opacity)

    def _toggle_diff_view(self, show: bool):
        """Show or hide the difference view."""
        if show:
            self.diff_view.show()
            self.splitter.setSizes([400, 400, 400])
            
            # First update diff data (sets the frame)
            config = self.sidebar.get_config()
            self._update_diff_view(config)
            
            # Use QTimer to delay sync until after layout is complete
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._sync_diff_view_delayed)
        else:
            self.diff_view.hide()
            self.splitter.setSizes([500, 500, 0])

    def _on_diff_mode_changed(self, _mode: str):
        config = self.sidebar.get_config()
        if hasattr(self, '_current_detail_block') and self._current_detail_block is not None:
            bx, by = self._current_detail_block
            self._show_block_detail(bx, by, "diff_mode_change")
        elif self.diff_view.isVisible():
            self._update_diff_view(config)
            if self.sidebar.grid_checkbox.isChecked():
                self._on_grid_toggled(True)

    def _get_diff_pair(self, config: dict):
        mode = config.get("diff_mode", "s1_s2")
        if mode == "s1_ref":
            return self._cached_s1, self._cached_ref, "S1 vs Ref", mode
        if mode == "s2_ref":
            return self._cached_s2, self._cached_ref, "S2 vs Ref", mode
        return self._cached_s1, self._cached_s2, "S1 vs S2", "s1_s2"
    
    def _sync_diff_view_delayed(self):
        """Delayed sync of diff view after layout is complete."""
        # Sync transform/zoom from view1
        self.diff_view.sync_from_view(self.view1.view.transform())
        self.diff_view.sync_scroll_x(self.view1.view.horizontalScrollBar().value())
        self.diff_view.sync_scroll_y(self.view1.view.verticalScrollBar().value())
        
        # If currently in detail mode, sync detail view transforms too
        if self.view1.stack.currentWidget() != self.view1.normal_widget:
            # We're in detail mode, sync the detail view
            dv1 = self.view1.get_detail_view()
            ddv = self.diff_view.get_detail_view()
            ddv.sync_transform(dv1.view.transform())
            ddv.sync_scroll_position(
                dv1.view.horizontalScrollBar().value(),
                dv1.view.verticalScrollBar().value()
            )

    def _on_load(self):
        """Load files and initialize comparison."""
        config = self.sidebar.get_config()
        
        if not config["ref_path"]:
            QMessageBox.warning(self, "Error", "Please select a reference YUV file.")
            return
        
        if not config["stream1_path"] and not config["stream2_path"]:
            QMessageBox.warning(self, "Error", "Please select at least one stream.")
            return

        try:
            self.reader = YUVReader(
                config["width"],
                config["height"],
                config["yuv_format"]
            )
            
            # Clear cache
            self._cached_frame_idx = -1
            self._cached_ref = None
            self._cached_s1 = None
            self._cached_s2 = None
            
            # Get frame count
            frame_count = self.reader.get_frame_count(config["ref_path"])
            self.sidebar.set_frame_count(frame_count)
            
            # Load first frame
            self._load_frame(0)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load files:\n{str(e)}")

    def _on_config_changed(self):
        """Re-calculate PSNR with new config (uses cache if same frame)."""
        if self.reader is None:
            return
        config = self.sidebar.get_config()
        self._update_psnr_only(config)
        
        # Refresh grid display if grid is visible (e.g., block size changed)
        if self.sidebar.grid_checkbox.isChecked():
            self._on_grid_toggled(True)
        
        # If currently in detail mode, refresh the detail view with new component selection
        if hasattr(self, '_current_detail_block') and self._current_detail_block is not None:
            bx, by = self._current_detail_block
            self._show_block_detail(bx, by, "config_change")

    def _on_frame_changed(self, frame_idx: int):
        """Load a specific frame."""
        if self.reader is None:
            return
        self._load_frame(frame_idx)

    def _load_frame(self, frame_idx: int):
        """Load and display a frame with PSNR calculations."""
        config = self.sidebar.get_config()
        
        try:
            # Check if we need to reload frames
            if frame_idx != self._cached_frame_idx:
                # Read reference frame
                ref_y, ref_u, ref_v = self.reader.read_yuv_frame(config["ref_path"], frame_idx)
                self._cached_ref = (ref_y, ref_u, ref_v)
                
                # Stream 1
                if config["stream1_path"]:
                    if config["stream1_path"].lower().endswith('.yuv'):
                        s1_y, s1_u, s1_v = self.reader.read_yuv_frame(config["stream1_path"], frame_idx)
                    else:
                        s1_y, s1_u, s1_v = self.reader.decode_stream_frame(config["stream1_path"], frame_idx)
                    self._cached_s1 = (s1_y, s1_u, s1_v)
                    self.view1.set_frame(s1_y, s1_u, s1_v)
                else:
                    self._cached_s1 = None
                
                # Stream 2
                if config["stream2_path"]:
                    if config["stream2_path"].lower().endswith('.yuv'):
                        s2_y, s2_u, s2_v = self.reader.read_yuv_frame(config["stream2_path"], frame_idx)
                    else:
                        s2_y, s2_u, s2_v = self.reader.decode_stream_frame(config["stream2_path"], frame_idx)
                    self._cached_s2 = (s2_y, s2_u, s2_v)
                    self.view2.set_frame(s2_y, s2_u, s2_v)
                else:
                    self._cached_s2 = None
                
                self._cached_frame_idx = frame_idx
            
            # Update PSNR with current config
            self._update_psnr_only(config)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load frame {frame_idx}:\n{str(e)}")

    def _update_psnr_only(self, config: dict):
        """Update PSNR calculations using cached frames."""
        if self._cached_ref is None:
            return
        
        ref_y, ref_u, ref_v = self._cached_ref
        
        # Update displayed component for both views
        component = config.get("components", "y")
        self.view1.set_display_component(component)
        self.view2.set_display_component(component)
        
        # Validate components
        if not config["components"]:
            return
        
        # Stream 1
        if self._cached_s1 is not None:
            s1_y, s1_u, s1_v = self._cached_s1
            psnr_grid = calculate_combined_psnr(
                ref_y, ref_u, ref_v,
                s1_y, s1_u, s1_v,
                config["block_size"],
                config["components"]
            )
            self.view1.set_psnr_grid(psnr_grid, config["block_size"])
            
            avg_psnr = psnr_grid[psnr_grid != float('inf')].mean() if (psnr_grid != float('inf')).any() else float('inf')
            self.view1.update_info(f"Avg PSNR ({config['components'].upper()}): {avg_psnr:.2f} dB" if avg_psnr != float('inf') else "Identical")
        
        # Stream 2
        if self._cached_s2 is not None:
            s2_y, s2_u, s2_v = self._cached_s2
            psnr_grid = calculate_combined_psnr(
                ref_y, ref_u, ref_v,
                s2_y, s2_u, s2_v,
                config["block_size"],
                config["components"]
            )
            self.view2.set_psnr_grid(psnr_grid, config["block_size"])
            
            avg_psnr = psnr_grid[psnr_grid != float('inf')].mean() if (psnr_grid != float('inf')).any() else float('inf')
            self.view2.update_info(f"Avg PSNR ({config['components'].upper()}): {avg_psnr:.2f} dB" if avg_psnr != float('inf') else "Identical")
        
        # Update diff view if visible
        if self.diff_view.isVisible():
            self._update_diff_view(config)

    def _update_diff_view(self, config: dict):
        """Update the difference view between Stream 1 and Stream 2."""
        import numpy as np
        
        if self._cached_s1 is None or self._cached_s2 is None or self._cached_ref is None:
            return

        diff_a, diff_b, diff_label, diff_mode = self._get_diff_pair(config)
        if diff_a is None or diff_b is None:
            return
        
        # Sync block_size for the diff view and refresh its selection highlight
        self.diff_view.block_size = config["block_size"]
        self.diff_view._update_highlight()  # Refresh selection rectangle with new block size
        
        s1_y, s1_u, s1_v = self._cached_s1
        s2_y, s2_u, s2_v = self._cached_s2
        ref_y, ref_u, ref_v = self._cached_ref
        a_y, a_u, a_v = diff_a
        b_y, b_u, b_v = diff_b
        
        component = config.get("components", "y").lower()
        
        self.diff_view.set_title(f"Difference ({diff_label})")

        if component == 'yuv':
            # Calculate diff for all channels and display as color
            diff_y = np.abs(a_y.astype(np.int16) - b_y.astype(np.int16))
            diff_u = np.abs(a_u.astype(np.int16) - b_u.astype(np.int16)) if a_u is not None and b_u is not None else None
            diff_v = np.abs(a_v.astype(np.int16) - b_v.astype(np.int16)) if a_v is not None and b_v is not None else None
            
            # Scale diff for visibility (multiply by 4 for better visibility)
            scale = 4
            diff_y = np.clip(diff_y * scale, 0, 255).astype(np.uint8)
            if diff_u is not None:
                diff_u = np.clip(diff_u * scale, 0, 255).astype(np.uint8)
            if diff_v is not None:
                diff_v = np.clip(diff_v * scale, 0, 255).astype(np.uint8)
            
            self.diff_view.set_frame(diff_y, diff_u, diff_v)
            self.diff_view.set_display_component('yuv')
        else:
            # Single component diff
            if component == 'y':
                diff = np.abs(a_y.astype(np.int16) - b_y.astype(np.int16))
            elif component == 'u' and a_u is not None and b_u is not None:
                diff = np.abs(a_u.astype(np.int16) - b_u.astype(np.int16))
                # Upsample to Y size for consistent display
                y_h, y_w = a_y.shape
                u_h, u_w = diff.shape
                scale_y = y_h // u_h
                scale_x = y_w // u_w
                diff = np.repeat(np.repeat(diff, scale_y, axis=0), scale_x, axis=1)
            elif component == 'v' and a_v is not None and b_v is not None:
                diff = np.abs(a_v.astype(np.int16) - b_v.astype(np.int16))
                # Upsample to Y size for consistent display
                y_h, y_w = a_y.shape
                v_h, v_w = diff.shape
                scale_y = y_h // v_h
                scale_x = y_w // v_w
                diff = np.repeat(np.repeat(diff, scale_y, axis=0), scale_x, axis=1)
            else:
                diff = np.abs(a_y.astype(np.int16) - b_y.astype(np.int16))
            
            # Scale for visibility
            scale = 4
            diff = np.clip(diff * scale, 0, 255).astype(np.uint8)
            
            self.diff_view.set_frame(diff, None, None)
            self.diff_view.set_display_component('y')
        
        if diff_mode == "s1_s2":
            # Calculate PSNR diff heatmap: PSNR(s1 vs ref) - PSNR(s2 vs ref)
            # This shows where stream1 is better (positive) or worse (negative) than stream2
            psnr_s1 = calculate_combined_psnr(
                ref_y, ref_u, ref_v,
                s1_y, s1_u, s1_v,
                config["block_size"],
                config["components"]
            )
            psnr_s2 = calculate_combined_psnr(
                ref_y, ref_u, ref_v,
                s2_y, s2_u, s2_v,
                config["block_size"],
                config["components"]
            )
            
            # Calculate PSNR difference (replace inf with a large value for calculation)
            max_psnr_val = 100.0
            psnr_s1_clean = np.where(psnr_s1 == float('inf'), max_psnr_val, psnr_s1)
            psnr_s2_clean = np.where(psnr_s2 == float('inf'), max_psnr_val, psnr_s2)
            psnr_diff = psnr_s1_clean - psnr_s2_clean  # Positive = S1 better, Negative = S2 better
            
            # Set the PSNR diff grid on diff view (custom handling for diff heatmap)
            self.diff_view.set_psnr_diff_grid(psnr_diff, config["block_size"])
        else:
            psnr_grid = calculate_combined_psnr(
                b_y, b_u, b_v,
                a_y, a_u, a_v,
                config["block_size"],
                config["components"]
            )
            self.diff_view.set_psnr_grid(psnr_grid, config["block_size"])
        
        # Calculate mean absolute difference and mean PSNR difference
        if component == 'y':
            mean_diff = np.abs(a_y.astype(np.float32) - b_y.astype(np.float32)).mean()
        elif component == 'yuv':
            mean_diff = np.abs(a_y.astype(np.float32) - b_y.astype(np.float32)).mean()
        elif component == 'u' and a_u is not None and b_u is not None:
            mean_diff = np.abs(a_u.astype(np.float32) - b_u.astype(np.float32)).mean()
        elif component == 'v' and a_v is not None and b_v is not None:
            mean_diff = np.abs(a_v.astype(np.float32) - b_v.astype(np.float32)).mean()
        else:
            mean_diff = 0.0

        if diff_mode == "s1_s2":
            mean_psnr_diff = np.mean(psnr_diff)
            self.diff_view.update_info(f"PSNR Diff (S1-S2): {mean_psnr_diff:+.2f}dB | MAD: {mean_diff:.2f}")
        else:
            avg_psnr = psnr_grid[psnr_grid != float('inf')].mean() if (psnr_grid != float('inf')).any() else float('inf')
            avg_text = f"{avg_psnr:.2f} dB" if avg_psnr != float('inf') else "Identical"
            self.diff_view.update_info(f"Avg PSNR ({diff_label}): {avg_text} | MAD: {mean_diff:.2f}")

    def _on_hex_mode_changed(self, is_hex: bool):
        """Update hex/dec display in detail views."""
        self.view1.get_detail_view().set_hex_mode(is_hex)
        self.view2.get_detail_view().set_hex_mode(is_hex)
        self.diff_view.get_detail_view().set_hex_mode(is_hex)

    def _on_grid_toggled(self, show_grid: bool):
        """Update grid-only overlay display."""
        import numpy as np
        
        config = self.sidebar.get_config()
        block_size = config["block_size"]
        
        # Update visibility for all views
        self.view1.set_grid_visible(show_grid)
        self.view2.set_grid_visible(show_grid)
        self.diff_view.set_grid_visible(show_grid)
        
        if show_grid:
            # Draw grid on stream views
            self.view1.show_grid_only(block_size)
            self.view2.show_grid_only(block_size)
            
            # For diff view, calculate which blocks have differences and highlight them
            if self._cached_s1 is not None and self._cached_s2 is not None and self._cached_ref is not None:
                diff_a, diff_b, _diff_label, _diff_mode = self._get_diff_pair(config)
                if diff_a is None or diff_b is None:
                    return
                s1_y, s1_u, s1_v = diff_a
                s2_y, s2_u, s2_v = diff_b
                
                component = config.get("components", "y").lower()
                
                # Calculate per-block difference
                height, width = s1_y.shape
                blocks_y = (height + block_size - 1) // block_size
                blocks_x = (width + block_size - 1) // block_size
                
                diff_mask = np.zeros((blocks_y, blocks_x), dtype=bool)
                
                for by in range(blocks_y):
                    for bx in range(blocks_x):
                        y_start = by * block_size
                        y_end = min(y_start + block_size, height)
                        x_start = bx * block_size
                        x_end = min(x_start + block_size, width)
                        
                        # Check if block has differences based on component
                        has_diff = False
                        
                        if component in ['y', 'yuv']:
                            block1 = s1_y[y_start:y_end, x_start:x_end]
                            block2 = s2_y[y_start:y_end, x_start:x_end]
                            if np.any(block1 != block2):
                                has_diff = True
                        
                        if component in ['u', 'yuv'] and s1_u is not None and s2_u is not None and not has_diff:
                            scale = max(1, s1_y.shape[0] // s1_u.shape[0])
                            uy_start, uy_end = y_start // scale, min(y_end // scale, s1_u.shape[0])
                            ux_start, ux_end = x_start // scale, min(x_end // scale, s1_u.shape[1])
                            if uy_end > uy_start and ux_end > ux_start:
                                block1 = s1_u[uy_start:uy_end, ux_start:ux_end]
                                block2 = s2_u[uy_start:uy_end, ux_start:ux_end]
                                if np.any(block1 != block2):
                                    has_diff = True
                        
                        if component in ['v', 'yuv'] and s1_v is not None and s2_v is not None and not has_diff:
                            scale = max(1, s1_y.shape[0] // s1_v.shape[0])
                            vy_start, vy_end = y_start // scale, min(y_end // scale, s1_v.shape[0])
                            vx_start, vx_end = x_start // scale, min(x_end // scale, s1_v.shape[1])
                            if vy_end > vy_start and vx_end > vx_start:
                                block1 = s1_v[vy_start:vy_end, vx_start:vx_end]
                                block2 = s2_v[vy_start:vy_end, vx_start:vx_end]
                                if np.any(block1 != block2):
                                    has_diff = True
                        
                        diff_mask[by, bx] = has_diff
                
                # Show grid with diff highlights on diff view
                self.diff_view.show_diff_highlight(diff_mask, block_size)

    def _sync_detail_views(self):
        """Connect synchronization signals for detail views."""
        if self._detail_sync_ready:
            return
        # Sync transform (zoom/pan)
        dv1 = self.view1.get_detail_view()
        dv2 = self.view2.get_detail_view()
        ddv = self.diff_view.get_detail_view()
        
        dv1.transform_changed.connect(dv2.sync_transform)
        dv2.transform_changed.connect(dv1.sync_transform)
        dv1.transform_changed.connect(ddv.sync_transform)
        ddv.transform_changed.connect(dv1.sync_transform)
        dv2.transform_changed.connect(ddv.sync_transform)
        ddv.transform_changed.connect(dv2.sync_transform)
        
        # Sync scroll position (pan/drag)
        dv1.scroll_position_changed.connect(dv2.sync_scroll_position)
        dv1.scroll_position_changed.connect(ddv.sync_scroll_position)
        dv2.scroll_position_changed.connect(dv1.sync_scroll_position)
        dv2.scroll_position_changed.connect(ddv.sync_scroll_position)
        ddv.scroll_position_changed.connect(dv1.sync_scroll_position)
        ddv.scroll_position_changed.connect(dv2.sync_scroll_position)
        
        # Sync pixel selection
        dv1.pixel_selected.connect(self._on_pixel_selected)
        dv2.pixel_selected.connect(self._on_pixel_selected)
        ddv.pixel_selected.connect(self._on_pixel_selected)
        
        # Sync exit
        dv1.exit_requested.connect(self._exit_block_detail)
        dv2.exit_requested.connect(self._exit_block_detail)
        ddv.exit_requested.connect(self._exit_block_detail)
        self._detail_sync_ready = True

    def _on_pixel_selected(self, component, x, y):
        """Sync pixel selection across all detail views."""
        self.view1.get_detail_view().set_highlighted_pixel(component, x, y)
        self.view2.get_detail_view().set_highlighted_pixel(component, x, y)
        self.diff_view.get_detail_view().set_highlighted_pixel(component, x, y)

    def _exit_block_detail(self):
        """Switch all views back to normal mode."""
        self._current_detail_block = None  # Clear state so config changes don't refresh
        self.view1.exit_block_detail()
        self.view2.exit_block_detail()
        self.diff_view.exit_block_detail()

    def _show_block_detail(self, bx: int, by: int, source: str):
        """Switch all views to in-place block detail mode."""
        import numpy as np
        
        config = self.sidebar.get_config()
        block_size = config["block_size"]
        
        # Ensure we have data
        if self._cached_ref is None or self._cached_s1 is None or self._cached_s2 is None:
            return
        
        # Save current block for config change refresh
        self._current_detail_block = (bx, by)

        ref_y, ref_u, ref_v = self._cached_ref
        s1_y, s1_u, s1_v = self._cached_s1
        s2_y, s2_u, s2_v = self._cached_s2
        
        show_overlay = self.sidebar.overlay_checkbox.isChecked()
        
        def calc_block_mse_psnr(ref_plane, tgt_plane, bx, by, block_size, scale=1):
            """Calculate MSE and PSNR for a specific block."""
            # Apply scale for chroma planes (e.g., 420 has half-size UV)
            sx = (bx * block_size) // scale
            sy = (by * block_size) // scale
            bs = max(1, block_size // scale)
            
            h, w = ref_plane.shape
            ex = min(sx + bs, w)
            ey = min(sy + bs, h)
            
            ref_block = ref_plane[sy:ey, sx:ex].astype(np.float64)
            tgt_block = tgt_plane[sy:ey, sx:ex].astype(np.float64)
            
            mse = np.mean((ref_block - tgt_block) ** 2)
            if mse == 0:
                return 0.0, float('inf')
            psnr = 10 * np.log10(255**2 / mse)
            return mse, psnr
        
        def get_psnr_text(ref, tgt, bx, by, block_size):
            """Generate PSNR calculation text for display."""
            ref_y, ref_u, ref_v = ref
            tgt_y, tgt_u, tgt_v = tgt
            
            lines = ["PSNR Calculation:"]
            
            # Y component
            y_mse, y_psnr = calc_block_mse_psnr(ref_y, tgt_y, bx, by, block_size, scale=1)
            psnr_str = f"{y_psnr:.2f}dB" if y_psnr != float('inf') else "∞ (identical)"
            lines.append(f"  Y:  MSE={y_mse:.4f}, PSNR={psnr_str}")
            
            # Cb component
            if ref_u is not None and tgt_u is not None:
                scale = max(1, ref_y.shape[0] // ref_u.shape[0])
                u_mse, u_psnr = calc_block_mse_psnr(ref_u, tgt_u, bx, by, block_size, scale=scale)
                psnr_str = f"{u_psnr:.2f}dB" if u_psnr != float('inf') else "∞ (identical)"
                lines.append(f"  Cb: MSE={u_mse:.4f}, PSNR={psnr_str}")
            
            # Cr component
            if ref_v is not None and tgt_v is not None:
                scale = max(1, ref_y.shape[0] // ref_v.shape[0])
                v_mse, v_psnr = calc_block_mse_psnr(ref_v, tgt_v, bx, by, block_size, scale=scale)
                psnr_str = f"{v_psnr:.2f}dB" if v_psnr != float('inf') else "∞ (identical)"
                lines.append(f"  Cr: MSE={v_mse:.4f}, PSNR={psnr_str}")
            
            return "\n".join(lines)
        
        def get_diff_text(s1, s2, bx, by, block_size):
            """Generate Mean Absolute Difference text for diff view."""
            s1_y, s1_u, s1_v = s1
            s2_y, s2_u, s2_v = s2
            
            lines = ["Difference Statistics:"]
            
            # Y component
            sx = bx * block_size
            sy = by * block_size
            h, w = s1_y.shape
            ex = min(sx + block_size, w)
            ey = min(sy + block_size, h)
            y_diff = np.abs(s1_y[sy:ey, sx:ex].astype(np.float64) - s2_y[sy:ey, sx:ex].astype(np.float64))
            y_mad = np.mean(y_diff)
            y_max = np.max(y_diff)
            lines.append(f"  Y:  MAD={y_mad:.4f}, Max={y_max:.0f}")
            
            # Cb component
            if s1_u is not None and s2_u is not None:
                scale = max(1, s1_y.shape[0] // s1_u.shape[0])
                ux = sx // scale
                uy = sy // scale
                ubs = max(1, block_size // scale)
                uh, uw = s1_u.shape
                uex = min(ux + ubs, uw)
                uey = min(uy + ubs, uh)
                u_diff = np.abs(s1_u[uy:uey, ux:uex].astype(np.float64) - s2_u[uy:uey, ux:uex].astype(np.float64))
                u_mad = np.mean(u_diff)
                u_max = np.max(u_diff)
                lines.append(f"  Cb: MAD={u_mad:.4f}, Max={u_max:.0f}")
            
            # Cr component
            if s1_v is not None and s2_v is not None:
                scale = max(1, s1_y.shape[0] // s1_v.shape[0])
                vx = sx // scale
                vy = sy // scale
                vbs = max(1, block_size // scale)
                vh, vw = s1_v.shape
                vex = min(vx + vbs, vw)
                vey = min(vy + vbs, vh)
                v_diff = np.abs(s1_v[vy:vey, vx:vex].astype(np.float64) - s2_v[vy:vey, vx:vex].astype(np.float64))
                v_mad = np.mean(v_diff)
                v_max = np.max(v_diff)
                lines.append(f"  Cr: MAD={v_mad:.4f}, Max={v_max:.0f}")
            
            return "\n".join(lines)
        
        diff_mode = config.get("diff_mode", "s1_s2")
        diff_label = "S1 vs S2"
        if diff_mode == "s1_ref":
            diff_label = "S1 vs Ref"
        elif diff_mode == "s2_ref":
            diff_label = "S2 vs Ref"
        psnr_text_1 = get_psnr_text(self._cached_ref, self._cached_s1, bx, by, block_size) if show_overlay else None
        psnr_text_2 = get_psnr_text(self._cached_ref, self._cached_s2, bx, by, block_size) if show_overlay else None
        if show_overlay:
            if diff_mode == "s1_ref":
                diff_text = get_diff_text(self._cached_s1, self._cached_ref, bx, by, block_size)
            elif diff_mode == "s2_ref":
                diff_text = get_diff_text(self._cached_s2, self._cached_ref, bx, by, block_size)
            else:
                diff_text = get_diff_text(self._cached_s1, self._cached_s2, bx, by, block_size)
        else:
            diff_text = None
        
        # Determine which components to show based on sidebar selection
        component = config.get("components", "yuv").lower()
        
        # Filter component data based on selection
        # For U/V components, we need to adjust block coordinates to account for chroma subsampling
        main_label = "Y"
        detail_bx, detail_by = bx, by
        detail_block_size = block_size
        
        if component == 'yuv':
            # Show all components
            v1_y, v1_u, v1_v = s1_y, s1_u, s1_v
            v2_y, v2_u, v2_v = s2_y, s2_u, s2_v
        elif component == 'y':
            # Only Y
            v1_y, v1_u, v1_v = s1_y, None, None
            v2_y, v2_u, v2_v = s2_y, None, None
        elif component == 'u':
            # Only U (Cb) - adjust block coordinates for chroma subsampling
            if s1_u is not None and s1_y is not None:
                scale_x = max(1, s1_y.shape[1] // s1_u.shape[1])
                scale_y = max(1, s1_y.shape[0] // s1_u.shape[0])
                # For chroma planes, the block position in luma grid maps to a scaled position in chroma
                detail_bx = bx
                detail_by = by
                # Block size in chroma plane is scaled down
                detail_block_size = max(1, block_size // scale_x)
            v1_y, v1_u, v1_v = s1_u, None, None
            v2_y, v2_u, v2_v = s2_u, None, None
            main_label = "Cb"
        elif component == 'v':
            # Only V (Cr) - adjust block coordinates for chroma subsampling
            if s1_v is not None and s1_y is not None:
                scale_x = max(1, s1_y.shape[1] // s1_v.shape[1])
                scale_y = max(1, s1_y.shape[0] // s1_v.shape[0])
                detail_bx = bx
                detail_by = by
                detail_block_size = max(1, block_size // scale_x)
            v1_y, v1_u, v1_v = s1_v, None, None
            v2_y, v2_u, v2_v = s2_v, None, None
            main_label = "Cr"
        else:
            v1_y, v1_u, v1_v = s1_y, s1_u, s1_v
            v2_y, v2_u, v2_v = s2_y, s2_u, s2_v
        
        # Prepare View 1 (S1)
        self.view1.enter_block_detail(
            detail_bx, detail_by, detail_block_size, 
            v1_y, v1_u, v1_v,
            is_diff_mode=False,
            psnr_text=psnr_text_1,
            main_label=main_label
        )
        
        # Prepare View 2 (S2)
        self.view2.enter_block_detail(
           detail_bx, detail_by, detail_block_size,
           v2_y, v2_u, v2_v,
           is_diff_mode=False,
           psnr_text=psnr_text_2,
           main_label=main_label
        )
        
        # Prepare Diff View
        self.diff_view.set_title(f"Difference ({diff_label})")
        if diff_mode == "s1_ref":
            diff_y, diff_u, diff_v = self._cached_s1[0], self._cached_s1[1], self._cached_s1[2]
            base_y, base_u, base_v = self._cached_ref
        elif diff_mode == "s2_ref":
            diff_y, diff_u, diff_v = self._cached_s2[0], self._cached_s2[1], self._cached_s2[2]
            base_y, base_u, base_v = self._cached_ref
        else:
            diff_y, diff_u, diff_v = self._cached_s1[0], self._cached_s1[1], self._cached_s1[2]
            base_y, base_u, base_v = self._cached_s2

        if component == 'yuv':
            d_y = np.abs(diff_y.astype(np.int16) - base_y.astype(np.int16))
            d_u = np.abs(diff_u.astype(np.int16) - base_u.astype(np.int16)) if diff_u is not None and base_u is not None else None
            d_v = np.abs(diff_v.astype(np.int16) - base_v.astype(np.int16)) if diff_v is not None and base_v is not None else None
        elif component == 'y':
            d_y = np.abs(diff_y.astype(np.int16) - base_y.astype(np.int16))
            d_u = None
            d_v = None
        elif component == 'u':
            d_y = np.abs(diff_u.astype(np.int16) - base_u.astype(np.int16)) if diff_u is not None and base_u is not None else None
            d_u = None
            d_v = None
        elif component == 'v':
            d_y = np.abs(diff_v.astype(np.int16) - base_v.astype(np.int16)) if diff_v is not None and base_v is not None else None
            d_u = None
            d_v = None
        else:
            d_y = np.abs(diff_y.astype(np.int16) - base_y.astype(np.int16))
            d_u = None
            d_v = None
        
        self.diff_view.enter_block_detail(
            detail_bx, detail_by, detail_block_size,
            d_y, d_u, d_v,
            is_diff_mode=True,
            psnr_text=diff_text,
            main_label=main_label
        )

        # Sync signals once (idempotent)
        self._sync_detail_views()

