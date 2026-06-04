"""
Colormap Utilities
Maps PSNR values to colors for heatmap visualization.
"""
import numpy as np
from PyQt6.QtGui import QColor


def psnr_to_color(psnr: float, min_psnr: float = 20.0, max_psnr: float = 50.0) -> QColor:
    """
    Map PSNR value to a color.
    
    Color scheme:
    - Low PSNR (bad quality): Red
    - Medium PSNR: Yellow
    - High PSNR (good quality): Green
    - Infinite PSNR (identical): Blue
    
    Args:
        psnr: PSNR value in dB
        min_psnr: Minimum PSNR for color mapping
        max_psnr: Maximum PSNR for color mapping
        
    Returns:
        QColor object
    """
    if psnr == float('inf'):
        return QColor(0, 100, 255, 150)  # Blue for identical
    
    # Clamp PSNR to range
    psnr = max(min_psnr, min(psnr, max_psnr))
    
    # Normalize to 0-1
    t = (psnr - min_psnr) / (max_psnr - min_psnr)
    
    # Interpolate: Red -> Yellow -> Green
    if t < 0.5:
        # Red to Yellow
        r = 255
        g = int(255 * (t * 2))
        b = 0
    else:
        # Yellow to Green
        r = int(255 * (1 - (t - 0.5) * 2))
        g = 255
        b = 0
    
    return QColor(r, g, b, 150)  # Semi-transparent


def create_heatmap_image(
    psnr_grid: np.ndarray,
    block_size: int,
    frame_width: int,
    frame_height: int,
    min_psnr: float = 20.0,
    max_psnr: float = 50.0
) -> np.ndarray:
    """
    Create RGBA heatmap image from PSNR grid.
    
    Args:
        psnr_grid: 2D array of PSNR values
        block_size: Size of each block in pixels
        frame_width: Target image width
        frame_height: Target image height
        min_psnr, max_psnr: PSNR range for color mapping
        
    Returns:
        RGBA numpy array (H, W, 4)
    """
    heatmap = np.zeros((frame_height, frame_width, 4), dtype=np.uint8)
    
    for by in range(psnr_grid.shape[0]):
        for bx in range(psnr_grid.shape[1]):
            y_start = by * block_size
            y_end = min(y_start + block_size, frame_height)
            x_start = bx * block_size
            x_end = min(x_start + block_size, frame_width)
            
            color = psnr_to_color(psnr_grid[by, bx], min_psnr, max_psnr)
            heatmap[y_start:y_end, x_start:x_end] = [
                color.red(), color.green(), color.blue(), color.alpha()
            ]
    
    return heatmap
